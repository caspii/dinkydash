"""Reading and writing config.yaml.

The settings UI writes this file back, so loads and saves go through ruamel's
round-trip mode: your comments and key order survive an edit made from a phone.
"""

import logging
import os
import secrets
import tempfile
from datetime import datetime
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from .calendars import addresses, zone

log = logging.getLogger(__name__)

DEFAULTS = {
    "family_name": "Our family",
    "timezone": "UTC",
    "location": "",
    "theme": "light",
    "calendars": [],
    "people": [],
    "pets": [],
    "recurring": [],
    "special_dates": [],
    "claude_model": "claude-haiku-4-5",
    "max_tokens": 1024,
    "calendar_days_ahead": 14,
    "history_days": 30,
    # Read only by `generate.py --tick`. A plain run still does both at once.
    "refresh_minutes": 60,
    "brief_time": "06:00",
    # Storage-layer keys, read only by dinkydash.store.FileStore. They say
    # where a self-hoster's generated files go and mean nothing in cloud mode,
    # where the same two things are rows.
    "data_file": "dashboard_data.json",
    "content_history_file": "content_history.json",
}

THEMES = ("light", "dark")

# Avatar colours the dashboard and the settings UI both understand. Names rather
# than hex so a theme change doesn't strand a colour nobody can read.
AVATAR_COLORS = ("purple", "blue", "green", "pink", "orange", "amber", "teal")

# The lists the settings UI edits. Every item in them carries a stable `id`.
LIST_KEYS = ("people", "pets", "recurring", "special_dates", "calendars")

# The mark on a person or pet the app invented rather than a family typed
# (see `starter_config`). The settings form drops it the first time that item
# is saved, so "still marked" means exactly "never touched" — which is what
# `invented_names` and `is_set_up` read, and what holds the first brief back.
INVENTED = "invented"

# Ids are short and typed by nobody, but they end up in URLs and get read aloud
# when something goes wrong, so leave out the characters that look like others.
ID_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
ID_LENGTH = 8

# A screen URL is read off a television and typed on a remote, so it uses the
# same unambiguous alphabet — 12 characters of it is about 59 bits, and the
# route rate-limits misses. The column allows 10 to 32.
SCREEN_TOKEN_LENGTH = 12


def quoted(value):
    """A string that stays quoted when the file is written back.

    `06:00` is a plain string to ruamel's resolver but a sexagesimal integer to
    a YAML 1.1 one, and config.yaml is meant to be editable by hand with
    whatever parser the reader has. So `brief_time` is written the way
    config.example.yaml documents it — in quotes.
    """
    return DoubleQuotedScalarString(str(value))


def _yaml():
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # don't rewrap long iCal URLs onto continuation lines
    # Indent list items under their key, the way the example file is written —
    # otherwise the first save from the UI re-indents the whole file and every
    # later diff is noise.
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def config_path():
    """Where config.yaml lives. Override with DINKYDASH_CONFIG."""
    return Path(os.environ.get("DINKYDASH_CONFIG", "config.yaml")).expanduser()


def load_config(path=None):
    """Load config.yaml, applying defaults and migrating old shapes."""
    path = Path(path) if path else config_path()
    with open(path) as f:
        raw = _yaml().load(f) or {}
    return with_defaults(raw)


def save_config(config, path=None):
    """Write config.yaml atomically, preserving comments and key order."""
    path = Path(path) if path else config_path()
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            _yaml().dump(config, f)
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    log.info("Wrote %s", path)


def with_defaults(raw):
    """Fill in defaults and migrate pre-multi-calendar config in place."""
    config = raw
    for key, value in DEFAULTS.items():
        if config.get(key) is None:
            config[key] = [] if isinstance(value, list) else value

    # A single calendar_url becomes the first entry in `calendars`, and the
    # global calendar_filter_emails that went with it becomes that entry's
    # `shared_with`. The old key meant what the new one means — show me the
    # events my partner is on — but it was one filter for the one URL, so it
    # only has a home when that URL is what is being migrated.
    legacy_url = config.pop("calendar_url", None)
    legacy_filter = addresses(config.pop("calendar_filter_emails", None))
    if legacy_url and not config["calendars"]:
        feed = {"label": "Calendar", "url": legacy_url, "enabled": True}
        if legacy_filter:
            feed["shared_with"] = legacy_filter
        config["calendars"] = [feed]
        log.info("Migrated calendar_url into calendars[]")
    elif legacy_filter:
        log.warning(
            "Ignoring calendar_filter_emails: it was one filter for one calendar_url. "
            "Put the addresses under `shared_with` on the calendar they were meant for."
        )

    if config.get("theme") not in THEMES:
        config["theme"] = "light"

    return config


