"""What is owed, and when.

`due` is the whole of the tick's decision-making and it is pure, so these are
the tests that stop a family in Auckland getting yesterday's brief and a Pi
left on UTC writing at the wrong hour. Every `now` here is UTC, deliberately:
the server's clock is never the family's.
"""

from datetime import datetime, time, timedelta, timezone

import pytest

from dinkydash.schedule import (DEFAULT_BRIEF_TIME, DEFAULT_REFRESH_MINUTES,
                                brief_due, brief_time, due, parse_stamp,
                                refresh_due, refresh_interval)

BERLIN = {"timezone": "Europe/Berlin", "refresh_minutes": 60, "brief_time": "06:00"}
AUCKLAND = {"timezone": "Pacific/Auckland", "refresh_minutes": 60, "brief_time": "06:00"}


def utc(text):
    """An aware UTC datetime from '2026-09-03 04:05'."""
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def payload(fetched=None, generated_for=None):
    stored = {}
    if fetched:
        stored["calendars_fetched_at"] = fetched
    if generated_for:
        stored["generated_for_date"] = generated_for
    return stored


class TestFirstRun:
    def test_no_payload_owes_a_fetch(self):
        # Nothing has ever been stored, so there is nothing to be stale.
        assert due(BERLIN, None, utc("2026-09-03 01:00"))["refresh"] is True

    def test_no_payload_before_the_brief_time_owes_both_anyway(self):
        # 03:00 Berlin, and the first board does not wait for 06:00 (DIN-45).
        # Somebody who signed up in the night has the waiting screen on the
        # wall, and that is not a board at any hour.
        owed = due(BERLIN, None, utc("2026-09-03 01:00"))
        assert owed == {"refresh": True, "brief": True}

    def test_no_payload_after_the_brief_time_owes_both(self):
        assert due(BERLIN, None, utc("2026-09-03 07:00")) == {"refresh": True, "brief": True}

    def test_an_empty_payload_is_the_same_as_none(self):
        assert due(BERLIN, {}, utc("2026-09-03 07:00")) == {"refresh": True, "brief": True}


class TestTheFirstBrief:
    """DIN-45: a family that has never had one is owed it now, not at `brief_time`.

    The condition is "the payload holds no `generated_for_date`", which both
    stores produce for exactly one situation — no successful generation. A
    calendar refresh does not clear it, and that is the pair of cases below.
    """

    @pytest.mark.parametrize("moment", ["2026-09-03 01:00",   # 03:00 Berlin
                                        "2026-09-03 22:30",   # 00:30, the next day
                                        "2026-09-03 12:00"])  # 14:00, an ordinary afternoon
    def test_it_is_owed_at_any_hour(self, moment):
        assert brief_due(BERLIN, {}, utc(moment)) is True

    def test_a_fetched_agenda_is_not_a_brief(self):
        # The worker's first tick refreshes and writes, in that order. Between
        # the two the payload holds an agenda and nothing else, and that must
        # still read as "no brief" or the board it just fetched for stays blank.
        stored = payload(fetched="2026-09-03T01:00:00+00:00")
        assert brief_due(BERLIN, stored, utc("2026-09-03 01:00")) is True

    def test_once_the_first_one_is_written_the_next_waits_for_the_morning(self):
        # The guard against "always due": having written one, the ordinary
        # rule is back and tomorrow's line waits for 06:00 Berlin.
        stored = payload(generated_for="2026-09-03")
        assert brief_due(BERLIN, stored, utc("2026-09-03 22:30")) is False  # 00:30 on the 4th
        assert brief_due(BERLIN, stored, utc("2026-09-04 03:59")) is False  # 05:59
        assert brief_due(BERLIN, stored, utc("2026-09-04 04:00")) is True   # 06:00

    def test_the_timezone_still_decides_which_day_it_is(self):
        # 18:00 UTC on the 14th is 06:00 on the 15th in Auckland. A family with
        # no brief is owed one either way, and the one written for the 15th
        # then holds — the first-run exception must not outlive the first run.
        assert brief_due(AUCKLAND, {}, utc("2026-06-14 17:59")) is True
        assert brief_due(AUCKLAND, payload(generated_for="2026-06-15"),
                         utc("2026-06-14 18:00")) is False


