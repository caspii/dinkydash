"""Calendar parsing, ordering and timezone handling.

The ordering tests are the point of this file: the previous implementation
sorted events by their formatted string, so "Friday, August 15" came before
"Monday, August 11" and today's school run could land after next Tuesday.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from dinkydash.calendars import (FeedError, events_on, fetch_events, parse_feed,
                                 sort_key, zone)

BERLIN = ZoneInfo("Europe/Berlin")


def ical(*events):
    body = "".join(events)
    return f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n{body}END:VCALENDAR\r\n"


def timed(uid, start, summary, tz="Europe/Berlin", location=None):
    where = f"LOCATION:{location}\r\n" if location else ""
    return (f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART;TZID={tz}:{start}\r\n"
            f"SUMMARY:{summary}\r\n{where}END:VEVENT\r\n")


def all_day(uid, day, summary):
    return (f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART;VALUE=DATE:{day}\r\n"
            f"SUMMARY:{summary}\r\nEND:VEVENT\r\n")


class TestParsing:
    def test_reads_a_timed_event(self):
        feed = ical(timed("1", "20260903T082000", "School run", location="The gate"))
        events = parse_feed(feed, date(2026, 9, 3), date(2026, 9, 4), BERLIN)
        assert len(events) == 1
        event = events[0]
        assert event["title"] == "School run"
        assert event["time"] == "08:20"
        assert event["date"] == "2026-09-03"
        assert event["all_day"] is False
        assert event["location"] == "The gate"

    def test_reads_an_all_day_event(self):
        feed = ical(all_day("1", "20260903", "Inset day"))
        events = parse_feed(feed, date(2026, 9, 3), date(2026, 9, 4), BERLIN)
        assert events[0]["all_day"] is True
        assert events[0]["time"] is None
        assert events[0]["date"] == "2026-09-03"

    def test_event_without_a_summary_still_appears(self):
        feed = ical("BEGIN:VEVENT\r\nUID:1\r\nDTSTART;TZID=Europe/Berlin:20260903T090000\r\nEND:VEVENT\r\n")
        events = parse_feed(feed, date(2026, 9, 3), date(2026, 9, 4), BERLIN)
        assert events[0]["title"] == "Untitled"

    def test_rubbish_is_reported_not_swallowed(self):
        with pytest.raises(FeedError):
            parse_feed("this is not a calendar", date(2026, 9, 3), date(2026, 9, 4), BERLIN)

    def test_labels_events_with_their_feed(self):
        feed = ical(timed("1", "20260903T082000", "School run"))
        events = parse_feed(feed, date(2026, 9, 3), date(2026, 9, 4), BERLIN, label="Sam's")
        assert events[0]["calendar"] == "Sam's"


class TestOrdering:
    def test_sorts_chronologically_not_alphabetically(self):
        # Monday sorts after Friday alphabetically; chronologically it is first.
        feed = ical(
            timed("1", "20260904T150000", "Friday afternoon"),
            timed("2", "20260907T090000", "Monday morning"),
            timed("3", "20260903T082000", "Thursday school run"),
        )
        events = sorted(
            parse_feed(feed, date(2026, 9, 3), date(2026, 9, 8), BERLIN), key=sort_key
        )
        assert [e["title"] for e in events] == [
            "Thursday school run", "Friday afternoon", "Monday morning",
        ]

    def test_orders_within_a_day_by_time(self):
        feed = ical(
            timed("1", "20260903T183000", "Parents' evening"),
            timed("2", "20260903T082000", "School run"),
            timed("3", "20260903T154500", "Swimming"),
        )
        events = sorted(
            parse_feed(feed, date(2026, 9, 3), date(2026, 9, 4), BERLIN), key=sort_key
        )
        assert [e["time"] for e in events] == ["08:20", "15:45", "18:30"]

    def test_all_day_events_lead_their_day(self):
        feed = ical(
            timed("1", "20260903T082000", "School run"),
            all_day("2", "20260903", "Inset day"),
        )
        events = sorted(
            parse_feed(feed, date(2026, 9, 3), date(2026, 9, 4), BERLIN), key=sort_key
        )
        assert [e["title"] for e in events] == ["Inset day", "School run"]


class TestTimezones:
    def test_converts_into_the_family_timezone(self):
        # 07:20 UTC is 09:20 in Berlin in September.
        feed = ical(timed("1", "20260903T072000", "Call", tz="UTC"))
        events = parse_feed(feed, date(2026, 9, 3), date(2026, 9, 4), BERLIN)
        assert events[0]["time"] == "09:20"

    def test_a_conversion_can_move_an_event_to_another_day(self):
        # 23:30 in Auckland on the 3rd is still the 3rd there, but 11:30 UTC.
        auckland = ZoneInfo("Pacific/Auckland")
        feed = ical(timed("1", "20260903T233000", "Late one", tz="UTC"))
        events = parse_feed(feed, date(2026, 9, 3), date(2026, 9, 5), auckland)
        assert events[0]["date"] == "2026-09-04"

    def test_floating_times_are_read_as_local(self):
        feed = ical("BEGIN:VEVENT\r\nUID:1\r\nDTSTART:20260903T082000\r\nSUMMARY:Floating\r\nEND:VEVENT\r\n")
        events = parse_feed(feed, date(2026, 9, 3), date(2026, 9, 4), BERLIN)
        assert events[0]["time"] == "08:20"

    def test_unknown_zone_falls_back_rather_than_crashing(self):
        assert zone("Not/AZone").key == "UTC"


class TestRecurrence:
    def test_expands_a_weekly_repeat(self):
        feed = ical(
            "BEGIN:VEVENT\r\nUID:1\r\nDTSTART;TZID=Europe/Berlin:20260903T082000\r\n"
            "RRULE:FREQ=WEEKLY;COUNT=3\r\nSUMMARY:Swimming\r\nEND:VEVENT\r\n"
        )
        events = parse_feed(feed, date(2026, 9, 3), date(2026, 9, 24), BERLIN)
        assert [e["date"] for e in events] == ["2026-09-03", "2026-09-10", "2026-09-17"]


class TestMerging:
    def test_one_broken_feed_does_not_empty_the_board(self, monkeypatch):
        good = ical(timed("1", "20260903T082000", "School run"))

        def fake_fetch(url, start, end, tzinfo, label=None, timeout=30):
            if url == "bad":
                raise FeedError("404")
            return parse_feed(good, start, end, tzinfo, label=label)

        monkeypatch.setattr("dinkydash.calendars.fetch_feed", fake_fetch)
        events, statuses = fetch_events(
            [{"label": "Broken", "url": "bad"}, {"label": "Fine", "url": "good"}],
            date(2026, 9, 3), BERLIN,
        )
        assert [e["title"] for e in events] == ["School run"]
        assert [s["ok"] for s in statuses] == [False, True]

    def test_paused_feeds_are_skipped(self, monkeypatch):
        monkeypatch.setattr(
            "dinkydash.calendars.fetch_feed",
            lambda *a, **k: pytest.fail("a paused feed should not be fetched"),
        )
        events, statuses = fetch_events(
            [{"label": "Off", "url": "x", "enabled": False}], date(2026, 9, 3), BERLIN
        )
        assert events == []
        assert statuses[0]["ok"] is None

    def test_a_feed_with_no_url_is_reported(self):
        events, statuses = fetch_events([{"label": "Blank"}], date(2026, 9, 3), BERLIN)
        assert events == []
        assert statuses[0]["ok"] is False

    def test_no_calendars_at_all(self):
        assert fetch_events(None, date(2026, 9, 3), BERLIN) == ([], [])


class TestEventsOn:
    def test_picks_out_one_day(self):
        feed = ical(
            timed("1", "20260903T082000", "Today"),
            timed("2", "20260904T090000", "Tomorrow"),
        )
        events = parse_feed(feed, date(2026, 9, 3), date(2026, 9, 5), BERLIN)
        assert [e["title"] for e in events_on(events, date(2026, 9, 3))] == ["Today"]

    def test_a_day_with_nothing_on_it(self):
        assert events_on([], date(2026, 9, 3)) == []
