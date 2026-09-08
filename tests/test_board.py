"""What the board shows, especially on a day the generation failed.

The design claim being tested: when a morning's run fails, the times, turns and
countdowns on the wall are still *today's* — only the written line is old.
"""

from datetime import date

import pytest

from dinkydash.board import build_view, computed_headline

CONFIG = {
    "family_name": "The Wilsons",
    "theme": "light",
    "people": [{"name": "Mia", "date_of_birth": "2017-03-15"}],
    "recurring": [{"title": "Set the table", "emoji": "🍽", "choices": ["Mia", "Theo"]}],
    "special_dates": [{"title": "Christmas", "emoji": "🎄", "date": "12/25"}],
}

TODAY = date(2026, 9, 3)


def event(day, time_, title, all_day=False):
    return {
        "title": title, "date": day, "time": None if all_day else time_,
        "all_day": all_day, "start": f"{day}T{time_ or '00:00'}:00+02:00",
        "location": None, "calendar": "Family",
    }


def payload(for_date, events=None, headline="Big morning", note="An octopus fact"):
    return {
        "generated_for_date": for_date,
        "generated_at": f"{for_date}T04:32:00+02:00",
        "headline": headline,
        "note": note,
        "note_kind": "fact",
        "events": events or [],
    }


class TestComputedHeadline:
    def test_nothing_on(self):
        assert computed_headline([]) == "Nothing booked in today."

    def test_one_thing(self):
        assert computed_headline([event("2026-09-03", "08:20", "School run")]) == \
            "1 thing on today, starting at 08:20."

    def test_several_things_lead_with_the_first_time(self):
        events = [event("2026-09-03", "08:20", "School run"),
                  event("2026-09-03", "15:45", "Swimming")]
        assert computed_headline(events) == "2 things on today, starting at 08:20."

    def test_all_day_only_has_no_start_time(self):
        events = [event("2026-09-03", None, "Inset day", all_day=True)]
        assert computed_headline(events) == "1 thing on today."


class TestFreshBoard:
    def test_shows_the_generated_headline_and_note(self):
        view = build_view(CONFIG, payload("2026-09-03"), TODAY)
        assert view["state"] == "ready"
        assert view["stale"] is False
        assert view["headline"] == "Big morning"
        assert view["note"] == "An octopus fact"

    def test_shows_only_todays_events_in_order(self):
        data = payload("2026-09-03", [
            event("2026-09-04", "09:00", "Tomorrow"),
            event("2026-09-03", "08:20", "School run"),
        ])
        view = build_view(CONFIG, data, TODAY)
        assert [e["title"] for e in view["events"]] == ["School run"]

    def test_recomputes_chores_and_countdowns_from_config(self):
        view = build_view(CONFIG, payload("2026-09-03"), TODAY)
        assert view["chores"][0]["assigned_to"] in {"Mia", "Theo"}
        assert view["countdowns"][0]["title"] == "Christmas"


class TestStaleBoard:
    """A payload from yesterday, still on the wall this morning."""

    data = payload("2026-09-02", [
        event("2026-09-03", "08:20", "School run"),
        event("2026-09-03", "15:45", "Swimming"),
    ])

    def test_is_flagged_stale(self):
        view = build_view(CONFIG, self.data, TODAY)
        assert view["stale"] is True
        assert view["state"] == "stale"
        assert view["stale_days"] == 1

    def test_agenda_is_still_todays(self):
        # Yesterday's fetch reached 14 days ahead, so today's events are in it.
        view = build_view(CONFIG, self.data, TODAY)
        assert [e["title"] for e in view["events"]] == ["School run", "Swimming"]

    def test_chores_are_todays_not_yesterdays(self):
        view = build_view(CONFIG, self.data, TODAY)
        fresh = build_view(CONFIG, payload("2026-09-03"), TODAY)
        assert view["chores"] == fresh["chores"]

    def test_countdowns_are_todays(self):
        view = build_view(CONFIG, self.data, TODAY)
        assert view["countdowns"][0]["days"] == 113  # Christmas, from 3 September

    def test_the_stale_headline_gives_way_to_a_computed_one(self):
        # A day-old headline can be actively wrong, so it is replaced.
        view = build_view(CONFIG, self.data, TODAY)
        assert view["headline"] == "2 things on today, starting at 08:20."

    def test_the_note_survives_because_it_is_harmless(self):
        view = build_view(CONFIG, self.data, TODAY)
        assert view["note"] == "An octopus fact"