class TestTheFirstBriefWaitsForSetUp:
    """The DIN-45 exception is for a real family, not for the invented one.

    A hosted family starts with `starter_config` — Mia, Theo, Biscuit and no
    timezone — and a Pi copying the example file starts the same way. Writing
    the first brief then would spend a call on somebody else's children and
    hang it on the wall as the first thing the family sees. So "no brief yet"
    is owed only once `config.is_set_up` says there is a family to write for.
    """

    def test_the_starter_household_is_owed_nothing_at_any_hour(self):
        from dinkydash import config as config_module
        starter = config_module.starter_config()
        for moment in ("2026-09-03 01:00", "2026-09-03 07:00", "2026-09-03 22:30"):
            assert brief_due(starter, {}, utc(moment)) is False

    def test_nor_with_the_calendars_fetched(self):
        from dinkydash import config as config_module
        stored = payload(fetched="2026-09-03T01:00:00+00:00")
        assert brief_due(config_module.starter_config(), stored, utc("2026-09-03 01:00")) is False

    def test_but_the_refresh_is_still_owed(self):
        # Fetching is free, and the agenda is ready when the brief is written.
        from dinkydash import config as config_module
        assert due(config_module.starter_config(), None, utc("2026-09-03 01:00")) == \
            {"refresh": True, "brief": False}

    def test_a_real_household_on_the_default_timezone_still_waits(self):
        # Replacing the people is half of set-up. On UTC the "day" the brief is
        # written for may not be the family's, so the timezone is the other half.
        home = {"timezone": "UTC", "people": [{"name": "Ines", "date_of_birth": "2022-01-09"}]}
        assert brief_due(home, {}, utc("2026-09-03 12:00")) is False

    def test_once_set_up_it_is_owed_immediately(self):
        from dinkydash import config as config_module
        home = config_module.starter_config()
        home["timezone"] = "Europe/Berlin"
        for person in home["people"] + home["pets"]:
            person.pop(config_module.INVENTED)
        assert brief_due(home, {}, utc("2026-09-03 01:00")) is True  # 03:00 Berlin

    def test_a_written_brief_follows_the_ordinary_rule_whatever_the_config(self):
        # The family that signed up before this rule has yesterday's board;
        # it is replaced at brief_time like anybody's, not held back.
        from dinkydash import config as config_module
        starter = config_module.starter_config()
        stored = payload(generated_for="2026-09-02")
        assert brief_due(starter, stored, utc("2026-09-03 05:59")) is False
        assert brief_due(starter, stored, utc("2026-09-03 06:00")) is True


class TestRefresh:
    def test_not_due_inside_the_interval(self):
        stored = payload(fetched="2026-09-03T10:00:00+00:00")
        assert refresh_due(BERLIN, stored, utc("2026-09-03 10:59")) is False

    def test_due_on_the_interval(self):
        stored = payload(fetched="2026-09-03T10:00:00+00:00")
        assert refresh_due(BERLIN, stored, utc("2026-09-03 11:00")) is True

    def test_a_shorter_interval_is_obeyed(self):
        stored = payload(fetched="2026-09-03T10:00:00+00:00")
        config = dict(BERLIN, refresh_minutes=15)
        assert refresh_due(config, stored, utc("2026-09-03 10:14")) is False
        assert refresh_due(config, stored, utc("2026-09-03 10:15")) is True

    def test_a_daily_interval_is_obeyed(self):
        stored = payload(fetched="2026-09-03T10:00:00+00:00")
        config = dict(BERLIN, refresh_minutes=1440)
        assert refresh_due(config, stored, utc("2026-09-03 23:00")) is False
        assert refresh_due(config, stored, utc("2026-09-04 10:00")) is True

    def test_a_stamp_from_the_future_forces_a_fetch(self):
        # The Pi's clock was wrong and has just been corrected. Believe the
        # clock rather than the file — a fetch costs nothing.
        stored = payload(fetched="2027-01-01T00:00:00+00:00")
        assert refresh_due(BERLIN, stored, utc("2026-09-03 10:00")) is True

    def test_a_naive_stamp_is_read_as_utc(self):
        # An older payload, written before the stamp carried an offset.
        stored = payload(fetched="2026-09-03T10:00:00")
        assert refresh_due(BERLIN, stored, utc("2026-09-03 10:30")) is False
        assert refresh_due(BERLIN, stored, utc("2026-09-03 11:30")) is True

    def test_an_unreadable_stamp_is_treated_as_absent(self):
        assert refresh_due(BERLIN, payload(fetched="soon"), utc("2026-09-03 10:00")) is True

    def test_a_stale_brief_does_not_make_a_fetch_due(self):
        # The two clocks are independent: yesterday's headline over a
        # ten-minute-old agenda is a state the board already handles.
        stored = payload(fetched="2026-09-03T10:00:00+00:00", generated_for="2026-09-02")
        assert refresh_due(BERLIN, stored, utc("2026-09-03 10:10")) is False