def new_id(taken=()):
    """A short id for a list item, avoiding any already in `taken`."""
    taken = set(taken)
    while True:
        value = "".join(secrets.choice(ID_ALPHABET) for _ in range(ID_LENGTH))
        if value not in taken:
            return value


def new_screen_token():
    """The unguessable part of a family's dashboard URL.

    A bearer credential: whoever holds it sees the dashboard, which is the whole
    point — a wall panel cannot sign in. Rotatable from the settings page, so
    this is called again rather than once per family for ever.
    """
    return "".join(secrets.choice(ID_ALPHABET)
                   for _ in range(SCREEN_TOKEN_LENGTH))


def starter_config():
    """What a brand-new family gets before they have typed anything.

    A dashboard with nothing on it looks broken rather than empty, and the first
    thing a parent sees should be the shape of the thing they signed up for —
    so this seeds the same invented family `config.example.yaml` documents:
    two children, a dog, two chores that rotate between them, and two
    countdowns. Every one of them is there to be replaced.

    **No calendar.** Not even an example URL. An iCal address is a password in
    a URL, and one that worked would put somebody else's appointments on a
    stranger's wall; one that did not would be a broken feed on a dashboard nobody
    has finished setting up yet. Adding the first calendar is the parent's
    first real act in the settings UI, and the per-provider help is written for
    exactly that moment.

    **The timezone is the default, which is UTC**, because guessing it from an
    IP address is wrong often enough to be worse than asking. It is the one
    setting that changes what the dashboard *says* — when today rolls over, and
    what time the brief is written — so the welcome on the settings home points
    at it first.

    Pure, and no clock: dates of birth are fixed like the example file's, and
    the ages computed from them move on their own. `ensure_ids` runs here so
    the settings UI can address a person the moment the family exists, rather
    than rewriting the document on first open.

    **Every invented person and pet is marked `invented: true`.** That mark is
    how the settings home knows what still has to be replaced, and how the
    tick knows not to write a brief about children who do not exist
    (`is_set_up`). Saving the item from the settings form clears it, so the
    mark says "never touched" and nothing else — a family who keeps the name
    Mia for a real Mia has still touched her.
    """
    config = with_defaults({
        "family_name": "Our family",
        "people": [
            {"name": "Mia", "date_of_birth": "2017-03-15",
             "avatar_emoji": "\U0001f996", "avatar_color": "purple",
             "interests": "dinosaurs, drawing, swimming", INVENTED: True},
            {"name": "Theo", "date_of_birth": "2019-06-20",
             "avatar_emoji": "\u26bd", "avatar_color": "blue",
             "interests": "football, lego", INVENTED: True},
        ],
        "pets": [
            {"name": "Biscuit", "type": "dog", "avatar_emoji": "\U0001f415",
             INVENTED: True},
        ],
        "recurring": [
            {"title": "Set the table", "emoji": "\U0001f37d",
             "choices": ["Mia", "Theo"]},
            {"title": "Feed Biscuit", "emoji": "\U0001f9b4",
             "choices": ["Theo", "Mia"]},
        ],
        "special_dates": [
            {"title": "Christmas", "emoji": "\U0001f384", "date": "12/25"},
            {"title": "Summer holidays", "emoji": "\u2600\ufe0f", "date": "07/01"},
        ],
    })
    ensure_ids(config)
    # Storage-layer keys: they say where a self-hoster's generated files go and
    # mean nothing as a jsonb column. `with_defaults` puts them in; a hosted
    # family should not carry two filenames nothing will ever open.
    for key in ("data_file", "content_history_file"):
        config.pop(key, None)
    return config


