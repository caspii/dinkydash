"""What a family is allowed to spend on the model, and what everybody is.

    NoBudget()                        single mode: no ceiling, and no database
    PostgresBudget(pool, family_id)   cloud mode: the breaker
    for_family(pool, family_id)       the same, with the caps read from the environment

    budget.allow()                    charge one call, or raise OverBudget
    budget.record(input, output)      what that call actually used
    budget.generation_config(config)  apply the payer's model/token policy

Nothing bounded the Anthropic bill before this (DIN-43). The worker walks every
non-lapsed family and calls Claude, "Rewrite now" calls it from a web request,
and a bug that ticks in a loop costs exactly what an abusive account would. The
rate limits elsewhere in this codebase raise the cost of causing that; **this is
the only thing that bounds the damage once somebody pays it.**

**Calls, not money.** A price table would go stale silently and in the wrong
direction — it under-counts after a price rise, which is precisely when a
breaker matters. A call is exact, is knowable *before* it is made, and the
product already says how many there should be: one brief a day per family.
`doc/operations.md` carries the multiplication into pounds, where a wrong number
is a wrong note rather than a broken control.

**Charged on the attempt, not on success.** An expired API key retried every
five minutes pays for input tokens every time and reports no usage at all. A
breaker that counted successes would watch that happen for ever.

**One statement decides and records**, the way `accounts.issue_link` does its
rate limit, so two callers arriving together cannot both read "one call today"
and both make a second. The two halves are not equally exact, and the
difference is written down rather than glossed:

* **the per-family cap is exact.** It is enforced in the `ON CONFLICT ... DO
  UPDATE ... WHERE`, which Postgres evaluates against the locked, current row;
* **the global cap is approximate**, by at most the number of callers arriving
  in the same instant. Its daily total is read before the write; concurrent
  callers can pass the check together. The trigger adds every successful charge
  to `global_model_spend` atomically, without retaining family identifiers or
  refunding calls when an account is deleted.

Cloud generation uses the platform's model and output-token ceiling. Family
config cannot change either; single mode keeps the self-hoster's settings.

**The global cap scales with the number of families**, and that is deliberate: a
fixed number is a control that silently starts starving real boards on the day
the product grows into it, and nobody notices because the failure looks like a
quiet morning. `GLOBAL_FLOOR + GLOBAL_PER_FAMILY × families` stays generous at
every size while still catching a runaway, which is what a breaker is for.

This module imports no driver — it is handed a pool and asks it for connections,
like `accounts.py` and `screens.py`.
"""

import logging
import os
from datetime import datetime, timezone

from .claude_client import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, GenerationError

log = logging.getLogger(__name__)

# What one family may spend in a UTC day. The product makes **one** call a day;
# the rest is headroom for somebody pressing "Rewrite now" a few times after
# fixing a calendar, which is a reasonable thing to do and not worth refusing.
# A loop trips this within an hour.
FAMILY_CALLS_A_DAY = 12

# The global ceiling, as a floor plus an allowance per family. The floor is what
# lets a brand-new install with two families still absorb a day of somebody
# experimenting; the per-family part is what stops the whole thing needing to be
# re-tuned at every order of magnitude.
GLOBAL_FLOOR = 50
GLOBAL_PER_FAMILY = 4


class OverBudget(GenerationError):
    """The call was refused because it would cost more than is allowed.

    **A `GenerationError` on purpose.** Every caller already handles one of
    those by keeping the board that is on the wall and trying again later — a
    failure here is "not handled, simply due again", which is how the whole tick
    treats failure. Inventing a second kind of failure would mean a second
    keep-last-good path, and the one that got written second is the one that
    blanks somebody's screen.
    """


class NoBudget:
    """No ceiling. What single mode passes, which is to say: nothing.

    A self-hoster brings their own API key, so the bill is theirs and a limit we
    invented would be a nuisance rather than a protection. The two things that
    actually bound a Pi are already there and are not about money: `schedule.due`
    asks for one brief a day, and `generate.only_one_tick` stops a slow tick
    being paid for twice.
    """

    def allow(self):
        return None

    def record(self, input_tokens, output_tokens):
        return None

    def generation_config(self, config):
        return config


