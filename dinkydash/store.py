"""The storage seam: where a family's config, board and history are kept.

The engine takes a config dict and hands back a payload dict. Something has to
keep those somewhere, and today that is three files beside `config.yaml`. In
cloud mode it is rows in Postgres, keyed on a family (PLAN.md decision 10).

So the six operations get a name now, while there is still one implementation:

    load_config()                save_config(config)
    load_payload(config)         save_agenda(config, agenda)
                                 save_brief(config, brief)
    recent_notes(config, days)   record_note(config, entry, keep)

The runner, the board route and the settings routes take a store and never
learn which one they were given. `PostgresStore` is then a second class rather
than a fork of every caller.

**The board is read whole and written in halves**, and that is the shape rather
than an accident. A refresh owns the agenda; the daily brief owns the words.
They run on different clocks, and the brief's write is separated from its read
by a slow model call — so a single `save_payload` meant a refresh that landed
during that call was overwritten by stale keys, silently, while the button that
triggered it said it had worked (DIN-28). Two operations that each write only
what they own makes that impossible rather than merely unlikely; in Postgres
they are already two tables, so it is also the more honest mapping.

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
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl  # POSIX only
except ImportError:  # pragma: no cover - Windows has no flock
    fcntl = None

from . import config as config_module
from . import history as history_module

log = logging.getLogger(__name__)

# What a calendar refresh owns, and the only keys `save_agenda` will write.
# Everything else in the payload belongs to the brief. Named here rather than in
# the runner because it is the storage contract's own vocabulary: both
# implementations enforce it, and no caller can talk its way past it.
AGENDA_KEYS = ("events", "calendar_statuses", "calendars_fetched_at")


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

    def save_agenda(self, config, agenda):
        """Replace the fetched window, leaving the brief exactly as it was."""
        self._replace(config, _is_agenda_key,
                      {k: agenda[k] for k in AGENDA_KEYS if k in agenda})

    def save_brief(self, config, brief):
        """Replace the model's words, leaving the fetched window alone.

        Agenda keys are dropped rather than trusted, so a caller handing over a
        whole payload cannot resurrect a stale agenda through this door.
        """
        self._replace(config, lambda key: not _is_agenda_key(key),
                      {k: v for k, v in brief.items() if not _is_agenda_key(k)})

    def _replace(self, config, owns, updates):
        """Swap out everything this half owns, inside one lock.

        **Replace, not merge.** A key the caller has stopped sending has to
        disappear, because that is what `PostgresStore` does — it writes whole
        rows, so an omitted `model` or token count comes back as None. Merging
        instead would leave a stale value behind on a Pi and not in the cloud,
        which is exactly the sort of quiet divergence the storage seam exists to
        prevent.

        The lock covers a read and a write a microsecond apart, never a model
        call, so nothing waits on it in practice. Without it two processes on
        one Pi could still interleave — the same bug the split removes, only
        very much narrower. Cloud mode needs no equivalent: there each half is
        a row and each write is one statement.
        """
        path = self._data_path(config)
        with _locked(path.parent):
            stored = _read_json(path, "the stored board")
            if not isinstance(stored, dict):
                stored = {}
            payload = {k: v for k, v in stored.items() if not owns(k)}
            payload.update(updates)
            _write_json(path, payload)

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


def _is_agenda_key(key):
    return key in AGENDA_KEYS


@contextmanager
def _locked(directory):
    """An exclusive lock on the directory, for one read and one write.

    **The directory rather than a lock file beside the data**, and that is the
    point: a sidecar would have to be kept out of `deploy_to_pi.sh`'s
    `rsync --delete`, and if it ever were not, a deploy landing mid-write would
    unlink the inode a running tick still holds. The next writer would then
    create a fresh file, take a lock on a different inode, and serialise against
    nobody — silently. A directory's inode survives all of that, and there is no
    file to remember to exclude.

    `flock` is per-machine, which is all single mode needs: the web process and
    the tick are on the same Pi. It is deliberately not the answer for cloud
    mode, where `web` and `worker` are separate containers — there the split
    into two rows is what makes concurrent writes safe.
    """
    if fcntl is None:  # Windows; the board runs on Linux and macOS
        yield
        return
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        # No directory to lock means the write is about to fail anyway, and it
        # will say why far more clearly than a lock error would.
        yield
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


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