def ensure_ids(config):
    """Give every list item an id. True if any were added.

    A position is not an identity: delete the first person and everyone below
    renumbers, so an edit form opened a moment earlier now points at somebody
    else. Ids make the settings UI address a person rather than a slot, which
    is also what lets the same routes run over a database row later.

    Deliberately not part of load_config — loading must not rewrite the file,
    and the engine never looks at ids. The settings UI calls this and saves.
    """
    added = False
    for key in LIST_KEYS:
        items = config.get(key) or []
        taken = {item.get("id") for item in items if isinstance(item, dict)}
        for item in items:
            if not isinstance(item, dict) or item.get("id"):
                continue
            _add_id(item, new_id(taken))
            taken.add(item["id"])
            added = True
    return added


def _add_id(item, value):
    """Put the id first in the mapping.

    Appending looks tidier but breaks the file: ruamel hangs the blank line and
    comment that introduce the *next* section off the last item of this one, so
    an appended key lands underneath somebody else's heading. First is safe
    everywhere, and it is where a database would put it anyway.
    """
    insert = getattr(item, "insert", None)  # ruamel's CommentedMap has one
    if callable(insert):
        insert(0, "id", value)
    else:
        item["id"] = value


def find_item(items, item_id):
    """(index, item) for the item with this id, or (None, None)."""
    for index, item in enumerate(items or []):
        if isinstance(item, dict) and item.get("id") == item_id:
            return index, item
    return None, None


def tzinfo_for(config):
    return zone(config.get("timezone") or "UTC")


def today_for(config):
    """Today's date in the family's own timezone, not the server's."""
    return datetime.now(tzinfo_for(config)).date()


def people_names(config):
    return [p.get("name", "") for p in config.get("people", []) if p.get("name")]


def invented_names(config):
    """The people and pets the app invented that nobody has touched yet.

    `starter_config` marks each one, and the settings form drops the mark the
    first time that item is saved — so this is exactly "what is still somebody
    else's household", in the order the dashboard shows it. A config written by
    hand carries no marks and returns nothing, whatever the names in it: a
    real Mia born on the example's date is still theirs.
    """
    return [item["name"]
            for key in ("people", "pets")
            for item in config.get(key) or []
            if isinstance(item, dict) and item.get(INVENTED) and item.get("name")]


def timezone_is_set(config):
    """False while the timezone is still the default.

    The default is UTC, which is nobody's kitchen; a family that really lives
    on it picks its named zone. It is the one setting that changes what the
    dashboard *says* — when today rolls over, when the brief is written, and what
    time an appointment shows — so a dashboard is not set up until it is chosen.
    """
    return (config.get("timezone") or DEFAULTS["timezone"]) != DEFAULTS["timezone"]


def is_set_up(config):
    """Is this a real family's dashboard yet?

    Two things have to be true: the invented household is gone, and the
    timezone has been chosen. Until then a brief would be written about
    children who do not exist, for a day that may not be theirs — so the
    tick holds the first one back (`schedule.brief_due`), the wall says
    "nearly there" (`board.build_view`), and the settings home shows the
    set-up checklist instead of the daily controls (`web/setup.py`).

    **Pure and config-only**, so all three ask the same question of the same
    data. There is no stored "onboarding step" to drift out of line with what
    the config actually holds, and no mode check: a freshly cloned Pi running
    the untouched example file is in the same state as a hosted family five
    seconds old.
    """
    return not invented_names(config) and timezone_is_set(config)


def rename_in_chores(config, old, new):
    """A person renamed in the settings keeps their place in every rotation.

    Chores hold names as plain text, so without this a family who replaced
    the invented Mia by editing her would have a dashboard announcing Mia's turn
    for the rest of time. Edited in place: a flow-style list in config.yaml
    stays a flow-style list.
    """
    for chore in config.get("recurring") or []:
        choices = chore.get("choices") or []
        for index, name in enumerate(choices):
            if name == old:
                choices[index] = new


def drop_from_chores(config, name):
    """A person removed from the settings leaves every rotation too."""
    for chore in config.get("recurring") or []:
        choices = chore.get("choices") or []
        for index in range(len(choices) - 1, -1, -1):
            if choices[index] == name:
                del choices[index]