class PostgresBudget:
    """The breaker, for one family, over the shared pool."""

    def __init__(self, pool, family_id, family_a_day=FAMILY_CALLS_A_DAY,
                 global_floor=GLOBAL_FLOOR, global_per_family=GLOBAL_PER_FAMILY):
        self.pool = pool
        self.family_id = family_id
        self.family_a_day = family_a_day
        self.global_floor = global_floor
        self.global_per_family = global_per_family

    def generation_config(self, config):
        """The platform pays, so stored family overrides cannot choose the cost."""
        return dict(config, claude_model=DEFAULT_MODEL, max_tokens=DEFAULT_MAX_TOKENS)

    def allow(self):
        """Charge one call, or raise `OverBudget`. Returns how many are now used.

        The whole decision is the one statement below, and the per-family cap
        appears in it **twice**, which is not redundant. There are two paths
        through an upsert and each needs its own check:

        * the **insert** path is the first call of the day, when there is no row
          to conflict with and `DO UPDATE` never runs. The row's count is zero
          there, so the condition is `0 < cap`;
        * the **update** path carries the check in `DO UPDATE ... WHERE`, where
          Postgres evaluates it against the locked, current row — which is what
          makes the per-family cap exact rather than a stale read.

        Written with only the second, a cap of **0** let every family make one
        call a day: the brake that exists to stop all spending was the one
        setting that could not. Caught by a test, not by reading it.
        """
        day = _today()
        with self.pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO model_spend (day, family_id, calls)
                       SELECT %(day)s, %(family)s, 1
                       WHERE coalesce((SELECT calls FROM global_model_spend
                                       WHERE day = %(day)s), 0)
                             < (SELECT %(floor)s + %(per)s * count(*)
                                FROM families WHERE status <> 'lapsed')
                         -- The insert path: no row yet, so this family has made
                         -- nothing today. Without it a cap of 0 allows one.
                         AND 0 < %(family_cap)s
                       ON CONFLICT (day, family_id) DO UPDATE
                          SET calls = model_spend.calls + 1, updated_at = now()
                          WHERE model_spend.calls < %(family_cap)s
                       RETURNING calls""",
                    {"day": day, "family": self.family_id,
                     "floor": self.global_floor, "per": self.global_per_family,
                     "family_cap": self.family_a_day},
                )
                row = cur.fetchone()

        if row is None:
            # **Which of the two limits tripped is deliberately not worked
            # out.** It would be a second query on the path that is already
            # refusing, and it would change nothing: the caller keeps the board
            # that is on the wall either way. The numbers are in the line so
            # that whoever reads it can tell at a glance which one it must have
            # been, and `used_today()` answers it exactly if anybody needs it.
            log.warning("Refused a model call for family %s: over the daily "
                        "budget (%s a family, %s + %s a family globally).",
                        self.family_id, self.family_a_day,
                        self.global_floor, self.global_per_family)
            raise OverBudget(
                "Today's limit on rewriting the board has been reached. "
                "The board on the screen is unchanged, and this will work "
                "again tomorrow.")
        return row[0]

    def record(self, input_tokens, output_tokens):
        """Add what the call used. Never raises.

        Bookkeeping rather than control: the breaker already counted the call,
        and losing a token count must not turn a written board into a failure.
        The row exists by now — `allow()` made it — so this only ever updates.
        """
        try:
            with self.pool.connection() as conn, conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE model_spend
                           SET input_tokens = input_tokens + %s,
                               output_tokens = output_tokens + %s,
                               updated_at = now()
                           WHERE day = %s AND family_id = %s""",
                        (int(input_tokens or 0), int(output_tokens or 0),
                         _today(), self.family_id),
                    )
        except Exception:
            log.exception("Could not record what a model call used; the call "
                          "itself was counted and the board was written.")

    def used_today(self):
        """(this family's calls, everybody's calls) today. For the settings page
        and for anybody looking at a bill and wondering."""
        day = _today()
        with self.pool.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT coalesce((SELECT calls FROM model_spend
                                    WHERE family_id = %s AND day = %s), 0),
                          coalesce((SELECT calls FROM global_model_spend
                                    WHERE day = %s), 0)""",
                (self.family_id, day, day),
            )
            return cur.fetchone()


def for_family(pool, family_id):
    """A budget with the caps read from the environment.

    **Raisable without a deploy**, which is most of what you want from a breaker
    at two in the morning: the numbers are App Platform environment variables,
    and a bad one falls back to the constant above rather than to no limit at
    all. A breaker that fails open because somebody typed `twelve` is not one.
    """
    return PostgresBudget(
        pool, family_id,
        family_a_day=_number("DINKYDASH_FAMILY_CALLS_A_DAY", FAMILY_CALLS_A_DAY),
        global_floor=_number("DINKYDASH_GLOBAL_CALL_FLOOR", GLOBAL_FLOOR),
        global_per_family=_number("DINKYDASH_GLOBAL_CALLS_PER_FAMILY",
                                  GLOBAL_PER_FAMILY),
    )


def _number(name, fallback):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return fallback
    try:
        value = int(raw)
    except ValueError:
        log.warning("%s is not a number; using %s.", name, fallback)
        return fallback
    if value < 0:
        log.warning("%s is negative; using %s.", name, fallback)
        return fallback
    return value


def _today():
    """The UTC date. Not the family's, and that is the point.

    `generations.generated_for_date` is the family's local date, which is right
    for "is today's board written" and wrong for a global total: a day summed
    over a dozen local dates is not a day.
    """
    return datetime.now(timezone.utc).date()
