"""A decade-long feed is parsed a fortnight at a time.

`icalendar` builds an object for every property of every event, and a personal
Google calendar is ten years of them: the owner's is 8 MB and 14,000 events,
measured at ~200 MB to parse and ~250 MB kept afterwards, which is how two
gunicorn workers took the hosted site past 512 MB on 10 September 2026.
`calendars._trim` drops, as text, every VEVENT that cannot touch the window
before the parser sees it. These tests pin what must survive the trim: the
trimmed parse has to give exactly what the untrimmed one gave.
"""

from datetime import date, timedelta

from icalendar import Calendar
from recurring_ical_events import of as recurring_events_of

from dinkydash import calendars
from dinkydash.calendars import parse_feed, sort_key
from tests.test_calendars import BERLIN, all_day, ical, timed

START = date(2026, 9, 10)
END = START + timedelta(days=14)


def weekly(uid, first, summary, until=None):
    rule = "RRULE:FREQ=WEEKLY" + (f";UNTIL={until}" if until else "")
    return (f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART;TZID=Europe/Berlin:{first}\r\n"
            f"{rule}\r\nSUMMARY:{summary}\r\nEND:VEVENT\r\n")


def moved(uid, original, new_start, summary):
    """One occurrence of `uid` rescheduled — the exception a RECURRENCE-ID carries."""
    return (f"BEGIN:VEVENT\r\nUID:{uid}\r\nRECURRENCE-ID;TZID=Europe/Berlin:{original}\r\n"
            f"DTSTART;TZID=Europe/Berlin:{new_start}\r\nSUMMARY:{summary}\r\nEND:VEVENT\r\n")


def extra_date(uid, first, extra, summary):
    return (f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART;VALUE=DATE:{first}\r\n"
            f"RDATE;VALUE=DATE:{extra}\r\nSUMMARY:{summary}\r\nEND:VEVENT\r\n")


def spanning(uid, first_day, last_day, summary):
    return (f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART;VALUE=DATE:{first_day}\r\n"
            f"DTEND;VALUE=DATE:{last_day}\r\nSUMMARY:{summary}\r\nEND:VEVENT\r\n")


def lasting(uid, start, duration, summary):
    return (f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART;TZID=Europe/Berlin:{start}\r\n"
            f"DURATION:{duration}\r\nSUMMARY:{summary}\r\nEND:VEVENT\r\n")


def with_alarm(uid, start, summary):
    return (f"BEGIN:VEVENT\r\nUID:{uid}\r\nDTSTART;TZID=Europe/Berlin:{start}\r\n"
            f"SUMMARY:{summary}\r\nBEGIN:VALARM\r\nACTION:DISPLAY\r\nTRIGGER:-PT10M\r\n"
            f"DESCRIPTION:{summary}\r\nEND:VALARM\r\nEND:VEVENT\r\n")


TIMEZONE_BLOCK = ("BEGIN:VTIMEZONE\r\nTZID:Europe/Berlin\r\nBEGIN:STANDARD\r\n"
                  "DTSTART:19701025T030000\r\nTZOFFSETFROM:+0200\r\nTZOFFSETTO:+0100\r\n"
                  "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU\r\nEND:STANDARD\r\nEND:VTIMEZONE\r\n")


def untrimmed(feed):
    """What the parser gave before the trim existed."""
    occurrences = recurring_events_of(Calendar.from_ical(feed)).between(START, END + timedelta(days=1))
    return sorted(calendars._events(list(occurrences), BERLIN, None, None), key=sort_key)


def trimmed(feed):
    return sorted(parse_feed(feed, START, END, BERLIN), key=sort_key)


def titles(feed):
    return [e["title"] for e in trimmed(feed)]


def test_events_outside_the_window_are_dropped_as_text():
    feed = ical(timed("old", "20250910T090000", "Last year"),
                timed("now", "20260915T090000", "This fortnight"),
                timed("later", "20270910T090000", "Next year"))
    kept = calendars._trim(feed, START, END)
    assert "UID:now" in kept
    assert "UID:old" not in kept and "UID:later" not in kept
    assert titles(feed) == ["This fortnight"]


