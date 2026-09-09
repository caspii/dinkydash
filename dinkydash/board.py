"""Turning config + payload into what the board template renders.

The split that matters: `headline` and `note` come from the payload (the model
wrote them, they can go stale), while the agenda, whose-turn and countdowns are
recomputed here from the config and today's date. So when a morning's
generation fails, the times and turns on the wall are still today's — only the
written line is yesterday's, and it says so.
"""

from datetime import date, datetime, timedelta

from .calendars import events_on
from .context import build_countdowns, compute_chore_assignments
from .schedule import refresh_interval

# The agenda's row budget, not just today's cap. Today fills it first and
# tomorrow tops up whatever is left, so a quiet day stops leaving the column
# half empty while a busy one is never made to shrink to fit.
MAX_EVENTS = 5
# Tomorrow stays a footnote even when today is empty, so the agenda always
# reads as today's first.
MAX_TOMORROW = 3
MAX_COUNTDOWNS = 3

# Nothing pushes to the board, so it reloads itself on a timer. Five minutes is
# the ceiling — it is a panel on a wall, not a page anyone is watching — and
# reloading faster than the calendars are fetched only shows the same thing
# again, so a shorter `refresh_minutes` is the only thing that lowers it.
MAX_RELOAD_SECONDS = 300
# Before the first run there is nothing to show, so ask more often: the screen
# then fills itself in a minute after the board is written rather than five.
WAITING_RELOAD_SECONDS = 60


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


def reload_seconds(config):
    """How long the board waits before rendering itself again.

    Config-derived, so it is computed here rather than written into the
    template: a family that fetches every 15 minutes still reloads every 5, and
    only an interval shorter than that pulls it down.
    """
    return min(MAX_RELOAD_SECONDS, int(refresh_interval(config).total_seconds()))


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
        "reload_seconds": WAITING_RELOAD_SECONDS,
    }

    if not payload:
        return view

    view["reload_seconds"] = reload_seconds(config)

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


def build_lapsed_view(config, payload, show_last_board):
    """Hold the last brief's date and computed turns, then show only a message.

    Read existing data rather than retaining another copy of calendar details.
    Explicit settings edits and calendar privacy invalidation still take effect.
    """
    if show_last_board:
        try:
            saved_day = date.fromisoformat((payload or {}).get("generated_for_date", ""))
        except (TypeError, ValueError):
            pass  # No successful brief: there is no board to preserve.
        else:
            view = build_view(config, payload, saved_day)
            view["state"] = "frozen"
            return view
    return {
        "state": "ended", "family_name": "", "reload_seconds": MAX_RELOAD_SECONDS,
        "theme": "dark" if config.get("theme") == "dark" else "light",
    }