class TestBriefTimeCrossing:
    @pytest.mark.parametrize("moment, expected", [
        ("2026-09-03 03:00", False),  # 05:00 Berlin
        ("2026-09-03 03:58", False),  # 05:58
        ("2026-09-03 03:59", False),  # 05:59
        ("2026-09-03 04:00", True),   # 06:00 — on the minute
        ("2026-09-03 04:01", True),   # 06:01
        ("2026-09-03 20:00", True),   # 22:00, still owed if the day was missed
    ])
    def test_the_brief_waits_for_the_family_clock(self, moment, expected):
        stored = payload(generated_for="2026-09-02")
        assert brief_due(BERLIN, stored, utc(moment)) is expected

    def test_once_written_it_is_not_owed_again(self):
        stored = payload(generated_for="2026-09-03")
        assert brief_due(BERLIN, stored, utc("2026-09-03 04:00")) is False
        assert brief_due(BERLIN, stored, utc("2026-09-03 21:59")) is False

    def test_it_is_owed_again_after_midnight_and_the_brief_time(self):
        stored = payload(generated_for="2026-09-03")
        # 00:30 Berlin on the 4th: a new day, but too early.
        assert brief_due(BERLIN, stored, utc("2026-09-03 22:30")) is False
        # 06:00 Berlin on the 4th.
        assert brief_due(BERLIN, stored, utc("2026-09-04 04:00")) is True

    def test_a_failed_brief_is_owed_again_on_the_next_tick(self):
        # A failure writes nothing, so generated_for_date still says yesterday
        # and five minutes later the answer is still yes. That is the retry.
        stored = payload(generated_for="2026-09-02")
        assert brief_due(BERLIN, stored, utc("2026-09-03 04:00")) is True
        assert brief_due(BERLIN, stored, utc("2026-09-03 04:05")) is True

    def test_a_later_brief_time_is_obeyed(self):
        stored = payload(generated_for="2026-09-02")
        config = dict(BERLIN, brief_time="07:30")
        assert brief_due(config, stored, utc("2026-09-03 05:29")) is False  # 07:29
        assert brief_due(config, stored, utc("2026-09-03 05:30")) is True   # 07:30


class TestTheOtherSideOfTheWorld:
    """Auckland is twelve hours from UTC, so the local date is often not the server's."""

    def test_the_day_is_the_familys_day_not_the_servers(self):
        # 2026-06-14 18:00 UTC is 2026-06-15 06:00 in Auckland.
        moment = utc("2026-06-14 18:00")
        assert brief_due(AUCKLAND, payload(generated_for="2026-06-14"), moment) is True
        assert brief_due(AUCKLAND, payload(generated_for="2026-06-15"), moment) is False

    def test_the_brief_time_is_the_familys_clock(self):
        stored = payload(generated_for="2026-06-14")
        assert brief_due(AUCKLAND, stored, utc("2026-06-14 17:59")) is False  # 05:59 local
        assert brief_due(AUCKLAND, stored, utc("2026-06-14 18:00")) is True   # 06:00 local

    def test_a_server_at_utc_midnight_is_mid_afternoon_there(self):
        # A board written at 18:00 local looks, from UTC, like it was written
        # "tomorrow". It is still today's, and must not be rewritten.
        assert brief_due(AUCKLAND, payload(generated_for="2026-06-15"),
                         utc("2026-06-15 06:00")) is False


