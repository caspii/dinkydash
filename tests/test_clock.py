"""The 12-hour clock, and the four places a time is written.

The design claim being tested: a time is *stored* in one shape and written for a
reader at the point of display. So changing the setting shows on the next
redraw, not on the next calendar fetch — and every place that prints a time
agrees with every other, including the line the model writes.
"""

import json
import pathlib
from datetime import date, datetime, time

import pytest

from dinkydash import config as config_module
from dinkydash.board import build_view
from dinkydash.clock import DEFAULT_CLOCK, clock_of, format_time
from dinkydash.prompt import build_user_prompt
from dinkydash.store import FileStore
from tests.conftest import client_for
from web import create_app

REPO = pathlib.Path(__file__).resolve().parent.parent
BOARD = REPO / "web" / "templates" / "board.html"

TODAY = date(2026, 9, 17)

CONFIG = """\
family_name: "The Wilsons"
timezone: "Europe/Berlin"

people:
  - name: "Mia"
    date_of_birth: "2017-03-15"

recurring:
  - title: "Set the table"
    choices: ["Mia", "Theo"]
"""


def event(time_, title, all_day=False):
    day = TODAY.isoformat()
    return {
        "title": title, "date": day, "time": None if all_day else time_,
        "all_day": all_day, "start": f"{day}T{time_ or '00:00'}:00+02:00",
        "location": None, "calendar": "Family",
    }


def payload(events):
    return {
        "generated_for_date": TODAY.isoformat(),
        "generated_at": f"{TODAY}T04:32:00+00:00",
        "headline": "Big morning", "note": "An octopus fact",
        "note_kind": "fact", "events": events,
    }


def board_config(clock):
    return {"family_name": "The Wilsons", "timezone": "Europe/Berlin",
            "clock": clock, "people": [], "recurring": []}


class TestFormatTime:
    @pytest.mark.parametrize("hhmm, written", [
        ("00:00", "12:00 am"),   # midnight is 12, not 0 — the whole reason for %-I
        ("00:07", "12:07 am"),
        ("09:05", "9:05 am"),    # no leading zero on the hour
        ("11:59", "11:59 am"),
        ("12:00", "12:00 pm"),   # noon is pm, and is 12 rather than 0
        ("12:30", "12:30 pm"),
        ("13:00", "1:00 pm"),
        ("15:45", "3:45 pm"),
        ("23:59", "11:59 pm"),
    ])
    def test_twelve_hour(self, hhmm, written):
        assert format_time(f"{TODAY}T{hhmm}:00+02:00", "12h") == written

    def test_twenty_four_hour_keeps_the_leading_zero(self):
        assert format_time(f"{TODAY}T08:20:00+02:00", "24h") == "08:20"

    def test_the_default_is_twenty_four_hour(self):
        assert format_time(f"{TODAY}T15:45:00+02:00") == "15:45"

    def test_it_takes_a_datetime_a_time_or_a_string(self):
        assert format_time(datetime(2026, 9, 17, 15, 45), "12h") == "3:45 pm"
        assert format_time(time(15, 45), "12h") == "3:45 pm"
        # An already-formatted time, which is what a stored event carries when
        # it predates `start`.
        assert format_time("15:45", "12h") == "3:45 pm"

    def test_nothing_readable_is_none(self):
        assert format_time(None) is None
        assert format_time("") is None
        assert format_time("some time on Tuesday") is None


