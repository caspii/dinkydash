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

from .calendars import zone

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

# Avatar colours the board and the settings UI both understand. Names rather
# than hex so a theme change doesn't strand a colour nobody can read.
AVATAR_COLORS = ("purple", "blue", "green", "pink", "orange", "amber", "teal")

# The lists the settings UI edits. Every item in them carries a stable `id`.
LIST_KEYS = ("people", "pets", "recurring", "special_dates", "calendars")

# Ids are short and typed by nobody, but they end up in URLs and get read aloud
# when something goes wrong, so leave out the characters that look like others.
ID_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
ID_LENGTH = 8


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

    # A single calendar_url becomes the first entry in `calendars`.
    legacy_url = config.pop("calendar_url", None)
    if legacy_url and not config["calendars"]:
        config["calendars"] = [{"label": "Calendar", "url": legacy_url, "enabled": True}]
        log.info("Migrated calendar_url into calendars[]")

    # calendar_filter_emails required every listed address to appear as an
    # ATTENDEE. Most personal Google Calendar events carry no ATTENDEE at all,
    # so it silently matched nothing. Separate feeds replace it.
    if config.pop("calendar_filter_emails", None):
        log.warning(
            "Ignoring calendar_filter_emails — it silently hid every event on "
            "calendars without ATTENDEE properties. Add one feed per person instead."
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
