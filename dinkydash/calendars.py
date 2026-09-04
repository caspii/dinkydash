"""iCal fetching, parsing and merging.

Several feeds go in (one per parent, plus a school calendar or two) and one
chronologically-ordered agenda comes out. Events keep their real start time all
the way through — the old code formatted them to a string too early and then
sorted those strings, which ordered the day alphabetically by weekday name.
"""

import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar
from recurring_ical_events import of as recurring_events_of

log = logging.getLogger(__name__)

DEFAULT_DAYS_AHEAD = 14
DEFAULT_TIMEOUT = 30


class FeedError(Exception):
    """A feed could not be fetched or parsed."""


def _localise(value, tzinfo):
    """Return an aware datetime in `tzinfo` for an iCal DTSTART value."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # A floating time means "whatever the local clock says", which for a
            # family board is the family's own timezone.
            return value.replace(tzinfo=tzinfo)
        return value.astimezone(tzinfo)
    # A bare date is an all-day event; anchor it to midnight for ordering.
    return datetime.combine(value, time.min, tzinfo=tzinfo)


def parse_feed(ical_text, start, end, tzinfo, label=None):
    """Parse iCal text into event dicts between `start` and `end` (dates)."""
    try:
        cal = Calendar.from_ical(ical_text)
    except Exception as exc:
        raise FeedError(f"could not parse iCal data: {exc}") from exc

    events = []
    for component in recurring_events_of(cal).between(start, end + timedelta(days=1)):
        dtstart = component.get("DTSTART")
        if dtstart is None:
            continue
        raw = dtstart.dt
        all_day = not isinstance(raw, datetime)
        starts_at = _localise(raw, tzinfo)

        events.append({
            "title": str(component.get("SUMMARY", "Untitled")).strip() or "Untitled",
            "start": starts_at.isoformat(),
            "date": starts_at.date().isoformat(),
            "time": None if all_day else starts_at.strftime("%H:%M"),
            "all_day": all_day,
            "location": str(component.get("LOCATION", "")).strip() or None,
            "calendar": label,
        })
    return events


def fetch_feed(url, start, end, tzinfo, label=None, timeout=DEFAULT_TIMEOUT):
    """Fetch one iCal URL and return its events. Raises FeedError."""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except Exception as exc:
        raise FeedError(f"could not fetch the calendar: {exc}") from exc
    return parse_feed(response.text, start, end, tzinfo, label=label)


def sort_key(event):
    """Chronological, with all-day events leading their day."""
    return (event["date"], 0 if event["all_day"] else 1, event["start"])


def fetch_events(calendars, today, tzinfo, days_ahead=DEFAULT_DAYS_AHEAD,
                 timeout=DEFAULT_TIMEOUT):
    """Fetch every enabled feed and merge into one ordered agenda.

    One broken feed must not empty the board, so a failing feed is logged and
    skipped. The second return value reports per-feed status so the settings
    page can show which one needs attention.
    """
    end = today + timedelta(days=days_ahead)
    merged = []
    statuses = []

    for entry in calendars or []:
        label = entry.get("label") or "Calendar"
        if not entry.get("enabled", True):
            statuses.append({"label": label, "ok": None, "detail": "paused", "count": 0})
            continue
        url = entry.get("url", "")
        if not url:
            statuses.append({"label": label, "ok": False, "detail": "no URL set", "count": 0})
            continue
        try:
            events = fetch_feed(url, today, end, tzinfo, label=label, timeout=timeout)
        except FeedError as exc:
            log.warning("Calendar %r failed: %s", label, exc)
            statuses.append({"label": label, "ok": False, "detail": str(exc), "count": 0})
            continue
        merged.extend(events)
        statuses.append({"label": label, "ok": True, "detail": "", "count": len(events)})
        log.info("Calendar %r: %d events", label, len(events))

    merged.sort(key=sort_key)
    return merged, statuses


def events_on(events, day):
    """The subset of `events` that fall on `day`, in order."""
    wanted = day.isoformat()
    return [e for e in events if e.get("date") == wanted]


def describe_feed(url, tzinfo, today=None, days_ahead=DEFAULT_DAYS_AHEAD,
                  timeout=DEFAULT_TIMEOUT):
    """Check a pasted URL and describe what came back.

    Used by the settings UI so pasting a link answers with a real event count
    and the next thing in it, rather than a silent success.
    """
    today = today or date.today()
    events = fetch_feed(url, today, today + timedelta(days=days_ahead), tzinfo)
    events.sort(key=sort_key)
    upcoming = [e for e in events if e["date"] >= today.isoformat()]
    return {
        "count": len(events),
        "next": upcoming[0] if upcoming else None,
        "days_ahead": days_ahead,
    }


def zone(name):
    """ZoneInfo for a configured timezone name, falling back to UTC."""
    try:
        return ZoneInfo(name)
    except Exception:
        log.warning("Unknown timezone %r, falling back to UTC", name)
        return ZoneInfo("UTC")
