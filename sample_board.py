#!/usr/bin/env python3
"""Seed a sample `dashboard_data.json` so a fresh workspace opens on a real board.

`dashboard_data.json` is gitignored, so a new Conductor workspace only gets one
if Files to copy brought it across from the main checkout. Without it the board
shows the first-run screen, which is a poor thing to check a layout change
against — and a payload written before the engine rebuild has none of the keys
`board.build_view` reads, so it renders an empty, permanently stale board.

This writes a plausible board for today, using whatever `config.yaml` is
present. It costs nothing and calls no API. Real data always wins: if a payload
in the current schema is already here, this leaves it alone.
"""

import json
import sys
from datetime import datetime, timedelta

from dinkydash import config as config_module

# Enough to fill today's agenda and leave a fortnight of context behind it, the
# same window a real run fetches.
SAMPLE_EVENTS = [
    (0, "Swimming lesson", "09:30", "Stadtbad"),
    (0, "Lunch at Oma's", "12:30", None),
    (0, "Football training", "16:00", "Sportplatz"),
    (1, "Term starts", None, None),
    (1, "Dentist", "14:15", None),
    (2, "Library books due", None, None),
    (3, "Parents' evening", "19:00", "School hall"),
    (5, "Playdate", "15:00", None),
    (6, "Vet check", "11:00", None),
    (8, "Bank holiday", None, None),
    (9, "Cinema trip", "17:30", None),
    (12, "Grandparents visiting", None, None),
]

HEADLINE = "Swimming, then football — a full day."
NOTE = ("Sample data, so the board has something to show. Run generate.py, or "
        "press “Rewrite now” in settings, for the real thing.")


def is_usable(path):
    """True if a payload is already here and speaks the current schema."""
    try:
        with open(path) as f:
            payload = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    # Pre-rebuild payloads carry `generated_date` and `ai_content` instead, and
    # nothing build_view reads, so they are worse than no payload at all.
    return isinstance(payload, dict) and "generated_for_date" in payload


def build_payload(config, today, tzinfo):
    events = []
    for offset, title, time, location in SAMPLE_EVENTS:
        day = today + timedelta(days=offset)
        if time is None:
            start = datetime(day.year, day.month, day.day, tzinfo=tzinfo)
        else:
            hour, minute = (int(part) for part in time.split(":"))
            start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tzinfo)
        events.append({
            "title": title,
            "start": start.isoformat(),
            "date": day.isoformat(),
            "time": time,
            "all_day": time is None,
            "location": location,
            "calendar": "Sample",
        })

    return {
        "generated_at": datetime.now(tzinfo).isoformat(),
        "generated_for_date": today.isoformat(),
        "family_name": config.get("family_name", ""),
        "timezone": config.get("timezone", "UTC"),
        "headline": HEADLINE,
        "note": NOTE,
        "note_kind": "sample",
        "events": events,
        "model": "sample-data",
        "input_tokens": 0,
        "output_tokens": 0,
    }


def main():
    config = config_module.load_config(config_module.config_path())
    path = config_module.data_path(config)

    if is_usable(path):
        print(f"{path} is already a current payload; leaving it alone.")
        return 0

    today = config_module.today_for(config)
    payload = build_payload(config, today, config_module.tzinfo_for(config))
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Wrote sample board data for {today} to {path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
