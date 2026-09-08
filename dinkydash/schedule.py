"""What is owed right now: a calendar refresh, a brief, both, or nothing.

Pure — no clock, no file, no network. The caller passes `now` as an aware
datetime and gets back a dict of two booleans, so the same function serves a
Pi's cron tick and (later) a worker loop walking every family.

The two cadences differ because their costs do. Re-fetching the calendars is a
few HTTP requests and happens every `refresh_minutes`, which is what puts an
appointment added at 09:00 onto the wall the same day. The brief is an API
call and happens once a day, after `brief_time` on the family's own clock —
**except the first one, which is owed the moment there is a family to write it
for** (DIN-45).

A brief that fails is simply due again on the next tick. That is the retry.
"""

import logging
from datetime import datetime, time, timedelta, timezone

from .config import tzinfo_for

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
    """True when today has no brief yet and the family's clock has passed `brief_time`.

    **The first brief does not wait for the morning** (DIN-45). `brief_time`
    decides when to replace yesterday's line, and there is nothing to replace
    before the first one: a family with no brief at all has the waiting screen
    on the wall, which is not a board at any hour. Somebody who signs up at
    03:00 would otherwise look at it until 06:00, and that is the whole of
    their first impression of the product.

    **The signal is exact, and it is the same one in both stores.**
    `save_agenda` writes only the agenda keys and `PostgresStore.load_payload`
    adds `generated_for_date` only when a successful generation exists, so a
    payload without that key is a family that has never had a brief rather
    than one whose calendars have merely been fetched. It needs no mode check
    and no new column: a freshly cloned Pi is in the same state, and gets the
    same answer from its first `generate.py --tick`.

    A first brief that keeps *failing* is therefore retried on every tick,
    around the clock rather than from `brief_time` onwards. The bound is
    unchanged and is the per-family spend cap, which a five-minute loop trips
    within an hour (`budget.FAMILY_CALLS_A_DAY`).
    """
    if not payload.get("generated_for_date"):
        return True
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