class TestTomorrow:
    """Tomorrow tops up the agenda, but only with the rows today did not use."""

    def test_a_quiet_today_is_topped_up_from_tomorrow(self):
        data = payload("2026-09-03", [
            event("2026-09-04", "09:00", "Term starts"),
            event("2026-09-04", "14:15", "Dentist"),
        ])
        view = build_view(CONFIG, data, TODAY)
        assert view["events"] == []
        assert [e["title"] for e in view["tomorrow"]] == ["Term starts", "Dentist"]

    def test_today_takes_the_rows_first(self):
        data = payload("2026-09-03", [
            event("2026-09-03", "08:20", "School run"),
            event("2026-09-03", "15:45", "Swimming"),
            event("2026-09-03", "18:00", "Football"),
            event("2026-09-04", "09:00", "Term starts"),
            event("2026-09-04", "14:15", "Dentist"),
            event("2026-09-04", "16:30", "Piano"),
        ])
        view = build_view(CONFIG, data, TODAY)
        assert len(view["events"]) == 3
        # Two rows left in the budget of five, so only two of tomorrow's three.
        assert [e["title"] for e in view["tomorrow"]] == ["Term starts", "Dentist"]

    def test_a_full_today_crowds_tomorrow_out(self):
        data = payload("2026-09-03", [
            event("2026-09-03", f"{hour:02d}:00", f"Thing {hour}")
            for hour in range(8, 13)
        ] + [event("2026-09-04", "09:00", "Term starts")])
        view = build_view(CONFIG, data, TODAY)
        assert len(view["events"]) == 5
        assert view["tomorrow"] == []

    def test_tomorrow_stays_a_footnote_on_a_completely_empty_day(self):
        # Nothing today and a packed tomorrow still reads as today's agenda.
        data = payload("2026-09-03", [
            event("2026-09-04", f"{hour:02d}:00", f"Thing {hour}")
            for hour in range(8, 13)
        ])
        view = build_view(CONFIG, data, TODAY)
        assert len(view["tomorrow"]) == 3

    def test_the_day_after_tomorrow_is_not_included(self):
        data = payload("2026-09-03", [
            event("2026-09-04", "09:00", "Term starts"),
            event("2026-09-05", "09:00", "Too far off"),
        ])
        view = build_view(CONFIG, data, TODAY)
        assert [e["title"] for e in view["tomorrow"]] == ["Term starts"]

    def test_a_stale_payload_still_knows_tomorrow(self):
        # Yesterday's fetch reached 14 days ahead, so tomorrow is in it too.
        data = payload("2026-09-02", [event("2026-09-04", "09:00", "Term starts")])
        view = build_view(CONFIG, data, TODAY)
        assert view["stale"] is True
        assert [e["title"] for e in view["tomorrow"]] == ["Term starts"]


