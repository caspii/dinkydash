"""The rolling record of what was written recently.

Fed back into the prompt so the board doesn't tell you the same octopus fact
every fortnight.
"""

import json
import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


def load_history(path):
    """Recent entries, oldest first. Never raises — a missing file just means
    there is nothing to avoid yet."""
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        log.warning("Content history is not a list, ignoring it")
    except FileNotFoundError:
        pass
    except Exception as exc:
        log.warning("Could not read content history: %s", exc)
    return []


def recent_notes(history, days):
    """Just the note text from the last `days` entries."""
    return [entry.get("note", "") for entry in history[-days:] if entry.get("note")]


def record(path, entry, keep=30):
    """Append one entry, keeping the most recent `keep`."""
    history = load_history(path)
    history.append(entry)
    history = history[-keep:]
    path = Path(path)
    try:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            os.replace(tmp, str(path))
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise
    except Exception as exc:
        log.warning("Could not write content history: %s", exc)