class TestWhichClock:
    def test_unset_is_twenty_four_hour(self):
        assert clock_of({}) == DEFAULT_CLOCK == "24h"

    def test_a_value_nobody_recognises_is_twenty_four_hour(self):
        # A hand-edited file or a jsonb column can hold anything at all, and an
        # unrecognised value must not reach a formatter.
        assert clock_of({"clock": "am/pm"}) == "24h"
        assert clock_of({"clock": None}) == "24h"
        assert clock_of(None) == "24h"

    def test_the_config_default_and_its_coercion(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text('family_name: "The Wilsons"\nclock: "nonsense"\n')
        assert config_module.load_config(path)["clock"] == "24h"

    def test_a_real_setting_survives_a_load(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text('family_name: "The Wilsons"\nclock: "12h"\n')
        assert config_module.load_config(path)["clock"] == "12h"


class TestTheAgendaOnTheWall:
    def test_todays_events_are_on_the_familys_clock(self):
        view = build_view(board_config("12h"),
                          payload([event("08:20", "School run"),
                                   event("15:45", "Swimming")]), TODAY)
        assert [e["time"] for e in view["events"]] == ["8:20 am", "3:45 pm"]

    def test_tomorrow_is_too(self):
        tomorrow = dict(event("17:30", "Cubs"), date="2026-09-18",
                        start="2026-09-18T17:30:00+02:00")
        view = build_view(board_config("12h"), payload([tomorrow]), TODAY)
        assert [e["time"] for e in view["tomorrow"]] == ["5:30 pm"]

    def test_all_day_events_are_untouched(self):
        view = build_view(board_config("12h"),
                          payload([event(None, "Inset day", all_day=True)]), TODAY)
        assert view["events"][0]["time"] is None

    def test_the_default_is_unchanged(self):
        view = build_view(board_config("24h"),
                          payload([event("15:45", "Swimming")]), TODAY)
        assert view["events"][0]["time"] == "15:45"

    def test_the_stored_payload_is_not_rewritten(self):
        # The stored shape is one shape in both modes. Rewriting it here would
        # make the setting a property of the last fetch rather than of the
        # family, and would reach the store through a caller holding the dict.
        stored = payload([event("15:45", "Swimming")])
        build_view(board_config("12h"), stored, TODAY)
        assert stored["events"][0]["time"] == "15:45"

    def test_the_setting_applies_without_a_fresh_fetch(self):
        # The same payload, rendered twice. This is the whole reason the
        # rewrite lives here and not in `calendars._events`.
        stored = payload([event("15:45", "Swimming")])
        assert build_view(board_config("24h"), stored, TODAY)["events"][0]["time"] == "15:45"
        assert build_view(board_config("12h"), stored, TODAY)["events"][0]["time"] == "3:45 pm"

    def test_an_event_with_no_start_still_renders(self):
        # A payload written before events carried `start`. Its `%H:%M` is all
        # there is, and it is enough.
        old = event("15:45", "Swimming")
        del old["start"]
        view = build_view(board_config("12h"), payload([old]), TODAY)
        assert view["events"][0]["time"] == "3:45 pm"


class TestTheComputedHeadline:
    """The stale-day headline quotes the first time, so it follows the setting."""

    def test_on_a_twelve_hour_dashboard(self):
        stale = payload([event("08:20", "School run")])
        stale["generated_for_date"] = "2026-09-16"
        view = build_view(board_config("12h"), stale, TODAY)
        assert view["headline"] == "1 thing on today, starting at 8:20 am."

    def test_on_a_twenty_four_hour_one(self):
        stale = payload([event("08:20", "School run")])
        stale["generated_for_date"] = "2026-09-16"
        view = build_view(board_config("24h"), stale, TODAY)
        assert view["headline"] == "1 thing on today, starting at 08:20."


class TestWhatTheModelIsTold:
    """The model quotes these times back into the headline it writes."""

    def prompt_for(self, clock):
        return build_user_prompt(
            board_config(clock), TODAY,
            [event("15:45", "Swimming"), event(None, "Inset day", all_day=True)],
            [], [], [], [], "fact",
        )

    def test_twelve_hour(self):
        text = self.prompt_for("12h")
        assert "- 3:45 pm: Swimming" in text
        assert "15:45" not in text

    def test_twenty_four_hour(self):
        assert "- 15:45: Swimming" in self.prompt_for("24h")

    def test_all_day_is_unchanged(self):
        assert "- All day: Inset day" in self.prompt_for("12h")


class TestTheSettingsPage:
    @pytest.fixture
    def config_path(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(CONFIG)
        return path

    @pytest.fixture
    def client(self, config_path):
        return client_for(create_app(FileStore(config_path)))

    def test_the_form_offers_both_with_the_real_format_beside_them(self, client):
        page = client.get("/settings/system").get_data(as_text=True)
        # The example is produced by the formatter itself, so it cannot drift
        # from what the dashboard prints.
        assert "24-hour (15:45)" in page
        assert "12-hour (3:45 pm)" in page

    def test_saving_it(self, client, config_path):
        client.post("/settings/system", data={
            "family_name": "The Wilsons", "timezone": "Europe/Berlin",
            "location": "", "clock": "12h"})
        assert config_module.load_config(config_path)["clock"] == "12h"

    def test_a_value_the_form_does_not_offer_is_ignored(self, client, config_path):
        client.post("/settings/system", data={
            "family_name": "The Wilsons", "timezone": "Europe/Berlin",
            "location": "", "clock": "swatch beats"})
        assert config_module.load_config(config_path)["clock"] == "24h"

    def test_the_status_line_follows_it(self, client, config_path, tmp_path):
        client.post("/settings/system", data={
            "family_name": "The Wilsons", "timezone": "Europe/Berlin",
            "location": "", "clock": "12h"})
        today = config_module.today_for(config_module.load_config(config_path))
        (tmp_path / "dashboard_data.json").write_text(json.dumps({
            "generated_for_date": today.isoformat(),
            "generated_at": f"{today}T04:07:00+00:00",
            "headline": "Hi", "note": "There", "events": []}))
        # 04:07 UTC is 06:07 in Berlin in September.
        assert "written 6:07 am" in client.get("/settings/").get_data(as_text=True)


class TestTheDashboardsOwnChrome:
    """The time column is a fixed width, so the page has to know which clock."""

    @pytest.fixture
    def config_path(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(CONFIG.replace('timezone: "Europe/Berlin"',
                                       'timezone: "Europe/Berlin"\nclock: "12h"'))
        return path

    @pytest.fixture
    def client(self, config_path, tmp_path):
        (tmp_path / "dashboard_data.json").write_text(json.dumps(
            payload([event("15:45", "Swimming")])))
        return client_for(create_app(FileStore(config_path)))

    def test_the_clock_is_on_the_html_element(self, client):
        # `--time-column` hangs off it: "12:00 pm" does not fit the width
        # "12:00" needs, and the column does not shrink.
        assert 'data-clock="12h"' in client.get("/").get_data(as_text=True)

    def test_the_refresh_carries_it_across(self):
        # A refresh swaps the <body> and keeps the <head> — and <html>, which
        # is where both this and the theme live. A swap that forgot it would
        # draw the new times in the old column and cut them off.
        swap = BOARD.read_text()
        swap = swap[swap.index("function swap(next)"):]
        swap = swap[:swap.index("fit();")]
        assert 'setAttribute("data-clock"' in swap
        assert 'setAttribute("data-theme"' in swap

    def test_the_time_column_is_a_token_with_both_widths(self):
        css = BOARD.read_text()
        assert "--time-column:" in css
        assert '[data-clock="12h"] { --time-column:' in css
        # The rule reads the token rather than either literal width.
        assert "width: var(--time-column);" in css


class TestTheCadenceLine:
    """The settings home says when the daily message is written, in prose."""

    @pytest.fixture
    def config_path(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(CONFIG + '\nbrief_time: "06:00"\nclock: "12h"\n')
        return path

    @pytest.fixture
    def client(self, config_path):
        return client_for(create_app(FileStore(config_path)))

    def test_the_prose_follows_the_setting(self, client):
        assert "daily message at 6:00 am" in client.get("/settings/").get_data(as_text=True)

    def test_the_form_still_posts_the_wire_format(self, client):
        # `<input type="time">` takes "HH:MM" whatever the reader sees; it is
        # the browser that draws it in their locale. Writing "6:00 am" into the
        # value attribute would empty the control.
        page = client.get("/settings/refresh").get_data(as_text=True)
        assert 'id="brief_time" name="brief_time" value="06:00"' in page
