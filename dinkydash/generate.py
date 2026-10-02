"""The orchestrator.

    generate(config, today, events) -> payload dict

No config file is read here, no clock is consulted, nothing is written to disk:
the caller injects the date and owns the I/O. That is what lets a Pi cron job
and (later) a multi-tenant scheduler share one code path.

The payload deliberately holds only what cannot be recomputed — the model's
words and the fetched calendar window. Ages, countdowns and whose turn it is
are pure functions of the config and the date, so the dashboard recomputes them at
render time and stays correct on a day when generation failed.
"""

import logging
from datetime import datetime, timezone

from .claude_client import call_claude
from .context import build_countdowns, compute_chore_assignments
from .calendars import events_on
from .prompt import build_user_prompt

log = logging.getLogger(__name__)

SOON_DAYS = 4


def generate(config, today, events, client=None):
    """Produce today's payload. Raises GenerationError if the model call fails.

    The model is asked for a headline only. `note` and `note_kind` are still
    written, empty, so a stored brief keeps the shape an older file has.
    """
    events = events or []
    events_today = events_on(events, today)
    horizon = today.toordinal() + SOON_DAYS
    events_soon = [
        e for e in events
        if today.toordinal() < datetime.fromisoformat(e["start"]).date().toordinal() <= horizon
    ]

    chores = compute_chore_assignments(config.get("recurring"), today)
    countdowns = build_countdowns(
        config.get("people"), config.get("special_dates"), today
    )

    user_prompt = build_user_prompt(
        config, today, events_today, events_soon, chores, countdowns,
    )
    log.info("Prompt built (%d characters)", len(user_prompt))

    ai = call_claude(user_prompt, config, client=client)

    return {
        # UTC, not the server's clock: the Pi is often not set to the family's
        # timezone, and hosted the server is nowhere near them. Rendered local.
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_for_date": today.isoformat(),
        "family_name": config.get("family_name", ""),
        "timezone": config.get("timezone", "UTC"),
        "headline": ai["headline"],
        # The brief's shape still has these keys, so a stored dashboard and an
        # export keep reading. Nothing new is written into them.
        "note": "",
        "note_kind": "",
        "events": events,
        "model": ai["model"],
        "input_tokens": ai["input_tokens"],
        "output_tokens": ai["output_tokens"],
    }