class TestDaylightSaving:
    """Berlin, 29 March 2026: 02:00 becomes 03:00. Wall times 02:00-02:59 never happen."""

    def test_a_brief_time_inside_the_lost_hour_is_not_skipped(self):
        config = dict(BERLIN, brief_time="02:30")
        stored = payload(generated_for="2026-03-28")
        # 01:30 local, before the jump.
        assert brief_due(config, stored, utc("2026-03-29 00:30")) is False
        # The clock goes straight to 03:00, which is past 02:30, so it is owed.
        assert brief_due(config, stored, utc("2026-03-29 01:00")) is True

    def test_the_refresh_interval_counts_real_minutes_not_wall_clock(self):
        # Fetched at 01:30 local. At 03:05 local the wall clock has moved 95
        # minutes but only 35 have passed, so an hourly refresh is not owed.
        stored = payload(fetched="2026-03-29T00:30:00+00:00")
        assert refresh_due(BERLIN, stored, utc("2026-03-29 01:05")) is False
        assert refresh_due(BERLIN, stored, utc("2026-03-29 01:30")) is True

    def test_the_repeated_hour_does_not_write_a_second_brief(self):
        # 25 October 2026: 02:00-02:59 happens twice. The first pass writes the
        # brief; the second must find it already written for the day.
        config = dict(BERLIN, brief_time="02:30")
        assert brief_due(config, payload(generated_for="2026-10-24"),
                         utc("2026-10-25 00:30")) is True   # 02:30 CEST
        assert brief_due(config, payload(generated_for="2026-10-25"),
                         utc("2026-10-25 01:30")) is False  # 02:30 CET, again

    def test_auckland_gains_an_hour_without_losing_the_brief(self):
        # 27 September 2026: 02:00 becomes 03:00 in Auckland too.
        config = dict(AUCKLAND, brief_time="02:30")
        stored = payload(generated_for="2026-09-26")
        assert brief_due(config, stored, utc("2026-09-26 13:30")) is False  # 01:30 local
        assert brief_due(config, stored, utc("2026-09-26 14:00")) is True   # 03:00 local


class TestSettings:
    def test_defaults_when_the_keys_are_missing(self):
        assert refresh_interval({}) == timedelta(minutes=DEFAULT_REFRESH_MINUTES)
        assert brief_time({}) == time.fromisoformat(DEFAULT_BRIEF_TIME)

    def test_nonsense_falls_back_rather_than_raising(self):
        assert refresh_interval({"refresh_minutes": "hourly"}) == timedelta(minutes=60)
        assert brief_time({"brief_time": "breakfast"}) == time(6, 0)
        # YAML 1.1 would read an unquoted 06:00 as the number 360.
        assert brief_time({"brief_time": 360}) == time(6, 0)

    def test_a_zero_interval_still_leaves_a_gap(self):
        # Otherwise every tick fetches, for ever.
        assert refresh_interval({"refresh_minutes": 0}) == timedelta(minutes=1)
        assert refresh_interval({"refresh_minutes": -5}) == timedelta(minutes=1)

    def test_seconds_in_a_brief_time_are_accepted(self):
        assert brief_time({"brief_time": "06:30:00"}) == time(6, 30)

    def test_parse_stamp_round_trips_an_offset(self):
        assert parse_stamp("2026-09-03T10:00:00+02:00") == utc("2026-09-03 08:00")
        assert parse_stamp(None) is None
        assert parse_stamp("") is None
