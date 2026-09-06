"""Turning config + payload into what the board template renders.

The split that matters: `headline` and `note` come from the payload (the model
wrote them, they can go stale), while the agenda, whose-turn and countdowns are
recomputed here from the config and today's date. So when a morning's
generation fails, the times and turns on the wall are still today's — only the
written line is yesterday's, and it says so.
"""

from datetime import datetime, timedelta

from .calendars import events_on
from .context import build_countdowns, compute_chore_assignments

# The agenda's row budget, not just today's cap. Today fills it first and
# tomorrow tops up whatever is left, so a quiet day stops leaving the column
# half empty while a busy one is never made to shrink to fit.
MAX_EVENTS = 5
# Tomorrow stays a footnote even when today is empty, so the agenda always
# reads as today's first.
MAX_TOMORROW = 3
MAX_COUNTDOWNS = 3


def computed_headline(events):
    """A headline derived from the day itself, for when the model's is stale."""
    if not events:
        return "Nothing booked in today."
    timed = [e for e in events if not e["all_day"]]
    count = len(events)
    noun = "thing" if count == 1 else "things"
    if timed:
        return f"{count} {noun} on today, starting at {timed[0]['time']}."
    return f"{count} {noun} on today."


def build_view(config, payload, today):
    """The complete view model for templates/board.html."""
    theme = config.get("theme", "light")
    theme = theme if theme in ("light", "dark") else "light"

    chores = compute_chore_assignments(config.get("recurring"), today)
    countdowns = build_countdowns(
        config.get("people"), config.get("special_dates"), today,
        limit=MAX_COUNTDOWNS,
    )

    view = {
        "family_name": config.get("family_name", ""),
        "theme": theme,
        "date_display": today.strftime("%A, %-d %B"),
        "chores": chores,
        "countdowns": countdowns,
        "events": [],
        "tomorrow": [],
        "headline": "",
        "note": "",
        "stale": False,
        "state": "waiting",
    }

    if not payload:
        return view

    fetched = payload.get("events") or []
    events = events_on(fetched, today)[:MAX_EVENTS]
    view["events"] = events
    # The fetch reaches 14 days ahead, so tomorrow is in the payload even when
    # it is a day old. Slots are what today did not use, which is why a busy
    # day silently drops tomorrow rather than overflowing the panel.
    slots = min(MAX_TOMORROW, MAX_EVENTS - len(events))
    view["tomorrow"] = events_on(fetched, today + timedelta(days=1))[:slots] if slots else []

    stale = payload.get("generated_for_date") != today.isoformat()
    view["stale"] = stale
    view["state"] = "stale" if stale else "ready"
    view["note"] = payload.get("note", "")
    # A day-old headline can be actively wrong ("Ines starts nursery today"), so
    # it gives way to one derived from the real day. The note is harmless when
    # stale, so it stays — labelled.
    view["headline"] = computed_headline(events) if stale else payload.get("headline", "")

    if stale:
        try:
            generated = datetime.fromisoformat(payload["generated_for_date"]).date()
            view["stale_days"] = (today - generated).days
        except (KeyError, ValueError):
            view["stale_days"] = None

    return view
