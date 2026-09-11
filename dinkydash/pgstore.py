"""The cloud half of the storage seam: one family's rows in Postgres.

Same seven operations as `FileStore`, same dicts in and out, so the runner, the
dashboard route and the settings routes cannot tell which one they were handed
(PLAN.md decision 10, and the seam named in DIN-19).

Kept in its own module rather than beside `FileStore` for one reason: single
mode must never import psycopg. A Raspberry Pi has no database and should not
install a driver for one, so `psycopg` lives in `requirements-cloud.txt` and
`dinkydash/store.py` stays importable with the single-mode dependencies.

**Every query is scoped to `self.family_id`.** There is no unscoped read and no
unscoped write in this file, and there must never be one — an id arriving in a
URL is a claim, not a fact, and the place to check it is before it reaches a
store, not inside one.

Where the payload lives:

    events, calendar_statuses, calendars_fetched_at  ->  agendas    (one row)
    headline, note, note_kind                        ->  generations.brief
    generated_for_date, generated_at, model, tokens  ->  generations columns

`load_payload` puts the two back together as the dict the engine takes, and
`save_agenda` and `save_brief` each write one table and never the other. That
is why the two are separate operations rather than one `save_payload`: a brief
whose write is separated from its read by a slow model call would otherwise
overwrite an agenda that landed in between (DIN-28). Config saves and agenda
publication also lock the family's config row: invalidation and settings commit
together, and a fetch made with obsolete calendar settings is rejected (DIN-46).
Network requests run outside these transactions.
"""

import logging
from datetime import date, datetime, timezone

from psycopg.types.json import Jsonb

from . import config as config_module
from .store import AGENDA_KEYS, calendar_config, invalidated_agenda

log = logging.getLogger(__name__)

# What `generations` holds in real columns rather than inside `brief`.
GENERATION_COLUMNS = ("generated_for_date", "generated_at", "model",
                      "input_tokens", "output_tokens")

# Everything else the model wrote. Anything the payload gains that is not named
# above lands here too, so a new key needs no migration.
BRIEF_KEYS = ("headline", "note", "note_kind")


class NoSuchFamily(LookupError):
    """That family id has no row.

    Named rather than a bare `LookupError` because the web app handles it: a
    session naming a family that has since been deleted should sign the holder
    out, not 500. `KeyError` and `IndexError` are `LookupError`s too, and an
    error handler catching the parent would swallow real bugs and send them to
    the login page.
    """


