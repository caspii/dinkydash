"""The storage seam: where a family's config, dashboard and history are kept.

FileStore keeps config.yaml and two JSON files; PostgresStore keeps rows keyed
on a family. The config dict is the contract, and both expose seven operations:

    load_config()                save_config(config, invalidate_calendars=())
    load_payload(config)         save_agenda(config, agenda)
                                 save_brief(config, brief)
    recent_notes(config, days)   record_note(config, entry, keep)

The runner, the dashboard route and the settings routes take a store and never
learn which one they were given.

**The dashboard is read whole and written in halves**, and that is the shape rather
than an accident. A refresh owns the agenda; the daily brief owns the words.
They run on different clocks, and the brief's write is separated from its read
by a slow model call — so a single `save_payload` meant a refresh that landed
during that call was overwritten by stale keys, silently, while the button that
triggered it said it had worked (DIN-28). Two operations that each write only
what they own makes that impossible rather than merely unlikely; in Postgres
they are already two tables, so it is also the more honest mapping.

Settings saves clear affected calendars under the same lock as agenda writes.
`save_agenda` returns False if the saved calendar settings no longer match the
fetch; the runner then stops before generating a brief from obsolete results.

The payload and history calls are handed the config because `FileStore` needs
two keys out of it — `data_file` and `content_history_file` — to know where to
write. Those are storage-layer keys: they mean nothing in cloud mode, and this
is the only module that reads them.

This module and `config.py` are the only places under `dinkydash/` that touch
a file.
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
from .calendars import feed_label

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
        with _locked(self.base):
            return config_module.load_config(self.config_path)

    def save_config(self, config, *, invalidate_calendars=()):
        """Save settings and invalidate changed calendars under the same lock."""
        with _locked(self.base):
            try:
                previous = config_module.load_config(self.config_path)
            except FileNotFoundError:
                previous = {}
            agenda = invalidated_agenda(previous, config, self.load_payload(previous),
                                        invalidate_calendars)
            if agenda is not None:
                # Clear first: even a failed config write must not leave a new
                # privacy setting visible beside events fetched before it.
                self._replace(previous, _is_agenda_key, agenda)
            config_module.save_config(config, self.config_path)

    # -- the dashboard ----------------------------------------------------------

    def load_payload(self, config):
        """The last generated dashboard, or None when there is not a usable one."""
        payload = _read_json(self._data_path(config), "the stored dashboard")
        return payload if isinstance(payload, dict) else None

    def save_agenda(self, config, agenda):
        """Publish only if the saved calendar settings still match the fetch."""
        with _locked(self.base):
            current = config_module.load_config(self.config_path)
            if calendar_config(current) != calendar_config(config):
                return False
            self._replace(config, _is_agenda_key,
                          {k: agenda[k] for k in AGENDA_KEYS if k in agenda})
            return True

    def save_brief(self, config, brief):
        """Replace the model's words, leaving the fetched window alone.

        Agenda keys are dropped rather than trusted, so a caller handing over a
        whole payload cannot resurrect a stale agenda through this door.
        """
        with _locked(self.base):
            self._replace(config, lambda key: not _is_agenda_key(key),
                          {k: v for k, v in brief.items() if not _is_agenda_key(k)})

    def _replace(self, config, owns, updates):
        """Replace this half's fields. The caller holds the config-directory lock."""
        path = self._data_path(config)
        stored = _read_json(path, "the stored dashboard")
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
        fact in a fortnight; it is not worth losing a written dashboard over.
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


def calendar_config(config):
    """Fetch inputs, grouped by the label carried by stored events.

    Ignore item IDs so backfilling them does not invalidate a working agenda.
    Keep duplicate labels together: changing either source invalidates that label.
    """
    feeds = {}
    for entry in config.get("calendars") or []:
        if isinstance(entry, dict):
            feeds.setdefault(feed_label(entry), []).append(
                {key: value for key, value in entry.items() if key != "id"})
    return (config.get("timezone") or config_module.DEFAULTS["timezone"],
            int(config.get("calendar_days_ahead") or 14), feeds)


def invalidated_agenda(previous, current, payload, labels=()):
    """Drop affected events and the fetch stamp, or return None for no change."""
    before, after = calendar_config(previous), calendar_config(current)
    if payload is None or (before == after and not labels):
        return None
    changed = set(labels) | {label for label in before[2].keys() | after[2].keys()
                            if before[2].get(label) != after[2].get(label)}
    return {key: [entry for entry in payload.get(key) or []
                  if before[:2] == after[:2] and entry.get(label_key) not in changed]
            for key, label_key in (("events", "calendar"), ("calendar_statuses", "label"))}


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

    Lock the config directory for settings and payload writes, including when
    `data_file` points elsewhere. No network call runs under this lock. Cloud
    mode coordinates config and agenda writes with a family-row lock instead.
    """
    if fcntl is None:  # Windows; the dashboard runs on Linux and macOS
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
    unreadable one must not take the dashboard down with it — the caller carries on
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
