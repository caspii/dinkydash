"""The two halves of the daily cycle, and the one place that does I/O.

`refresh_calendars` re-fetches the feeds and costs a few HTTP requests.
`write_brief` asks Claude for the headline and note and costs money. They were
one function only because history put them there; splitting them lets the
calendars run on their own cadence, so an appointment added at 09:00 reaches
the wall the same day (`generate.py --tick`, and `dinkydash.schedule.due`).

`run` is still both, in order, which is what `python generate.py` has always
meant and what the settings page's "Rewrite now" does.
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone

from . import config as config_module
from . import history as history_module
from .calendars import fetch_events, sort_key
from .claude_client import GenerationError
from .generate import generate

log = logging.getLogger(__name__)

# What a refresh owns. Everything else in the payload belongs to the brief, and
# a refresh must not touch it: a fresh agenda under yesterday's headline is
# exactly the amber-banner state `board.build_view` already handles.
REFRESH_KEYS = ("events", "calendar_statuses", "calendars_fetched_at")


def read_payload(path):
    """The stored payload, or None when there isn't a usable one."""
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Dashboard data is not readable (%s); treating it as no board yet", exc)
        return None
    return data if isinstance(data, dict) else None


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


def refresh_calendars(config, now=None, base=None, today=None):
    """Re-fetch every enabled feed and store the merged agenda. No model call.

    `now` is when this is happening and becomes the `calendars_fetched_at`
    stamp. `today` is the day the fourteen-day window starts on, and defaults
    to today on the family's clock — they are the same thing except under
    `generate.py --date`, where the window is moved but the stamp is not.
    """
    now = now or datetime.now(timezone.utc)
    tzinfo = config_module.tzinfo_for(config)
    today = today or now.astimezone(tzinfo).date()

    days_ahead = int(config.get("calendar_days_ahead") or 14)
    events, statuses = fetch_events(
        config.get("calendars"), today, tzinfo, days_ahead=days_ahead,
    )

    path = config_module.data_path(config, base=base)
    payload = read_payload(path) or {}

    failed = {s["label"] for s in statuses if s["ok"] is False}
    if failed:
        log.warning("Calendars that did not answer: %s", ", ".join(sorted(failed)))
        events = _with_last_known(events, payload.get("events"), failed,
                                  today, today + timedelta(days=days_ahead))

    payload["events"] = events
    payload["calendar_statuses"] = statuses
    payload["calendars_fetched_at"] = now.astimezone(timezone.utc).isoformat()
    write_payload(payload, path)
    log.info("Calendars refreshed: %d events stored", len(payload["events"]))
    return payload


def _with_last_known(fresh, previous, failed_labels, start, end):
    """Fresh events, plus the last-known events of the feeds that did not answer.

    A missing event is invisible while a stale one is still on the right day —
    the previous fetch reached the same fourteen days ahead — so a feed that
    fails holds its last agenda rather than emptying it. Only that feed does:
    the ones that answered are always fresh, or a single dead URL would freeze
    the whole board for as long as nobody fixed it.

    Events are kept only inside the current window, so a permanently broken feed
    empties out as the days pass instead of accumulating a tail of past events.
    """
    window = (start.isoformat(), end.isoformat())
    seen = {(e.get("calendar"), e.get("title"), e.get("start")) for e in fresh}
    kept = []
    for event in previous or []:
        if event.get("calendar") not in failed_labels:
            continue
        if not window[0] <= str(event.get("date")) <= window[1]:
            continue
        key = (event.get("calendar"), event.get("title"), event.get("start"))
        if key in seen:  # two feeds sharing one label
            continue
        seen.add(key)
        kept.append(event)
    if kept:
        log.info("Kept %d event(s) from the feeds that did not answer", len(kept))
    return sorted(fresh + kept, key=sort_key)


def write_brief(config, today=None, base=None, client=None):
    """Ask Claude for today's headline and note, and store them. Costs one call.

    The events come from the stored payload rather than a second fetch, so the
    brief always describes the agenda the board is showing, and a tick that
    owes both does one fetch rather than two.

    Raises GenerationError if the model call fails — the caller decides what to
    do, and the previous payload is left untouched either way.
    """
    require_api_key()
    today = today or config_module.today_for(config)

    path = config_module.data_path(config, base=base)
    stored = read_payload(path) or {}

    history_file = config_module.history_path(config, base=base)
    keep = int(config.get("history_days") or 30)
    recent = history_module.recent_notes(history_module.load_history(history_file), keep)

    payload = generate(
        config, today, stored.get("events") or [], recent_notes=recent, client=client
    )
    for key in REFRESH_KEYS:
        if key in stored:
            payload[key] = stored[key]

    write_payload(payload, path)
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


def run(config, today=None, client=None, base=None):
    """Both halves: fetch the calendars, then write the brief. Returns the payload."""
    require_api_key()  # before the fetch, so a missing key fails in a second
    refresh_calendars(config, base=base, today=today)
    return write_brief(config, today=today, base=base, client=client)


def require_api_key():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise GenerationError(
            "ANTHROPIC_API_KEY is not set. Put it in .env as ANTHROPIC_API_KEY=sk-ant-..."
        )
