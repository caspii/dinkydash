"""What the dashboard shows, especially on a day the generation failed.

The design claim being tested: when a morning's run fails, the times, turns and
countdowns on the wall are still *today's*. The headline gives way to one
worked out from the day. A stored note stays on the view and is not rendered.
"""

import json
from datetime import date, datetime, timezone

import pytest

from dinkydash.board import build_view, computed_headline
from dinkydash.config import tzinfo_for

CONFIG = {
    "family_name": "The Wilsons",
    "timezone": "Europe/Berlin",  # set up: a real family's dashboard, not the starter
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


class TestTheBannerWaitsUntilTheBriefIsDue:
    """Stale is not the same as late, and only late may show the banner.

    A dashboard goes stale at local midnight; the brief is not owed until
    `brief_time`, 06:00 by default. Between the two, an amber
    "today’s note hasn’t arrived" reports a failure that has not happened —
    all night, on a screen in a kitchen. The words are still handled as stale
    throughout, because yesterday’s headline is wrong from midnight on.
    """

    data = payload("2026-09-02", [event("2026-09-03", "08:20", "School run")])

    def view_at(self, hour, minute=0, config=CONFIG, data=None):
        """The dashboard as it reads at that hour on the family’s own clock."""
        moment = datetime(2026, 9, 3, hour, minute, tzinfo=tzinfo_for(config))
        return build_view(config, self.data if data is None else data,
                          moment.date(), now=moment)

    def test_the_small_hours_claim_nothing(self):
        view = self.view_at(1, 30)
        assert view["stale"] is True      # the line on the wall is yesterday’s
        assert view["overdue"] is False   # but nothing was owed yet

    def test_after_the_brief_time_it_is_late(self):
        assert self.view_at(6, 5)["overdue"] is True

    def test_the_hour_is_the_one_the_family_chose(self):
        late = dict(CONFIG, brief_time="08:00")
        assert self.view_at(7, 0, config=late)["overdue"] is False
        assert self.view_at(8, 30, config=late)["overdue"] is True

    def test_it_is_the_family_clock_not_the_server_clock(self):
        # 23:30 UTC is 01:30 in Berlin: their night, not their morning.
        moment = datetime(2026, 9, 2, 23, 30, tzinfo=timezone.utc)
        view = build_view(CONFIG, self.data, date(2026, 9, 3), now=moment)
        assert view["overdue"] is False

    def test_more_than_a_day_behind_is_late_at_any_hour(self):
        old = payload("2026-08-30", [event("2026-09-03", "08:20", "School run")])
        assert self.view_at(1, 30, data=old)["overdue"] is True

    def test_an_agenda_with_no_brief_at_all_is_never_late(self):
        # No brief has been written, so there is no line to be behind: the
        # dashboard is the first one, under a headline worked out from the day.
        agenda = {"events": [event("2026-09-03", "08:20", "School run")],
                  "calendars_fetched_at": "2026-09-03T00:10:00+00:00"}
        for hour in (1, 7, 23):
            assert self.view_at(hour, 30, data=agenda)["overdue"] is False

    def test_todays_dashboard_is_never_late(self):
        assert self.view_at(1, 30, data=payload("2026-09-03"))["overdue"] is False

    def test_the_words_are_still_yesterdays_overnight(self):
        # The banner going quiet must not put yesterday’s headline back up:
        # "Ines starts nursery today" was wrong the moment the day changed.
        view = self.view_at(1, 30)
        assert view["headline"] == "1 thing on today, starting at 08:20."
        assert view["note"] == "An octopus fact"
        assert view["stale_days"] == 1

    def test_a_caller_with_no_clock_counts_every_stale_dashboard_as_late(self):
        assert build_view(CONFIG, self.data, TODAY)["overdue"] is True


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
    def test_no_payload_at_all_is_already_a_dashboard(self):
        view = build_view(CONFIG, None, TODAY)
        assert view["state"] == "first"
        assert view["events"] == []
        assert view["tomorrow"] == []
        # Chores and countdowns never needed the model.
        assert view["chores"]
        assert view["countdowns"]
        assert view["headline"] == "Nothing booked in today."
        assert view["overdue"] is False

    def test_a_quiet_day_keeps_everything_else(self):
        view = build_view(CONFIG, payload("2026-09-03"), TODAY)
        assert view["events"] == []
        assert view["state"] == "ready"
        assert view["chores"]

    def test_an_agenda_with_no_brief_yet_shows_the_day_without_a_banner(self):
        # A `--tick` that refreshed the calendars before the brief leaves a
        # payload with events and no words — between the two halves of a first
        # tick, or after a first brief that failed. No brief was ever written,
        # so there is nothing to call late.
        agenda = {"events": [event("2026-09-03", "08:20", "School run")],
                  "calendars_fetched_at": "2026-09-03T03:00:00+00:00"}
        view = build_view(CONFIG, agenda, TODAY)
        assert view["state"] == "first"
        assert [e["title"] for e in view["events"]] == ["School run"]
        assert view["headline"] == "1 thing on today, starting at 08:20."
        assert view["overdue"] is False
        assert view["stale"] is False

    def test_it_asks_again_sooner_than_a_written_one(self):
        # The model's line should reach the wall within a minute of being written.
        assert build_view(CONFIG, None, TODAY)["reload_seconds"] == 60
        assert build_view(CONFIG, payload("2026-09-03"), TODAY)["reload_seconds"] == 300


class TestStillSettingUp:
    """A family that is not set up yet sees the dashboard it is setting up.

    `config.is_set_up` is false while the household is still the invented
    starter or the timezone is unset. Nothing is being written for such a
    family (`schedule.brief_due`), but the turns, countdowns and agenda are
    worked out from the config, so the settings home can preview the real
    thing from the first second — invented household and all — rather than a
    screen saying "nearly there".
    """

    STARTER = {**CONFIG, "timezone": "UTC"}

    def test_no_payload_is_the_starter_dashboard(self):
        from dinkydash import config as config_module
        starter = config_module.starter_config()
        view = build_view(starter, None, TODAY)
        assert view["state"] == "first"
        assert [c["assigned_to"] for c in view["chores"]]
        assert view["countdowns"]

    def test_an_agenda_with_no_brief_shows_the_agenda(self):
        agenda = {"events": [event("2026-09-03", "08:20", "School run")],
                  "calendars_fetched_at": "2026-09-03T03:00:00+00:00"}
        view = build_view(self.STARTER, agenda, TODAY)
        assert view["state"] == "first"
        assert [e["title"] for e in view["events"]] == ["School run"]
        assert view["overdue"] is False

    def test_a_written_brief_renders_as_usual(self):
        # A brief that already exists is shown, set up or not: the family
        # that signed up before this rule still has yesterday's dashboard.
        view = build_view(self.STARTER, payload("2026-09-03"), TODAY)
        assert view["state"] == "ready"


class TestTheme:
    def test_dark_is_carried_through(self):
        view = build_view(dict(CONFIG, theme="dark"), payload("2026-09-03"), TODAY)
        assert view["theme"] == "dark"

    def test_an_unknown_theme_falls_back_to_light(self):
        view = build_view(dict(CONFIG, theme="neon"), payload("2026-09-03"), TODAY)
        assert view["theme"] == "light"


class TestLocations:
    ADDRESS = "1 High Street, London N1 1AA, UK"

    def events(self):
        return [
            dict(event("2026-09-03", "08:20", "Dentist"), location=self.ADDRESS),
            dict(event("2026-09-03", "10:00", "Parents' evening"),
                 location="Main hall", calendar="School"),
            dict(event("2026-09-04", "09:00", "Swimming"), location="Leisure centre"),
        ]

    def config(self, family_shows):
        return dict(CONFIG, calendars=[
            {"label": "Family", "url": "https://example.com/a.ics", "show_locations": family_shows},
            {"label": "School", "url": "https://example.com/b.ics"},
        ])

    def test_shown_unless_the_calendar_says_otherwise(self):
        view = build_view(self.config(True), payload("2026-09-03", self.events()), TODAY)
        assert view["events"][0]["location"] == self.ADDRESS
        view = build_view(CONFIG, payload("2026-09-03", self.events()), TODAY)
        assert view["events"][0]["location"] == self.ADDRESS

    def test_hidden_on_that_calendar_only_today_and_tomorrow(self):
        view = build_view(self.config(False), payload("2026-09-03", self.events()), TODAY)
        assert view["events"][0]["location"] is None
        assert view["events"][0]["title"] == "Dentist"
        assert view["events"][1]["location"] == "Main hall"
        assert view["tomorrow"][0]["location"] is None

    def test_the_payload_keeps_them(self):
        stored = payload("2026-09-03", self.events())
        build_view(self.config(False), stored, TODAY)
        assert stored["events"][0]["location"] == self.ADDRESS


class TestReloadInterval:
    """The dashboard reloads itself on a timer, derived from `refresh_minutes`.

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


class TestTheFirstDashboard:
    """What a screen shows before the first brief arrives: the dashboard.

    `board.html` is rendered from the same file in both modes and
    `tests/test_cloud_mode.py` asserts the two are byte-identical, so this has
    to be true of a Raspberry Pi *and* of a wall panel in a kitchen. There is
    no waiting screen: the turns and countdowns are worked out from the config,
    and the model's line replaces the stand-in headline when it is written.
    """

    def page(self, tmp_path, config):
        from dinkydash.store import FileStore
        from tests.conftest import client_for
        from web import create_app

        path = tmp_path / "config.yaml"
        path.write_text(config)
        return client_for(create_app(FileStore(path))).get("/").get_data(as_text=True)

    def test_a_set_up_family_sees_its_dashboard(self, tmp_path):
        page = self.page(tmp_path, 'family_name: "The Wilsons"\ntimezone: "Europe/Berlin"\n')
        assert '<div class="board">' in page
        assert "The Wilsons" in page
        assert "Nothing booked in today." in page
        assert "first dashboard" not in page

    def test_it_names_no_command(self, tmp_path):
        # A parent reading this has no shell, and nobody needs one.
        page = self.page(tmp_path, 'family_name: "The Wilsons"\ntimezone: "Europe/Berlin"\n')
        assert "generate.py" not in page

    def test_so_does_a_family_still_setting_up(self, tmp_path):
        # The example household is what the settings home previews.
        page = self.page(tmp_path, 'family_name: "The Wilsons"\ntimezone: "Europe/Berlin"\n'
                                   'people:\n  - name: "Mia"\n    date_of_birth: "2017-03-15"\n'
                                   '    invented: true\n')
        assert '<div class="board">' in page
        assert "Mia" in page
        assert "Nearly there" not in page


class TestTheBannerOnTheDashboard:
    """The one part of this a family reads, so the page itself is checked.

    Rendered through the real route, because that is what decides which moment
    `build_view` is given — a dashboard that knows it is 01:30 and a template
    that shows the banner anyway would pass every test above.
    """

    BANNER = "headline hasn&rsquo;t arrived"

    def page_at(self, tmp_path, monkeypatch, hour, minute=0, data=None):
        from dinkydash import config as config_module
        from dinkydash.store import FileStore
        from tests.conftest import client_for
        from web import create_app

        path = tmp_path / "config.yaml"
        path.write_text('family_name: "The Wilsons"\ntimezone: "Europe/Berlin"\n')
        (tmp_path / "dashboard_data.json").write_text(json.dumps(data or
            payload("2026-09-02", [event("2026-09-03", "08:20", "School run")])))
        moment = datetime(2026, 9, 3, hour, minute,
                          tzinfo=tzinfo_for({"timezone": "Europe/Berlin"}))
        monkeypatch.setattr(config_module, "now_for", lambda _: moment)
        return client_for(create_app(FileStore(path))).get("/").get_data(as_text=True)

    def test_the_night_is_quiet(self, tmp_path, monkeypatch):
        page = self.page_at(tmp_path, monkeypatch, 1, 30)
        assert self.BANNER not in page
        assert "An octopus fact" not in page

    def test_the_morning_says_the_headline_was_worked_out(self, tmp_path, monkeypatch):
        page = self.page_at(tmp_path, monkeypatch, 7, 0)
        assert self.BANNER in page
        assert "worked out from the day" in page
        assert "An octopus fact" not in page
        assert "Yesterday&rsquo;s note" not in page

    def test_an_older_brief_still_renders_without_its_note(self, tmp_path, monkeypatch):
        old = payload("2026-08-30", [event("2026-09-03", "08:20", "School run")])
        page = self.page_at(tmp_path, monkeypatch, 7, 0, data=old)
        assert "School run" in page
        assert "An octopus fact" not in page
        assert "Older note" not in page
        assert "Yesterday" not in page

    def test_an_agenda_with_no_brief_shows_no_banner(self, tmp_path, monkeypatch):
        agenda = {"events": [event("2026-09-03", "08:20", "School run")],
                  "calendars_fetched_at": "2026-09-03T00:10:00+00:00"}
        page = self.page_at(tmp_path, monkeypatch, 7, 0, data=agenda)
        assert self.BANNER not in page
        assert "School run" in page


class TestTheFactOfTheDayIsNotShown:
    """A stored note must not come back onto the dashboard.

    The brief can still carry one — an older file, an export, a row written
    before the dashboard stopped asking for it — and the page has to render
    the rest of that brief without printing the note.
    """

    def test_a_fresh_dashboard_drops_the_note(self, tmp_path, monkeypatch):
        from dinkydash import config as config_module
        from dinkydash.store import FileStore
        from tests.conftest import client_for
        from web import create_app

        path = tmp_path / "config.yaml"
        path.write_text(
            'family_name: "The Wilsons"\ntimezone: "Europe/Berlin"\n'
            'people:\n  - name: "Mia"\n    date_of_birth: "2017-03-15"\n'
            'recurring:\n  - title: "Set the table"\n    emoji: "🍽"\n'
            '    choices: ["Mia"]\n'
        )
        (tmp_path / "dashboard_data.json").write_text(json.dumps(payload(
            "2026-09-03",
            [event("2026-09-03", "08:20",
                   "A very long appointment title that has to wrap on a narrow column")],
            headline="Big morning",
            note="Did you know? Violins are made from over 70 separate pieces of wood.",
        )))
        moment = datetime(2026, 9, 3, 9, 0,
                          tzinfo=tzinfo_for({"timezone": "Europe/Berlin"}))
        monkeypatch.setattr(config_module, "now_for", lambda _: moment)
        page = client_for(create_app(FileStore(path))).get("/").get_data(as_text=True)
        assert "Big morning" in page
        assert "A very long appointment title that has to wrap" in page
        assert "Set the table" in page
        assert "Did you know?" not in page
        assert "Violins are made" not in page
        assert 'class="note' not in page
        # The title is allowed to wrap; it is not clipped in the markup.
        assert "overflow-wrap: break-word" in page
