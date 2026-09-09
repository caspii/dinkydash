"""The two halves of the daily cycle: fetch the calendars, write the brief.

`refresh_calendars` re-fetches the feeds and costs a few HTTP requests.
`write_brief` asks Claude for the headline and note and costs money. They were
one function only because history put them there; splitting them lets the
calendars run on their own cadence, so an appointment added at 09:00 reaches
the wall the same day (`generate.py --tick`, and `dinkydash.schedule.due`).

`run` is still both, in order, which is what `python generate.py` has always
meant and what the settings page's "Rewrite now" does.

All three take a `store` and read and write only through it, so nothing here
knows whether the board it is replacing is a file on a Pi or a row belonging to
one family among thousands.

**Each half writes only what it owns** — `save_agenda` or `save_brief`, never a
whole payload. That is what makes a refresh landing during the model call
survive rather than being overwritten by the stale keys the brief read minutes
earlier (DIN-28). A fresh agenda under yesterday's headline is exactly the
amber-banner state `board.build_view` already handles.

**`write_brief` takes a budget as well as a store**, and for the same reason it
takes a store: what a call is allowed to cost is the caller's business, not the
engine's (DIN-43). Single mode passes nothing and gets `NoBudget`; cloud mode
passes one backed by Postgres. A refusal arrives as a `GenerationError`, so
every caller's existing keep-last-good path handles it with no new branch.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from . import config as config_module
from .budget import NoBudget
from .calendars import fetch_events, sort_key
from .claude_client import GenerationError
from .generate import generate

log = logging.getLogger(__name__)


def refresh_calendars(config, store, now=None, today=None):
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

    # Read only to find out what a failing feed last gave us. Nothing from this
    # read is written back except the events themselves.
    previous = (store.load_payload(config) or {}).get("events")

    failed = {s["label"] for s in statuses if s["ok"] is False}
    if failed:
        log.warning("Calendars that did not answer: %s", ", ".join(sorted(failed)))
        events = _with_last_known(events, previous, failed,
                                  today, today + timedelta(days=days_ahead))

    agenda = {
        "events": events,
        "calendar_statuses": statuses,
        "calendars_fetched_at": now.astimezone(timezone.utc).isoformat(),
    }
    if not store.save_agenda(config, agenda):
        raise GenerationError("Calendar settings changed during the refresh. Please refresh again.")
    log.info("Calendars refreshed: %d events stored", len(events))
    return agenda


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


def write_brief(config, store, today=None, client=None, budget=None):
    """Ask Claude for today's headline and note, and store them. Costs one call.

    The events come from the stored payload rather than a second fetch, so the
    brief always describes the agenda the board is showing, and a tick that
    owes both does one fetch rather than two.

    Raises GenerationError if the model call fails **or if the budget refuses
    it** — the caller decides what to do, and the previous payload is left
    untouched either way. That sameness is the point: a board that is too
    expensive to rewrite and a board whose rewrite failed should both leave the
    screen on the wall showing yesterday, labelled stale.
    """
    require_api_key()
    budget = budget or NoBudget()
    today = today or config_module.today_for(config)

    stored = store.load_payload(config) or {}

    keep = int(config.get("history_days") or 30)
    recent = store.recent_notes(config, keep)

    # **Charged before the call, not after.** A key that has been revoked fails
    # every time and reports no usage, so counting successes would let a
    # five-minute retry loop run for ever. Raises `OverBudget` if it will not
    # pay for this one, and nothing below has run.
    budget.allow()

    payload = generate(
        budget.generation_config(config), today, stored.get("events") or [],
        recent_notes=recent, client=client,
    )
    budget.record(payload.get("input_tokens"), payload.get("output_tokens"))
    # Only the brief. `stored` was read before a model call that takes seconds,
    # so anything of the agenda's in it is already potentially out of date — a
    # refresh may well have landed in the meantime, and writing this copy back
    # would throw that away while telling the person it had worked.
    store.save_brief(config, payload)
    store.record_note(
        config,
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


def run(config, store, today=None, client=None, budget=None):
    """Both halves: fetch the calendars, then write the brief. Returns the payload.

    The refresh is deliberately outside the budget: fetching calendars costs a
    few HTTP requests to somebody else's server, not money, and a family whose
    board cannot be rewritten today should still have an accurate agenda under
    yesterday's headline.
    """
    require_api_key()  # before the fetch, so a missing key fails in a second
    refresh_calendars(config, store, today=today)
    return write_brief(config, store, today=today, client=client, budget=budget)


def require_api_key():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise GenerationError(
            "ANTHROPIC_API_KEY is not set. Put it in .env as ANTHROPIC_API_KEY=sk-ant-..."
        )
