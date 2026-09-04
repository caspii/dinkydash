"""Reading and writing config.yaml.

The settings UI writes this file back, so loads and saves go through ruamel's
round-trip mode: your comments and key order survive an edit made from a phone.
"""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

from ruamel.yaml import YAML

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
    "data_file": "dashboard_data.json",
    "content_history_file": "content_history.json",
}

THEMES = ("light", "dark")

# Avatar colours the board and the settings UI both understand. Names rather
# than hex so a theme change doesn't strand a colour nobody can read.
AVATAR_COLORS = ("purple", "blue", "green", "pink", "orange", "amber", "teal")


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


def tzinfo_for(config):
    return zone(config.get("timezone") or "UTC")


def today_for(config):
    """Today's date in the family's own timezone, not the server's."""
    return datetime.now(tzinfo_for(config)).date()


def people_names(config):
    return [p.get("name", "") for p in config.get("people", []) if p.get("name")]


def data_path(config, base=None):
    return _resolve(config.get("data_file", DEFAULTS["data_file"]), base)


def history_path(config, base=None):
    return _resolve(config.get("content_history_file", DEFAULTS["content_history_file"]), base)


def _resolve(value, base):
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    base = Path(base) if base else config_path().parent
    return base / path
