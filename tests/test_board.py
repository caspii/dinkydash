"""What the board shows, especially on a day the generation failed.

The design claim being tested: when a morning's run fails, the times, turns and
countdowns on the wall are still *today's* — only the written line is old.
"""

from datetime import date

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


class TestEmptyStates:
    def test_no_payload_at_all_is_the_waiting_screen(self):
        view = build_view(CONFIG, None, TODAY)
        assert view["state"] == "waiting"
        assert view["events"] == []
        # Chores and countdowns still work — they never needed the model.
        assert view["chores"]
        assert view["countdowns"]

    def test_a_quiet_day_keeps_everything_else(self):
        view = build_view(CONFIG, payload("2026-09-03"), TODAY)
        assert view["events"] == []
        assert view["state"] == "ready"
        assert view["chores"]


class TestTheme:
    def test_dark_is_carried_through(self):
        view = build_view(dict(CONFIG, theme="dark"), payload("2026-09-03"), TODAY)
        assert view["theme"] == "dark"

    def test_an_unknown_theme_falls_back_to_light(self):
        view = build_view(dict(CONFIG, theme="neon"), payload("2026-09-03"), TODAY)
        assert view["theme"] == "light"
