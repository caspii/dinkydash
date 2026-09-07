"""The storage seam: where a family's config, board and history are kept.

The engine takes a config dict and hands back a payload dict. Something has to
keep those somewhere, and today that is three files beside `config.yaml`. In
cloud mode it is rows in Postgres, keyed on a family (PLAN.md decision 10).

So the six operations get a name now, while there is still one implementation:

    load_config()                save_config(config)
    load_payload(config)         save_payload(config, payload)
    recent_notes(config, days)   record_note(config, entry, keep)

The runner, the board route and the settings routes take a store and never
learn which one they were given. `PostgresStore` is then a second class rather
than a fork of every caller.

The payload and history calls are handed the config because `FileStore` needs
two keys out of it — `data_file` and `content_history_file` — to know where to
write. Those are storage-layer keys: they mean nothing in cloud mode, and this
is the only module that reads them.

This module and `config.py` are the only places under `dinkydash/` that touch
a file. Everything else stays pure.
"""

import json
import logging
import os
import tempfile
from pathlib import Path

from . import config as config_module
from . import history as history_module

log = logging.getLogger(__name__)


class FileStore:
    """One family, as files beside its own `config.yaml`.

    A relative `data_file` or `content_history_file` resolves against the
    config's own directory, so `generate.py --config /tmp/scratch.yaml` keeps
    its generated files with it rather than in whatever directory it was run
    from.
    """

    def __init__(self, config_path=None):
        path = Path(config_path) if config_path else config_module.config_path()
        self.config_path = path.expanduser()
        self.base = self.config_path.parent

    # -- the config ---------------------------------------------------------

    def load_config(self):
        """The config as a plain dict, defaults filled in and old shapes migrated."""
        return config_module.load_config(self.config_path)

    def save_config(self, config):
        """Write it back, comments and key order intact."""
        config_module.save_config(config, self.config_path)

    # -- the board ----------------------------------------------------------

    def load_payload(self, config):
        """The last generated board, or None when there is not a usable one."""
        payload = _read_json(self._data_path(config), "the stored board")
        return payload if isinstance(payload, dict) else None

    def save_payload(self, config, payload):
        """Write the board atomically, so nothing ever reads half a file."""
        _write_json(self._data_path(config), payload)

    # -- what was written recently ------------------------------------------

    def recent_notes(self, config, days):
        """The note text from the last `days` entries, oldest first."""
        return history_module.recent_notes(self._history(config), days)

    def record_note(self, config, entry, keep=30):
        """Add one entry to the history, keeping the most recent `keep`.

        Never raises. A history that cannot be written costs a repeated octopus
        fact in a fortnight; it is not worth losing a written board over.
        """
        try:
            _write_json(self._history_path(config),
                        history_module.appended(self._history(config), entry, keep))
        except Exception as exc:
            log.warning("Could not write the note history: %s", exc)

    def _history(self, config):
        history = _read_json(self._history_path(config), "the note history")
        if history is None:
            return []
        if not isinstance(history, list):
            log.warning("The note history is not a list; ignoring it")
            return []
        return history

    # -- where the files are ------------------------------------------------

    def _data_path(self, config):
        return self._resolve(config.get("data_file") or config_module.DEFAULTS["data_file"])

    def _history_path(self, config):
        return self._resolve(config.get("content_history_file")
                             or config_module.DEFAULTS["content_history_file"])

    def _resolve(self, value):
        path = Path(value).expanduser()
        return path if path.is_absolute() else self.base / path


def _read_json(path, what):
    """Parsed JSON, or None when there is nothing usable there.

    Never raises. A missing file means this family has not got one yet, and an
    unreadable one must not take the board down with it — the caller carries on
    as though it were absent, and the next write replaces it.
    """
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        log.warning("Could not read %s (%s); carrying on as if it were not there", what, exc)
        return None


def _write_json(path, data):
    """Write via a temporary file and rename, so a reader sees old or new, never half."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
