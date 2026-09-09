"""Calendar parsing, ordering and timezone handling.

The ordering tests are the point of this file: the previous implementation
sorted events by their formatted string, so "Friday, August 15" came before
"Monday, August 11" and today's school run could land after next Tuesday.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from dinkydash.calendars import (FeedError, addresses, describe_feed, events_on,
                                 fetch_events, parse_feed, sort_key, zone)

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


def with_people(uid, start, summary, organizer=None, guests=()):
    """A timed event with a guest list, written the way a Google feed writes one."""
    lines = [f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART;TZID=Europe/Berlin:{start}\r\n"
             f"SUMMARY:{summary}\r\n"]
    if organizer:
        lines.append(f"ORGANIZER;CN=Someone:mailto:{organizer}\r\n")
    for guest in guests:
        lines.append(f"ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;"
                     f"CN=Someone;X-NUM-GUESTS=0:mailto:{guest}\r\n")
    lines.append("END:VEVENT\r\n")
    return "".join(lines)


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

        def fake_fetch(url, start, end, tzinfo, label=None, timeout=30, shared_with=None):
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

    def test_each_feed_carries_its_own_guest_list(self, monkeypatch):
        # Per feed, not global: the school calendar has no guests, and a
        # filter that applied to it would empty it — the old key's failure.
        seen = []

        def fake_fetch(url, start, end, tzinfo, label=None, timeout=30, shared_with=None):
            seen.append((label, shared_with))
            return []

        monkeypatch.setattr("dinkydash.calendars.fetch_feed", fake_fetch)
        fetch_events([
            {"label": "Sam's", "url": "a", "shared_with": ["Jess@Example.com"]},
            {"label": "School", "url": "b"},
        ], date(2026, 9, 3), BERLIN)
        assert seen == [("Sam's", ["jess@example.com"]), ("School", [])]


class TestSharedWith:
    """A personal calendar contributes only the events the other parent is on."""

    WINDOW = (date(2026, 9, 3), date(2026, 9, 4))
    JESS = "jess@example.com"

    def titles(self, feed, shared_with):
        events = parse_feed(feed, *self.WINDOW, BERLIN, shared_with=shared_with)
        return [e["title"] for e in events]

    def test_keeps_an_event_they_were_invited_to(self):
        feed = ical(with_people("1", "20260903T082000", "Swimming",
                                organizer="sam@example.com",
                                guests=["sam@example.com", self.JESS]))
        assert self.titles(feed, [self.JESS]) == ["Swimming"]

    def test_keeps_an_event_they_organised(self):
        # She sent the invitation, so she is the ORGANIZER — and a Google feed
        # does not always list an organiser as a guest of their own event. The
        # old filter looked at ATTENDEE alone and missed everything she arranged.
        feed = ical(with_people("1", "20260903T082000", "Parents' evening",
                                organizer=self.JESS, guests=["sam@example.com"]))
        assert self.titles(feed, [self.JESS]) == ["Parents' evening"]

    def test_hides_an_event_with_nobody_on_it(self):
        # The private and the work things: no guest list at all.
        feed = ical(
            timed("1", "20260903T090000", "Therapy"),
            with_people("2", "20260903T100000", "Dentist",
                        organizer="sam@example.com", guests=[self.JESS]),
        )
        assert self.titles(feed, [self.JESS]) == ["Dentist"]

    def test_hides_an_event_shared_with_somebody_else(self):
        feed = ical(with_people("1", "20260903T090000", "1:1 with Priya",
                                organizer="sam@example.com", guests=["priya@work.example"]))
        assert self.titles(feed, [self.JESS]) == []

    def test_case_and_mailto_do_not_matter(self):
        feed = ical(with_people("1", "20260903T090000", "Lunch", guests=["Jess@Example.COM"]))
        assert self.titles(feed, ["JESS@example.com"]) == ["Lunch"]

    def test_any_one_of_several_addresses_is_enough(self):
        # Two addresses for one person, or two people: either counts. The old
        # key required every listed address on every event.
        feed = ical(
            with_people("1", "20260903T090000", "With her work address",
                        guests=["jess@work.example"]),
            with_people("2", "20260903T100000", "With the nanny", guests=["nanny@example.com"]),
            with_people("3", "20260903T110000", "With neither", guests=["priya@work.example"]),
        )
        wanted = [self.JESS, "jess@work.example", "nanny@example.com"]
        assert self.titles(feed, wanted) == ["With her work address", "With the nanny"]

    @pytest.mark.parametrize("nobody", [None, [], "", "  "])
    def test_no_list_means_everything(self, nobody):
        feed = ical(
            timed("1", "20260903T090000", "Therapy"),
            with_people("2", "20260903T100000", "Dentist", guests=[self.JESS]),
        )
        assert self.titles(feed, nobody) == ["Therapy", "Dentist"]

    def test_a_hand_written_string_works_like_the_list(self):
        # config.yaml is edited by hand too: `shared_with: jess@example.com`.
        feed = ical(with_people("1", "20260903T090000", "Lunch", guests=[self.JESS]))
        assert self.titles(feed, "jess@example.com") == ["Lunch"]
        assert self.titles(feed, "nanny@example.com, jess@example.com") == ["Lunch"]

    def test_the_guest_list_stays_out_of_the_event(self):
        # The addresses are other people's. They decide what is shown and are
        # then forgotten: nothing in the payload can say who was invited.
        feed = ical(with_people("1", "20260903T090000", "Lunch",
                                organizer="sam@example.com", guests=[self.JESS]))
        event = parse_feed(feed, *self.WINDOW, BERLIN, shared_with=[self.JESS])[0]
        assert "example.com" not in str(event)


class TestAddresses:
    def test_splits_on_commas_spaces_and_newlines(self):
        assert addresses("a@x.example, b@x.example c@x.example\nd@x.example") == [
            "a@x.example", "b@x.example", "c@x.example", "d@x.example",
        ]

    def test_lowercases_trims_and_drops_mailto_and_duplicates(self):
        assert addresses(["  A@X.example ", "mailto:a@x.example", None, ""]) == ["a@x.example"]

    def test_nothing_is_an_empty_list(self):
        assert addresses(None) == []
        assert addresses("") == []
        assert addresses([]) == []


class TestDescribeFeed:
    """What "Check this link" is told."""

    FEED = ical(
        timed("1", "20260903T090000", "Therapy"),
        with_people("2", "20260903T100000", "Dentist", guests=["jess@example.com"]),
        timed("3", "20260904T090000", "Standup"),
    )

    @pytest.fixture(autouse=True)
    def served(self, monkeypatch):
        monkeypatch.setattr("dinkydash.calendars.fetch_text",
                            lambda url, timeout=30: self.FEED)

    def describe(self, **kwargs):
        return describe_feed("https://x.example/a.ics", BERLIN, today=date(2026, 9, 3), **kwargs)

    def test_the_caller_must_supply_the_date(self):
        with pytest.raises(TypeError, match="today"):
            describe_feed("https://x.example/a.ics", BERLIN)

    def test_counts_everything_without_a_list(self):
        found = self.describe()
        assert (found["count"], found["total"]) == (3, 3)
        assert found["next"]["title"] == "Therapy"

    def test_counts_before_and_after_the_list(self):
        found = self.describe(shared_with=["jess@example.com"])
        assert (found["count"], found["total"]) == (1, 3)
        assert found["next"]["title"] == "Dentist"
        assert found["shared_with"] == ["jess@example.com"]

    def test_a_list_that_matches_nobody_is_told_apart_from_an_empty_calendar(self):
        found = self.describe(shared_with=["nobody@example.com"])
        assert (found["count"], found["total"]) == (0, 3)
        assert found["next"] is None


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
