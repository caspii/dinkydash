"""The orchestrator.

    generate(config, today, events, recent_notes) -> payload dict

No config file is read here, no clock is consulted, nothing is written to disk:
the caller injects the date and owns the I/O. That is what lets a Pi cron job
and (later) a multi-tenant scheduler share one code path.

The payload deliberately holds only what cannot be recomputed — the model's
words and the fetched calendar window. Ages, countdowns and whose turn it is
are pure functions of the config and the date, so the board recomputes them at
render time and stays correct on a day when generation failed.
"""

import logging
from datetime import datetime

from .claude_client import call_claude
from .context import build_countdowns, compute_chore_assignments
from .calendars import events_on
from .prompt import build_user_prompt, choose_note_kind

log = logging.getLogger(__name__)

SOON_DAYS = 4


def generate(config, today, events, recent_notes=(), client=None, rng=None,
             note_kind=None):
    """Produce today's payload. Raises GenerationError if the model call fails."""
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

    kind = note_kind or choose_note_kind(config, rng=rng)
    user_prompt = build_user_prompt(
        config, today, events_today, events_soon, chores, countdowns,
        recent_notes, kind, rng=rng,
    )
    log.info("Prompt built (%d characters, note kind=%s)", len(user_prompt), kind)

    ai = call_claude(user_prompt, config, client=client)

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "generated_for_date": today.isoformat(),
        "family_name": config.get("family_name", ""),
        "timezone": config.get("timezone", "UTC"),
        "headline": ai["headline"],
        "note": ai["note"],
        "note_kind": kind,
        "events": events,
        "model": ai["model"],
        "input_tokens": ai["input_tokens"],
        "output_tokens": ai["output_tokens"],
    }