class PostgresStore:
    """One family, as rows. Construct one per request or per worker iteration."""

    def __init__(self, pool, family_id):
        self.pool = pool
        self.family_id = family_id

    # -- the config ---------------------------------------------------------

    def load_config(self):
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT config FROM families WHERE id = %s", (self.family_id,))
            row = cur.fetchone()
        if row is None:
            raise NoSuchFamily(f"No family {self.family_id}")
        return config_module.with_defaults(dict(row[0] or {}))

    def save_config(self, config, *, invalidate_calendars=()):
        with self.pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                previous = self._locked_config(cur)
                agenda = invalidated_agenda(previous, config, self._load_agenda(cur),
                                            invalidate_calendars)
                cur.execute(
                    "UPDATE families SET config = %s, updated_at = now() WHERE id = %s",
                    (Jsonb(_plain(config)), self.family_id),
                )
                if agenda is not None:
                    self._save_agenda(cur, agenda)

    def _locked_config(self, cur):
        """Serialize settings edits and agenda publication, never the fetch itself."""
        cur.execute("SELECT config FROM families WHERE id = %s FOR UPDATE", (self.family_id,))
        row = cur.fetchone()
        if row is None:
            raise NoSuchFamily(f"No family {self.family_id}")
        return config_module.with_defaults(dict(row[0] or {}))

    # -- the dashboard ----------------------------------------------------------

    def load_payload(self, config=None):
        """The stored dashboard, or None when this family has never had one."""
        with self.pool.connection() as conn, conn.cursor() as cur:
            agenda = self._load_agenda(cur)
            cur.execute(
                """SELECT brief, generated_for_date, generated_at, model,
                          input_tokens, output_tokens
                   FROM generations
                   WHERE family_id = %s AND status = 'ok'
                   ORDER BY generated_for_date DESC
                   LIMIT 1""",
                (self.family_id,),
            )
            generation = cur.fetchone()

        if agenda is None and generation is None:
            return None

        payload = {}
        if generation is not None:
            brief, for_date, at, model, tokens_in, tokens_out = generation
            payload.update(brief or {})
            payload["generated_for_date"] = _iso(for_date)
            payload["generated_at"] = _iso(at)
            payload["model"] = model
            payload["input_tokens"] = tokens_in
            payload["output_tokens"] = tokens_out
        if agenda is not None:
            payload.update(agenda)
        return payload

    def _load_agenda(self, cur):
        cur.execute("SELECT events, statuses, fetched_at FROM agendas WHERE family_id = %s",
                    (self.family_id,))
        row = cur.fetchone()
        if row is None:
            return None
        events, statuses, fetched_at = row
        return {"events": events or [], "calendar_statuses": statuses or [],
                "calendars_fetched_at": _iso(fetched_at)}

    def save_agenda(self, config, agenda):
        """Publish only if the saved calendar settings still match the fetch."""
        with self.pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                if calendar_config(self._locked_config(cur)) != calendar_config(config):
                    return False
                self._save_agenda(cur, agenda)
                return True

    def _save_agenda(self, cur, agenda):
        cur.execute(
            """INSERT INTO agendas (family_id, events, statuses, fetched_at)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (family_id) DO UPDATE
               SET events = EXCLUDED.events,
                   statuses = EXCLUDED.statuses,
                   fetched_at = EXCLUDED.fetched_at""",
            (self.family_id, Jsonb(agenda.get("events") or []),
             Jsonb(agenda.get("calendar_statuses") or []),
             _stamp(agenda.get("calendars_fetched_at"))),
        )

    def save_brief(self, config, brief):
        """Replace today's `generations` row. Never writes `agendas`.

        A brief with no date is a refresh-shaped payload arriving at the wrong
        door — there is no generation to write, and inventing one would put a
        dashboard with no words on the wall claiming a date.
        """
        for_date = brief.get("generated_for_date")
        if not for_date:
            return
        with self.pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO generations
                           (family_id, generated_for_date, generated_at, brief,
                            model, input_tokens, output_tokens)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (family_id, generated_for_date) DO UPDATE
                       SET generated_at = EXCLUDED.generated_at,
                           brief = EXCLUDED.brief,
                           model = EXCLUDED.model,
                           input_tokens = EXCLUDED.input_tokens,
                           output_tokens = EXCLUDED.output_tokens""",
                    (self.family_id, _as_date(for_date), _stamp(brief.get("generated_at")),
                     Jsonb(_brief(brief)), brief.get("model"),
                     brief.get("input_tokens"), brief.get("output_tokens")),
                )

    # -- what was written recently ------------------------------------------

    def recent_notes(self, config, days):
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT note FROM (
                       SELECT id, note FROM content_history
                       WHERE family_id = %s
                       ORDER BY id DESC LIMIT %s
                   ) recent ORDER BY id ASC""",
                (self.family_id, days),
            )
            return [row[0] for row in cur.fetchall() if row[0]]

    def record_note(self, config, entry, keep=30):
        """Add one entry and trim to the last `keep`. Never raises.

        A history that cannot be written costs a repeated octopus fact in a
        fortnight; it is not worth losing a written dashboard over. Same promise
        `FileStore` makes, for the same reason.
        """
        try:
            with self.pool.connection() as conn, conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO content_history
                               (family_id, date, headline, note, note_kind)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (self.family_id, _as_date(entry.get("date")),
                         entry.get("headline"), entry.get("note"), entry.get("note_kind")),
                    )
                    # Trimmed here rather than by a nightly job, so the table
                    # cannot grow between sweeps and Phase 5's retention answer
                    # stays "the last thirty, always".
                    cur.execute(
                        """DELETE FROM content_history
                           WHERE family_id = %s AND id NOT IN (
                               SELECT id FROM content_history
                               WHERE family_id = %s ORDER BY id DESC LIMIT %s
                           )""",
                        (self.family_id, self.family_id, keep),
                    )
        except Exception as exc:
            log.warning("Could not write the note history: %s", exc)


def _brief(payload):
    """The model's words, plus anything new the payload has grown.

    Named keys go in explicitly; the rest is swept up so a payload that gains a
    key still round-trips without a migration. The refresh keys and the columns
    above are the only things kept out.
    """
    kept = set(AGENDA_KEYS) | set(GENERATION_COLUMNS)
    brief = {key: value for key, value in payload.items() if key not in kept}
    for key in BRIEF_KEYS:
        brief.setdefault(key, payload.get(key))
    return brief


def _plain(value):
    """A config dict as plain JSON types.

    Single mode's dict is ruamel's CommentedMap with DoubleQuotedScalarString
    values — both subclasses of dict and str, so they serialise, but they carry
    comment and style objects that mean nothing here.
    """
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, str):
        return str(value)
    return value


def _iso(value):
    """A stamp as the payload holds it: an ISO string in UTC, or None.

    `FileStore` stores what the runner wrote, which is always UTC ISO. Postgres
    hands back an aware datetime in whatever the session zone is, so it is
    converted rather than formatted — otherwise the two stores would disagree
    about what time a dashboard was written, and only one of them would be right.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _stamp(value):
    """An ISO string from the payload as a datetime Postgres will take."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _as_date(value):
    if not value or isinstance(value, date):
        return value or None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None