def test_the_window_edges_are_kept():
    feed = ical(all_day("first", START.strftime("%Y%m%d"), "Day one"),
                all_day("last", END.strftime("%Y%m%d"), "Day fourteen"),
                all_day("before", (START - timedelta(days=30)).strftime("%Y%m%d"), "A month ago"))
    assert titles(feed) == ["Day one", "Day fourteen"]


def test_recurring_events_are_kept_whatever_their_start():
    feed = ical(weekly("standup", "20200910T100000", "Weekly since 2020"),
                weekly("gone", "20190101T100000", "Ended in 2021", until="20210101T000000Z"))
    assert "UID:standup" in calendars._trim(feed, START, END)
    assert titles(feed) == ["Weekly since 2020"] * 3
    assert trimmed(feed) == untrimmed(feed)


def test_a_moved_occurrence_is_honoured():
    # 17 September falls in the window; the exception moves it to October. If the
    # trim dropped that exception, the parser would put the original back.
    feed = ical(weekly("standup", "20200910T100000", "Weekly"),
                moved("standup", "20260917T100000", "20261001T100000", "Weekly"),
                moved("standup", "20261008T100000", "20260918T110000", "Weekly, pulled forward"))
    assert [e["date"] for e in trimmed(feed)] == ["2026-09-10", "2026-09-18", "2026-09-24"]
    assert trimmed(feed) == untrimmed(feed)


def test_an_extra_date_on_an_old_event_is_kept():
    feed = ical(extra_date("party", "20190601", "20260915", "Reunion"))
    assert [e["date"] for e in trimmed(feed)] == ["2026-09-15"]
    assert trimmed(feed) == untrimmed(feed)


def test_an_event_that_started_before_the_window_and_runs_into_it_is_kept():
    feed = ical(spanning("holiday", "20260901", "20260912", "Holiday"),
                lasting("retreat", "20260830T090000", "P3W", "Retreat"),
                spanning("finished", "20260801", "20260805", "Over before it began"))
    kept = calendars._trim(feed, START, END)
    assert "UID:holiday" in kept and "UID:retreat" in kept
    assert "UID:finished" not in kept
    assert trimmed(feed) == untrimmed(feed)


def test_a_date_the_trim_cannot_read_means_keep():
    folded = ("BEGIN:VEVENT\r\nUID:folded\r\nDTSTART;TZID=Europe/Berlin:2026091\r\n 5T090000\r\n"
              "SUMMARY:Folded mid-value\r\nEND:VEVENT\r\n")
    quoted = ("BEGIN:VEVENT\r\nUID:quoted\r\nDTSTART;X-NOTE=\"a:b\":20260916T090000\r\n"
              "SUMMARY:Colon in a parameter\r\nEND:VEVENT\r\n")
    feed = ical(folded, quoted)
    kept = calendars._trim(feed, START, END)
    assert "UID:folded" in kept and "UID:quoted" in kept
    assert titles(feed) == ["Folded mid-value", "Colon in a parameter"]


def test_timezones_and_alarms_survive_and_dropped_events_take_their_alarms_with_them():
    feed = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n" + TIMEZONE_BLOCK
            + with_alarm("now", "20260915T090000", "Dentist")
            + with_alarm("old", "20200915T090000", "Old dentist")
            + "END:VCALENDAR\r\n")
    kept = calendars._trim(feed, START, END)
    assert "BEGIN:VTIMEZONE" in kept
    assert kept.count("BEGIN:VALARM") == 1
    assert "Old dentist" not in kept
    assert titles(feed) == ["Dentist"]
    assert trimmed(feed) == untrimmed(feed)


def test_a_decade_of_appointments_shrinks_to_the_fortnight():
    old = [timed(f"old-{i}", (date(2016, 1, 1) + timedelta(days=i % 3600)).strftime("%Y%m%dT090000"),
                 f"Event {i}") for i in range(10_000)]
    current = [timed("a", "20260911T090000", "A"), timed("b", "20260920T090000", "B")]
    feed = ical(*old, *current)
    kept = calendars._trim(feed, START, END)
    assert kept.count("BEGIN:VEVENT") == 2
    assert titles(feed) == ["A", "B"]
    assert trimmed(feed) == untrimmed(feed)


def test_trim_leaves_a_small_feed_alone():
    feed = ical(timed("a", "20260911T090000", "A"), all_day("b", "20260920", "B"))
    assert calendars._trim(feed, START, END) == feed
