"""What is owed right now: a calendar refresh, a brief, both, or nothing.

Pure — no clock, no file, no network. The caller passes `now` as an aware
datetime and gets back a dict of two booleans, so the same function serves a
Pi's cron tick and (later) a worker loop walking every family.

The two cadences differ because their costs do. Re-fetching the calendars is a
few HTTP requests and happens every `refresh_minutes`, which is what puts an
appointment added at 09:00 onto the wall the same day. The brief is an API
call and happens once a day, after `brief_time` on the family's own clock —
**except the first one, which is owed the moment there is a family to write it
for** (DIN-45). A *set-up* family: while the household is still the invented
starter or the timezone has not been chosen, there is nothing true to write
and no right day to write it for, so the first brief waits for
`config.is_set_up` rather than for the clock.

A brief that fails is simply due again on the next tick. That is the retry.
"""

import logging
from datetime import datetime, time, timedelta, timezone

from .config import is_set_up, tzinfo_for

log = logging.getLogger(__name__)

DEFAULT_REFRESH_MINUTES = 60
DEFAULT_BRIEF_TIME = "06:00"

# Below a minute the tick interval is the real limit anyway, and zero would
# mean "fetch on every tick, forever".
MIN_REFRESH_MINUTES = 1


def due(config, payload, now):
    """`{"refresh": bool, "brief": bool}` for this moment.

    `now` must be an aware datetime; the caller owns the clock.
    """
    payload = payload or {}
    return {
        "refresh": refresh_due(config, payload, now),
        "brief": brief_due(config, payload, now),
    }


def refresh_due(config, payload, now):
    """True when the stored agenda is older than `refresh_minutes`."""
    fetched = parse_stamp(payload.get("calendars_fetched_at"))
    if fetched is None:
        return True
    if fetched > now:
        # A stamp from the future means the clock moved, not that the fetch is
        # fresh. Fetching is free, so believe the clock rather than the file.
        return True
    return now - fetched >= refresh_interval(config)


def brief_due(config, payload, now):
    """Owe the first brief as soon as the family is set up; later ones after brief_time.

    A calendar-only payload has no generated_for_date. Failed first briefs stay
    due on each tick; cloud callers remain subject to the spend breaker.

    **The first brief waits for set-up, not for the morning.** A hosted family
    starts with an invented household and no timezone, and a Pi copying the
    example file starts the same way. Writing a brief then would spend a call
    on somebody else's children, put that line into the family's history, and
    hang it on the wall as the first thing they see. The moment the household
    is theirs and the clock is theirs, it is owed at any hour, as before.
    """
    if not payload.get("generated_for_date"):
        return is_set_up(config)
    local = now.astimezone(tzinfo_for(config))
    if payload["generated_for_date"] == local.date().isoformat():
        return False
    return local.time() >= brief_time(config)


def refresh_interval(config):
    """`refresh_minutes` as a timedelta, falling back to the default."""
    raw = config.get("refresh_minutes")
    try:
        minutes = int(raw) if raw is not None else DEFAULT_REFRESH_MINUTES
    except (TypeError, ValueError):
        log.warning("refresh_minutes is not a number (%r); using %d", raw, DEFAULT_REFRESH_MINUTES)
        minutes = DEFAULT_REFRESH_MINUTES
    return timedelta(minutes=max(minutes, MIN_REFRESH_MINUTES))


def brief_time(config):
    """`brief_time` as a `time` on the family's clock, falling back to the default."""
    raw = config.get("brief_time")
    if raw is None:
        return time.fromisoformat(DEFAULT_BRIEF_TIME)
    try:
        return time.fromisoformat(str(raw).strip())
    except ValueError:
        log.warning("brief_time is not a time (%r); using %s", raw, DEFAULT_BRIEF_TIME)
        return time.fromisoformat(DEFAULT_BRIEF_TIME)


def parse_stamp(value):
    """A payload timestamp as an aware datetime, or None if there isn't one.

    Stamps are written in UTC. A naive one comes from an older payload, and is
    read as UTC rather than as the server's clock — which on a Pi is often not
    the family's clock at all.
    """
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        log.warning("Unreadable timestamp in the payload (%r); treating it as absent", value)
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
