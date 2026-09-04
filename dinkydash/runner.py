"""The full daily cycle: fetch calendars, ask Claude, write the payload.

This is the one place that does I/O around the engine, shared by the cron
script and the settings page's "Rewrite now" button.
"""

import json
import logging
import os
import tempfile
from datetime import datetime

from . import config as config_module
from . import history as history_module
from .calendars import fetch_events
from .claude_client import GenerationError
from .generate import generate

log = logging.getLogger(__name__)


def write_payload(payload, path):
    """Write the payload atomically so the board never reads a half-written file."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(path))
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def run(config, today=None, client=None, base=None):
    """Generate today's board and save it. Returns the payload.

    Raises GenerationError if the model call fails — the caller decides what to
    do, and the previous payload is left untouched either way.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise GenerationError(
            "ANTHROPIC_API_KEY is not set. Put it in .env as ANTHROPIC_API_KEY=sk-ant-..."
        )

    today = today or config_module.today_for(config)
    tzinfo = config_module.tzinfo_for(config)

    events, statuses = fetch_events(
        config.get("calendars"), today, tzinfo,
        days_ahead=int(config.get("calendar_days_ahead") or 14),
    )
    failed = [s["label"] for s in statuses if s["ok"] is False]
    if failed:
        log.warning("Calendars that did not answer: %s", ", ".join(failed))

    history_file = config_module.history_path(config, base=base)
    keep = int(config.get("history_days") or 30)
    recent = history_module.recent_notes(history_module.load_history(history_file), keep)

    payload = generate(config, today, events, recent_notes=recent, client=client)
    payload["calendar_statuses"] = statuses

    write_payload(payload, config_module.data_path(config, base=base))
    history_module.record(
        history_file,
        {
            "date": today.isoformat(),
            "headline": payload["headline"],
            "note": payload["note"],
            "note_kind": payload["note_kind"],
        },
        keep=max(keep, 30),
    )
    log.info(
        "Board written for %s (%s tokens in, %s out)",
        today, payload.get("input_tokens"), payload.get("output_tokens"),
    )
    return payload