class TestEmptyStates:
    def test_no_payload_at_all_is_the_waiting_screen(self):
        view = build_view(CONFIG, None, TODAY)
        assert view["state"] == "waiting"
        assert view["events"] == []
        assert view["tomorrow"] == []
        # Chores and countdowns still work — they never needed the model.
        assert view["chores"]
        assert view["countdowns"]

    def test_a_quiet_day_keeps_everything_else(self):
        view = build_view(CONFIG, payload("2026-09-03"), TODAY)
        assert view["events"] == []
        assert view["state"] == "ready"
        assert view["chores"]

    def test_an_agenda_with_no_brief_yet_still_shows_the_day(self):
        # A `--tick` that refreshed the calendars before brief_time leaves a
        # payload with events and no words. Reachable only since the split, and
        # the right answer is today's agenda under the amber banner rather than
        # the first-run screen.
        agenda = {"events": [event("2026-09-03", "08:20", "School run")],
                  "calendars_fetched_at": "2026-09-03T03:00:00+00:00"}
        view = build_view(CONFIG, agenda, TODAY)
        assert view["state"] == "stale"
        assert [e["title"] for e in view["events"]] == ["School run"]
        assert view["headline"] == "1 thing on today, starting at 08:20."
        assert view["note"] == ""
        assert view["stale_days"] is None


class TestTheme:
    def test_dark_is_carried_through(self):
        view = build_view(dict(CONFIG, theme="dark"), payload("2026-09-03"), TODAY)
        assert view["theme"] == "dark"

    def test_an_unknown_theme_falls_back_to_light(self):
        view = build_view(dict(CONFIG, theme="neon"), payload("2026-09-03"), TODAY)
        assert view["theme"] == "light"


class TestReloadInterval:
    """The board reloads itself on a timer, derived from `refresh_minutes`.

    Five minutes is the ceiling, so the four longer intervals all render the
    same value the template used to hard-code. Only a shorter one moves it.
    """

    def test_the_default_is_five_minutes(self):
        assert build_view(CONFIG, payload("2026-09-03"), TODAY)["reload_seconds"] == 300

    def test_a_longer_fetch_interval_does_not_slow_the_reload(self):
        config = dict(CONFIG, refresh_minutes=1440)
        assert build_view(config, payload("2026-09-03"), TODAY)["reload_seconds"] == 300

    def test_a_quarter_hourly_fetch_still_reloads_every_five_minutes(self):
        config = dict(CONFIG, refresh_minutes=15)
        assert build_view(config, payload("2026-09-03"), TODAY)["reload_seconds"] == 300

    def test_only_an_interval_under_five_minutes_pulls_it_down(self):
        config = dict(CONFIG, refresh_minutes=2)
        assert build_view(config, payload("2026-09-03"), TODAY)["reload_seconds"] == 120

    def test_the_waiting_screen_asks_more_often(self):
        # Nothing to show yet, so fill the screen in a minute rather than five.
        assert build_view(CONFIG, None, TODAY)["reload_seconds"] == 60

    def test_an_unreadable_interval_falls_back_to_five_minutes(self):
        config = dict(CONFIG, refresh_minutes="hourly")
        assert build_view(config, payload("2026-09-03"), TODAY)["reload_seconds"] == 300


class TestTheWaitingScreen:
    """What a family reads before their first board arrives.

    `board.html` is rendered from the same file in both modes and
    `tests/test_cloud_mode.py` asserts the two are byte-identical, so anything
    written here has to be true of a Raspberry Pi *and* of a wall panel in a
    kitchen. It used to say "Run `python generate.py`", which was a Pi's
    instruction on a hosted family's screen and, since DIN-45, the wrong advice
    on the Pi too — the next tick writes it either way.
    """

    @pytest.fixture
    def page(self, tmp_path):
        from dinkydash.store import FileStore
        from tests.conftest import client_for
        from web import create_app

        path = tmp_path / "config.yaml"
        path.write_text('family_name: "The Wilsons"\ntimezone: "Europe/Berlin"\n')
        client = client_for(create_app(FileStore(path)))
        return client.get("/").get_data(as_text=True)

    def test_it_is_the_waiting_screen(self, page):
        assert "first board" in page

    def test_it_names_no_command(self, page):
        # A parent reading this has no shell, and after DIN-45 nobody needs one.
        assert "generate.py" not in page

    def test_it_names_the_button_the_settings_page_actually_has(self, page):
        assert "Write it now" in page
