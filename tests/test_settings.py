"""The settings routes, which are the only thing that writes config.yaml.

The claim being tested: an item's URL means the same person tomorrow as it did
when the page was rendered. It used to be a list position, so deleting anyone
above shifted everybody below onto somebody else's edit form.
"""

import json
import re
from datetime import date, timedelta

import pytest

from dinkydash import config as config_module
from dinkydash.store import FileStore
from tests.conftest import client_for
from web import create_app

CONFIG = """\
family_name: "The Wilsons"
timezone: "Europe/Berlin"

people:
  - name: "Mia"
    date_of_birth: "2017-03-15"
  - name: "Theo"
    date_of_birth: "2019-06-20"
  - name: "Ines"
    date_of_birth: "2022-01-09"

recurring:
  - title: "Set the table"
    choices: ["Mia", "Theo"]
  - title: "Feed the dog"
    choices: ["Theo", "Mia"]
"""


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(CONFIG)
    return path


@pytest.fixture
def client(config_path):
    """The app over that config, handed the store rather than finding one."""
    return client_for(create_app(FileStore(config_path)))


def people(config_path):
    return config_module.load_config(config_path)["people"]


def ids_for(config_path, key="people"):
    return [item["id"] for item in config_module.load_config(config_path)[key]]


class TestBackfill:
    def test_opening_a_list_gives_the_file_ids(self, client, config_path):
        assert "id" not in people(config_path)[0]
        assert client.get("/settings/people").status_code == 200
        assert all(p["id"] for p in people(config_path))

    def test_the_ids_do_not_change_on_a_second_visit(self, client, config_path):
        client.get("/settings/people")
        first = ids_for(config_path)
        client.get("/settings/people")
        assert ids_for(config_path) == first

    def test_the_list_links_to_ids_not_positions(self, client, config_path):
        html = client.get("/settings/people").get_data(as_text=True)
        for person_id in ids_for(config_path):
            assert f"/settings/people/{person_id}" in html


class TestEditing:
    def test_an_edit_form_opens_by_id(self, client, config_path):
        client.get("/settings/people")
        theo = ids_for(config_path)[1]
        page = client.get(f"/settings/people/{theo}").get_data(as_text=True)
        assert "Theo" in page

    def test_saving_keeps_the_id(self, client, config_path):
        client.get("/settings/people")
        theo = ids_for(config_path)[1]
        client.post(f"/settings/people/{theo}",
                    data={"name": "Theodore", "date_of_birth": "2019-06-20"})
        after = people(config_path)
        assert after[1]["name"] == "Theodore"
        assert after[1]["id"] == theo

    def test_a_new_person_gets_an_id_of_their_own(self, client, config_path):
        client.get("/settings/people")
        before = set(ids_for(config_path))
        client.post("/settings/people/new",
                    data={"name": "Otto", "date_of_birth": "2024-04-02"})
        after = ids_for(config_path)
        assert len(after) == 4
        assert after[3] not in before

    def test_an_unknown_id_is_a_404(self, client, config_path):
        client.get("/settings/people")
        assert client.get("/settings/people/nosuchid").status_code == 404


class TestDatesOfBirth:
    """A browser's date input accepts any year from 0001, and a flick of the
    year wheel on a phone saved "0017-03-04" without complaint — the People
    page then read "2009 years old". The form refuses what cannot be a date of
    birth, and says which year it received."""

    def test_a_year_before_1900_is_refused(self, client, config_path):
        client.get("/settings/people")
        page = client.post("/settings/people/new",
                           data={"name": "Otto", "date_of_birth": "0017-03-04"})
        assert page.status_code == 200
        assert "Date of birth has the year 0017" in page.get_data(as_text=True)
        assert len(people(config_path)) == 3

    def test_a_date_in_the_future_is_refused(self, client, config_path):
        client.get("/settings/people")
        # Two days on: the family's date is in Berlin, this machine's may not be.
        soon = (date.today() + timedelta(days=2)).isoformat()
        page = client.post("/settings/people/new",
                           data={"name": "Otto", "date_of_birth": soon})
        assert "Date of birth is in the future" in page.get_data(as_text=True)
        assert len(people(config_path)) == 3

    def test_a_baby_born_today_is_fine(self, client, config_path):
        client.get("/settings/people")
        today = config_module.today_for(config_module.load_config(config_path))
        client.post("/settings/people/new",
                    data={"name": "Otto", "date_of_birth": today.isoformat()})
        assert len(people(config_path)) == 4

    def test_a_shape_that_is_not_a_date_is_still_refused(self, client, config_path):
        client.get("/settings/people")
        page = client.post("/settings/people/new",
                           data={"name": "Otto", "date_of_birth": "17-03-04"})
        assert "should look like 2017-03-15" in page.get_data(as_text=True)
        assert len(people(config_path)) == 3

    def test_a_stored_bad_year_must_be_fixed_before_the_person_saves(self, tmp_path):
        # The remediation path for a row that got in before the check existed:
        # renaming the person is refused until the year is corrected.
        path = tmp_path / "config.yaml"
        path.write_text(CONFIG.replace('"2019-06-20"', '"0978-06-20"'))
        client = client_for(create_app(FileStore(path)))
        client.get("/settings/people")
        theo = ids_for(path)[1]
        page = client.post(f"/settings/people/{theo}",
                           data={"name": "Theodore", "date_of_birth": "0978-06-20"})
        assert "Date of birth has the year 0978" in page.get_data(as_text=True)
        assert people(path)[1]["name"] == "Theo"

    def test_the_input_carries_the_same_bounds(self, client, config_path):
        client.get("/settings/people")
        today = config_module.today_for(config_module.load_config(config_path))
        page = client.get("/settings/people/new").get_data(as_text=True)
        assert 'min="1900-01-01"' in page
        assert f'max="{today.isoformat()}"' in page


class TestDeleting:
    def test_delete_removes_the_named_person(self, client, config_path):
        client.get("/settings/people")
        theo = ids_for(config_path)[1]
        client.post(f"/settings/people/{theo}/delete", data={"confirmed": "yes"})
        assert [p["name"] for p in people(config_path)] == ["Mia", "Ines"]

    def test_a_deletion_does_not_move_anyone_elses_url(self, client, config_path):
        # The bug this whole change exists to prevent: with positions, removing
        # Mia turned Theo's open edit form into Ines's.
        client.get("/settings/people")
        mia, _theo, ines = ids_for(config_path)
        client.post(f"/settings/people/{mia}/delete", data={"confirmed": "yes"})
        page = client.get(f"/settings/people/{ines}").get_data(as_text=True)
        assert "Ines" in page

    def test_deleting_a_stranger_is_a_404(self, client, config_path):
        client.get("/settings/people")
        assert client.post("/settings/people/nosuchid/delete", data={"confirmed": "yes"}).status_code == 404


class TestReordering:
    """Moving a chore changes its display position, not its participant rotation."""

    def test_moving_down_swaps_with_the_next_one(self, client, config_path):
        client.get("/settings/recurring")
        first = ids_for(config_path, "recurring")[0]
        client.post(f"/settings/recurring/{first}/move", data={"direction": "down"})
        titles = [c["title"] for c in config_module.load_config(config_path)["recurring"]]
        assert titles == ["Feed the dog", "Set the table"]

    def test_moving_the_top_one_up_does_nothing(self, client, config_path):
        client.get("/settings/recurring")
        first = ids_for(config_path, "recurring")[0]
        client.post(f"/settings/recurring/{first}/move", data={"direction": "up"})
        titles = [c["title"] for c in config_module.load_config(config_path)["recurring"]]
        assert titles == ["Set the table", "Feed the dog"]

    def test_moving_a_stranger_is_a_404(self, client, config_path):
        client.get("/settings/recurring")
        assert client.post("/settings/recurring/nosuchid/move",
                           data={"direction": "up"}).status_code == 404


class TestHomeScreen:
    """Saving either page to a phone: the icon, the name, and the two manifests.

    The dashboard's manifest lives on the dashboard blueprint, but it is tested here
    because this is where the Flask client is.
    """

    def test_the_manifest_is_not_swallowed_by_the_section_routes(self, client):
        # `/settings/<section_name>` would happily match "manifest.webmanifest"
        # and 404 it, if Werkzeug preferred the dynamic rule.
        response = client.get("/settings/manifest.webmanifest")
        assert response.status_code == 200
        assert response.mimetype == "application/manifest+json"

    def test_the_saved_settings_link_has_a_name_and_opens_at_settings(self, client):
        manifest = client.get("/settings/manifest.webmanifest").get_json(force=True)
        assert manifest["short_name"] == "DinkyDash"
        assert manifest["start_url"] == "/settings/"
        assert "The Wilsons" in manifest["description"]

    def test_the_board_is_a_second_app_not_the_same_one(self, client):
        # Share an id and the phone treats them as one app: saving the dashboard
        # would quietly replace the settings icon.
        board = client.get("/manifest.webmanifest").get_json(force=True)
        settings = client.get("/settings/manifest.webmanifest").get_json(force=True)
        assert board["id"] != settings["id"]
        assert board["start_url"] == "/"
        assert board["name"] == "The Wilsons"
        assert board["display"] == "fullscreen"

    def test_every_icon_the_manifest_promises_is_really_there(self, client):
        manifest = client.get("/settings/manifest.webmanifest").get_json(force=True)
        assert {icon["purpose"] for icon in manifest["icons"]} == {"any", "maskable"}
        for icon in manifest["icons"]:
            assert client.get(icon["src"]).status_code == 200, icon["src"]

    def test_the_settings_page_points_at_its_icon_and_manifest(self, client):
        page = client.get("/settings/").get_data(as_text=True)
        assert '<link rel="manifest" href="/settings/manifest.webmanifest">' in page
        # iOS reads none of the manifest; this link and the title meta are all
        # it has to go on.
        assert 'rel="apple-touch-icon"' in page
        assert '<meta name="apple-mobile-web-app-title" content="DinkyDash">' in page
        assert client.get("/static/apple-touch-icon.png").status_code == 200


class TestTheClockOnTheStatusLine:
    """Stamps are stored in UTC; the family reads their own clock."""

    @pytest.fixture
    def config_path(self, tmp_path):
        # Kolkata is UTC+05:30 in every month of the year. Berlin would make
        # these assertions pass in summer and fail in winter, and the half hour
        # means no accidental slice of the ISO string can look like a pass.
        path = tmp_path / "config.yaml"
        path.write_text(CONFIG.replace('timezone: "Europe/Berlin"',
                                       'timezone: "Asia/Kolkata"'))
        return path

    @pytest.fixture
    def board(self, tmp_path, config_path):
        def _write(payload):
            (tmp_path / "dashboard_data.json").write_text(json.dumps(payload))
        return _write

    @pytest.fixture
    def today(self, config_path):
        """Today on the family's clock — the same question the page asks."""
        return config_module.today_for(config_module.load_config(config_path)).isoformat()

    def test_a_utc_stamp_is_shown_in_the_familys_timezone(self, client, board, today):
        board({"generated_for_date": today, "generated_at": f"{today}T04:07:00+00:00",
               "headline": "Hi", "note": "There", "events": []})
        page = client.get("/settings/").get_data(as_text=True)
        # 04:07 UTC is 09:37 in Kolkata, whatever the server thinks the time is.
        assert "written 09:37" in page

    def test_the_calendar_refresh_is_shown_too(self, client, board, today):
        board({"generated_for_date": today, "generated_at": f"{today}T04:00:00+00:00",
               "calendars_fetched_at": f"{today}T12:30:00+00:00",
               "headline": "Hi", "note": "There", "events": []})
        assert "Calendars refreshed 18:00" in client.get("/settings/").get_data(as_text=True)

    def test_an_agenda_with_no_brief_yet_is_still_waiting(self, client, board, today):
        # Events, no words: the state between the two halves of a first tick,
        # or after a brief that failed. The family is set up, so this is the
        # last step of the checklist — and the page must not claim a dashboard it
        # hasn't got.
        board({"calendars_fetched_at": f"{today}T05:00:00+00:00", "events": []})
        page = client.get("/settings/").get_data(as_text=True)
        assert "dashboard is up" not in page
        assert "Rewrite daily message" not in page
        assert "from None" not in page

    def test_the_button_offers_a_first_board_rather_than_a_rewrite(self, client, board, today):
        """The waiting screen points at this button by name, so they must agree.

        "Rewrite daily message" is the wrong word for a dashboard nobody has written, and
        `board.html` — which is byte-identical in both modes — tells a family
        to press "Write first daily message" (DIN-45).
        """
        board({"calendars_fetched_at": f"{today}T05:00:00+00:00", "events": []})
        page = client.get("/settings/").get_data(as_text=True)
        assert "Write first daily message" in page
        assert "Rewrite daily message" not in page

    def test_and_goes_back_to_a_rewrite_once_there_is_one(self, client, board, today):
        board({"generated_for_date": today, "generated_at": f"{today}T04:00:00+00:00",
               "headline": "Hi", "note": "There", "events": []})
        page = client.get("/settings/").get_data(as_text=True)
        assert "Rewrite daily message" in page
        assert "Write first daily message" not in page

    def test_an_unreadable_stamp_does_not_break_the_page(self, client, board, today):
        board({"generated_for_date": today, "generated_at": "who knows",
               "headline": "Hi", "note": "There", "events": []})
        assert "written earlier" in client.get("/settings/").get_data(as_text=True)


CADENCE_CONFIG = """\
# What the family is called.
family_name: "The Wilsons"
timezone: "Europe/Berlin"

# How often --tick re-fetches the calendars.
refresh_minutes: 60

# When --tick writes the daily brief, on your own clock.
brief_time: "06:00"

people:
  - id: mia12345
    name: "Mia"
    date_of_birth: "2017-03-15"
"""


STARTER_CONFIG = """\
family_name: "Our family"
timezone: "UTC"
people:
  - id: mia12345
    name: "Mia"
    date_of_birth: "2017-03-15"
    invented: true
  - id: theo1234
    name: "Theo"
    date_of_birth: "2019-06-20"
    invented: true
pets:
  - id: dog12345
    name: "Biscuit"
    type: "dog"
    invented: true
recurring:
  - id: job12345
    title: "Set the table"
    choices: ["Mia", "Theo"]
"""


class TestTheWayBackFromTheBoard:
    """The dashboard is the wall panel and has no link out. Opened in the same tab
    from a settings page saved to a phone's home screen — no address bar, and
    on an iPhone no Back button — it was a dead end, and the way out was to
    force-quit the app. So it opens in its own tab, which every client knows
    how to leave, and nothing has to be drawn on the dashboard itself."""

    @pytest.fixture
    def written(self, tmp_path, config_path):
        """A dashboard for today, so the home page shows the daily card."""
        today = config_module.today_for(config_module.load_config(config_path))
        (tmp_path / "dashboard_data.json").write_text(json.dumps({
            "generated_for_date": today.isoformat(), "headline": "Hi",
            "note": "There", "events": []}))

    def test_both_links_to_the_board_open_their_own_tab(self, client, written):
        page = client.get("/settings/").get_data(as_text=True)
        links = [a for a in re.findall(r"<a [^>]*>", page) if 'href="/"' in a]
        assert len(links) == 2, links  # "Dashboard" in the app bar, and "View dashboard"
        for link in links:
            assert 'target="_blank"' in link and 'rel="noopener"' in link

    def test_the_board_itself_has_no_way_back_to_draw(self, client, written):
        """The panel is the same page. A link out on it would sit on the wall,
        and hosted it would land a panel with no session on the login page."""
        board = client.get("/").get_data(as_text=True)
        assert "/settings" not in board

    def test_a_self_hoster_gets_no_screen_link_button(self, client, written):
        """Their dashboard is at / on the host they are already on, and the
        Colours page says so. The button is for the hosted address."""
        page = client.get("/settings/").get_data(as_text=True)
        assert "Screen link" not in page


class TestTheSetUpChecklist:
    """What the settings home is until the family is set up and its dashboard written.

    The example file's household, in single mode — the same state a hosted
    family is created in (`tests/test_signup.py` covers that side). The daily
    controls are not offered: nothing to refresh, no dashboard worth viewing, and
    nothing worth writing until the answers are real.
    """

    @pytest.fixture
    def config_path(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(STARTER_CONFIG)
        return path

    def home(self, client):
        return client.get("/settings/").get_data(as_text=True)

    def loaded(self, config_path):
        return config_module.load_config(config_path)

    def make_it_theirs(self, client):
        """Steps one and two, the way a person would do them."""
        client.post("/settings/people/mia12345",
                    data={"name": "Anna", "date_of_birth": "2018-05-02"})
        client.post("/settings/people/theo1234/delete", data={"confirmed": "yes"})
        client.post("/settings/pets/dog12345/delete", data={"confirmed": "yes"})
        client.post("/settings/timezone", data={"timezone": "Europe/Berlin"})

    def test_it_replaces_the_daily_controls(self, client):
        page = self.home(client)
        assert "Set up your dashboard" in page
        for button in ("Refresh calendars", "View dashboard", "Rewrite daily message",
                       "Write first daily message", ">Dashboard<"):
            assert button not in page

    def test_step_one_names_what_is_invented(self, client):
        page = self.home(client)
        assert "Mia, Theo and Biscuit are invented" in page
        assert 'href="/settings/people"' in page

    def test_the_steps_come_in_order(self, client):
        page = self.home(client)
        assert page.index("Who lives here") < page.index("Time zone") \
            < page.index("A calendar") < page.index("Put it on the screen")

    def test_nothing_nags_about_the_home_screen_yet(self, client):
        assert "install-nudge" not in self.home(client)

    def test_the_lists_mark_who_is_invented(self, client):
        people = client.get("/settings/people").get_data(as_text=True)
        assert people.count("Invented") == 2
        pets = client.get("/settings/pets").get_data(as_text=True)
        assert pets.count("Invented") == 1

    def test_and_stop_once_they_are_saved(self, client):
        client.post("/settings/people/mia12345",
                    data={"name": "Mia", "date_of_birth": "2017-03-15"})
        assert client.get("/settings/people").get_data(as_text=True).count("Invented") == 1

    def test_saving_a_person_makes_them_yours(self, client, config_path):
        client.post("/settings/people/mia12345",
                    data={"name": "Anna", "date_of_birth": "2018-05-02"})
        assert "Theo and Biscuit are invented" in self.home(client)
        assert "invented" not in self.loaded(config_path)["people"][0]

    def test_and_their_chores_follow_the_new_name(self, client, config_path):
        client.post("/settings/people/mia12345",
                    data={"name": "Anna", "date_of_birth": "2017-03-15"})
        assert self.loaded(config_path)["recurring"][0]["choices"] == ["Anna", "Theo"]

    def test_removing_a_person_takes_them_out_of_the_rotation(self, client, config_path):
        client.post("/settings/people/theo1234/delete", data={"confirmed": "yes"})
        assert self.loaded(config_path)["recurring"][0]["choices"] == ["Mia"]

    def test_a_rotation_left_empty_is_said_on_the_chores_row(self, client, config_path):
        client.post("/settings/people/mia12345/delete", data={"confirmed": "yes"})
        client.post("/settings/people/theo1234/delete", data={"confirmed": "yes"})
        assert "1 with nobody assigned" in self.home(client)
        assert self.loaded(config_path)["recurring"][0]["choices"] == []

    def test_the_chores_row_names_the_jobs(self, client):
        # So a starter job left behind is visible from the home page.
        assert "Set the table" in self.home(client)

    def test_the_time_zone_is_one_tap_away(self, client, config_path):
        page = self.home(client)
        assert 'id="tz-offer"' in page and 'action="/settings/timezone"' in page
        landed = client.post("/settings/timezone", data={"timezone": "Europe/Berlin"},
                             follow_redirects=True).get_data(as_text=True)
        assert "Time zone set to Europe/Berlin." in landed
        assert self.loaded(config_path)["timezone"] == "Europe/Berlin"
        assert 'id="tz-offer"' not in landed  # done, so no longer offered

    def test_a_made_up_zone_is_refused(self, client, config_path):
        landed = client.post("/settings/timezone", data={"timezone": "Mars/Olympus"},
                             follow_redirects=True).get_data(as_text=True)
        assert "not a time zone this dashboard knows" in landed
        assert self.loaded(config_path)["timezone"] == "UTC"

    def test_the_screen_step_waits_for_the_first_two(self, client):
        client.post("/settings/timezone", data={"timezone": "Europe/Berlin"})
        page = self.home(client)
        assert "Once the first two steps are done" in page
        assert "Write first daily message" not in page

    def test_then_the_link_and_the_button_arrive(self, client):
        self.make_it_theirs(client)
        page = self.home(client)
        assert "Open the link below" in page
        assert "http://localhost/" in page  # single mode: the dashboard is at /
        assert "Copy link" in page  # and a button to get it onto the other device
        assert "Write first daily message" in page
        assert "Anna" in page  # step one, done, names who is here

    def test_a_calendar_is_not_required_to_finish(self, client):
        self.make_it_theirs(client)
        page = self.home(client)
        assert "None yet. The dashboard works without one" in page
        assert "Write first daily message" in page

    def test_writing_the_first_board_says_so(self, client, monkeypatch):
        self.make_it_theirs(client)
        monkeypatch.setattr("web.routes.settings.run_generation",
                            lambda config, store, **kw: {"headline": "Hello, Anna"})
        landed = client.post("/settings/generate", follow_redirects=True).get_data(as_text=True)
        assert "Your first daily message is written — “Hello, Anna”" in landed

    def test_it_leaves_once_the_first_board_is_written(self, client, tmp_path):
        self.make_it_theirs(client)
        (tmp_path / "dashboard_data.json").write_text(json.dumps({
            "generated_for_date": "2026-09-03", "headline": "Hi", "note": "There",
            "events": []}))
        page = self.home(client)
        assert "Set up your dashboard" not in page
        assert "Rewrite daily message" in page and "View dashboard" in page
        assert "Add a calendar" in page  # still no calendar, so not "Refresh"

    def test_a_written_board_alone_does_not_end_set_up(self, client, tmp_path):
        # The family that signed up before the rule has a dashboard about Mia and
        # Theo. That is not set up; the checklist stays until they are gone.
        (tmp_path / "dashboard_data.json").write_text(json.dumps({
            "generated_for_date": "2026-09-03", "headline": "Hi", "note": "There",
            "events": []}))
        assert "Set up your dashboard" in self.home(client)


class TestTheCadencePage:
    """`refresh_minutes` and `brief_time`, edited from a phone rather than in YAML."""

    @pytest.fixture
    def config_path(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(CADENCE_CONFIG)
        return path

    def test_the_page_is_not_swallowed_by_the_section_routes(self, client):
        # `/settings/<section_name>` would match "refresh" too.
        assert client.get("/settings/refresh").status_code == 200

    def test_it_opens_on_what_the_file_says(self, client):
        page = client.get("/settings/refresh").get_data(as_text=True)
        assert '<option value="60" selected>Every hour</option>' in page
        assert 'value="06:00"' in page

    def test_it_offers_the_five_intervals(self, client):
        page = client.get("/settings/refresh").get_data(as_text=True)
        for label in ("Every 15 minutes", "Every 30 minutes", "Every hour",
                      "Every 6 hours", "Once a day"):
            assert f">{label}</option>" in page

    def test_saving_both_writes_them_back(self, client, config_path):
        client.post("/settings/refresh",
                    data={"refresh_minutes": "15", "brief_time": "07:30"})
        config = config_module.load_config(config_path)
        assert config["refresh_minutes"] == 15
        assert config["brief_time"] == "07:30"

    def test_a_save_changes_exactly_the_two_lines_it_means_to(self, client, config_path):
        before = config_path.read_text().splitlines()
        client.post("/settings/refresh",
                    data={"refresh_minutes": "1440", "brief_time": "07:30"})
        after = config_path.read_text().splitlines()

        changed = [(a, b) for a, b in zip(before, after) if a != b]
        assert changed == [
            ("refresh_minutes: 60", "refresh_minutes: 1440"),
            ('brief_time: "06:00"', 'brief_time: "07:30"'),
        ]
        # The comments introducing them are what a self-hoster reads.
        assert "# How often --tick re-fetches the calendars." in "\n".join(after)
        assert "# When --tick writes the daily brief, on your own clock." in "\n".join(after)

    def test_the_brief_time_stays_quoted(self, config_path, client):
        # Bare 07:30 is a string to ruamel and a sexagesimal integer to a YAML
        # 1.1 parser. The file is edited by hand, so it keeps its quotes.
        client.post("/settings/refresh",
                    data={"refresh_minutes": "60", "brief_time": "07:30"})
        assert 'brief_time: "07:30"' in config_path.read_text()

    def test_seconds_from_a_time_input_are_trimmed(self, client, config_path):
        client.post("/settings/refresh",
                    data={"refresh_minutes": "60", "brief_time": "07:30:00"})
        assert config_module.load_config(config_path)["brief_time"] == "07:30"

    def test_an_interval_that_was_not_offered_is_refused(self, client, config_path):
        page = client.post("/settings/refresh",
                           data={"refresh_minutes": "7", "brief_time": "07:30"})
        assert "Pick one of the calendar intervals offered." in page.get_data(as_text=True)
        assert config_module.load_config(config_path)["refresh_minutes"] == 60

    def test_a_time_that_is_not_a_time_is_refused(self, client, config_path):
        page = client.post("/settings/refresh",
                           data={"refresh_minutes": "15", "brief_time": "breakfast"})
        assert "should look like 06:00" in page.get_data(as_text=True)
        # Neither key is written when either is wrong.
        config = config_module.load_config(config_path)
        assert (config["refresh_minutes"], config["brief_time"]) == (60, "06:00")

    def test_a_rejected_form_shows_back_what_was_typed(self, client):
        page = client.post("/settings/refresh",
                           data={"refresh_minutes": "15", "brief_time": "breakfast"})
        assert 'value="breakfast"' in page.get_data(as_text=True)

    def test_a_hand_edited_interval_is_offered_rather_than_overwritten(self, client, config_path):
        config_path.write_text(CADENCE_CONFIG.replace("refresh_minutes: 60",
                                                      "refresh_minutes: 45"))
        page = client.get("/settings/refresh").get_data(as_text=True)
        assert '<option value="45" selected>Every 45 minutes</option>' in page
        # And saving it back keeps it, rather than snapping to the nearest offer.
        client.post("/settings/refresh", data={"refresh_minutes": "45", "brief_time": "06:00"})
        assert config_module.load_config(config_path)["refresh_minutes"] == 45


class TestTheCadenceOnTheHomePage:
    @pytest.fixture
    def config_path(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(CADENCE_CONFIG)
        return path

    def test_the_row_says_both_cadences(self, client):
        page = client.get("/settings/").get_data(as_text=True)
        assert "Calendars every hour · daily message at 06:00" in page
        assert 'href="/settings/refresh"' in page

    def test_it_follows_what_was_saved(self, client):
        client.post("/settings/refresh", data={"refresh_minutes": "1440", "brief_time": "07:30"})
        page = client.get("/settings/").get_data(as_text=True)
        assert "Calendars once a day · daily message at 07:30" in page


CALENDAR_CONFIG = """\
family_name: "The Wilsons"
timezone: "Europe/Berlin"

calendars:
  - id: school123
    label: "School"
    url: "https://school.example/term.ics"
    enabled: true
  - id: sams12345
    label: "Sam's"
    url: "https://calendar.google.com/calendar/ical/sam%40gmail.com/private-xxxx/basic.ics"
    enabled: true
    shared_with: ["jess@example.com"]
"""


class TestTheGuestList:
    """A personal calendar can show only the events the other parent is on."""

    @pytest.fixture
    def config_path(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(CALENDAR_CONFIG)
        return path

    def calendars(self, config_path):
        return config_module.load_config(config_path)["calendars"]

    def test_the_form_has_the_field(self, client):
        page = client.get("/settings/calendars/school123").get_data(as_text=True)
        assert "Only show events shared with" in page
        assert 'name="shared_with"' in page

    def test_the_form_shows_the_list_as_one_line(self, client):
        page = client.get("/settings/calendars/sams12345").get_data(as_text=True)
        assert 'value="jess@example.com"' in page

    def test_saving_tidies_the_addresses_into_a_list(self, client, config_path):
        client.post("/settings/calendars/school123", data={
            "label": "School", "url": "https://school.example/term.ics", "enabled": "on",
            "shared_with": " Jess@Example.com, nanny@example.com ",
        })
        assert self.calendars(config_path)[0]["shared_with"] == [
            "jess@example.com", "nanny@example.com",
        ]

    def test_an_empty_field_means_everything(self, client, config_path):
        client.post("/settings/calendars/sams12345", data={
            "label": "Sam's", "enabled": "on", "shared_with": "",
            "url": "https://calendar.google.com/calendar/ical/sam%40gmail.com/private-xxxx/basic.ics",
        })
        assert self.calendars(config_path)[1]["shared_with"] == []

    def test_something_that_is_not_an_address_is_refused(self, client, config_path):
        page = client.post("/settings/calendars/school123", data={
            "label": "School", "url": "https://school.example/term.ics", "shared_with": "jess",
        }).get_data(as_text=True)
        assert "is not an email address" in page
        assert "shared_with" not in self.calendars(config_path)[0]

    def test_the_list_says_which_calendars_are_filtered(self, client):
        page = client.get("/settings/calendars").get_data(as_text=True)
        assert "Only events shared with jess@example.com" in page
        assert page.count("Only events shared with") == 1

    @pytest.fixture
    def described(self, monkeypatch):
        """Stub the fetch: the check is about the wording, not the network."""
        def _serve(count, total, nxt=None):
            def fake(url, tzinfo, today=None, days_ahead=14, shared_with=None, **kwargs):
                return {"count": count, "total": total, "days_ahead": days_ahead,
                        "shared_with": shared_with or [], "next": nxt}
            monkeypatch.setattr("web.routes.settings.describe_feed", fake)
        return _serve

    def check(self, client, shared_with):
        return client.post("/settings/calendars/new", data={
            "action": "check", "label": "Sam's", "url": "https://x.example/a.ics",
            "shared_with": shared_with,
        }).get_data(as_text=True)

    def test_checking_says_how_many_got_through(self, client, described):
        described(3, 24, {"title": "Swimming", "date": "2026-09-04",
                          "all_day": False, "time": "16:00"})
        page = self.check(client, "jess@example.com")
        assert ("3 of the 24 events over the next 14 days are shared with "
                "jess@example.com.") in page
        assert "Next up: Swimming, 2026-09-04 at 16:00." in page

    def test_checking_warns_when_nothing_gets_through(self, client, described):
        # The failure the old global filter hid: a working link, a full
        # calendar, and a dashboard with nothing on it.
        described(0, 24)
        page = self.check(client, "jess@example.com")
        assert ("has 24 events in the next 14 days, but none of them is shared with "
                "jess@example.com") in page
        assert 'class="flash error"' in page

    def test_checking_without_a_list_reads_as_before(self, client, described):
        described(24, 24, {"title": "Swimming", "date": "2026-09-04",
                           "all_day": True, "time": None})
        page = self.check(client, "")
        assert "24 events over the next 14 days. Next up: Swimming, 2026-09-04 at all day." in page


class TestCalendarLinkFeedback:
    @pytest.mark.parametrize("status, body, message", [
        (401, b"", "isn't allowing DinkyDash"),
        (403, b"", "isn't allowing DinkyDash"),
        (404, b"", "It may be private, out of date, or copied incorrectly."),
        (410, b"", "It may be private, out of date, or copied incorrectly."),
        (200, b"<html>Sign in to your calendar</html>", "didn't return readable calendar data"),
    ])
    def test_unusable_links_explain_how_to_retry_without_saving(
            self, client, config_path, monkeypatch, status, body, message):
        from html import unescape
        from test_feed_safety import FakeResponse, resolves_to, serves

        resolves_to(monkeypatch, "1.1.1.1")
        serves(monkeypatch, FakeResponse(status=status, body=body))
        # A link can be tested before choosing a name. Testing must neither
        # create a calendar nor lose the pasted link and guest filter.
        link = "https://calendar.example/not-a-feed"
        response = client.post("/settings/calendars/new", data={
            "action": "check", "label": "", "url": link,
            "shared_with": "sam@example.com", "enabled": "on",
        })
        assert response.status_code == 200
        page = unescape(response.get_data(as_text=True))
        assert message in page
        assert "Copy a fresh iCal / ICS sharing link" in page
        assert '<details class="note-box calendar-help" open>' in page
        assert "This works for private calendars too" in page
        assert f'value="{link}"' in page
        assert 'value="sam@example.com"' in page
        assert not config_module.load_config(config_path).get("calendars")

    def test_server_failure_does_not_blame_calendar_sharing(self, client, monkeypatch):
        from test_feed_safety import FakeResponse, resolves_to, serves

        resolves_to(monkeypatch, "1.1.1.1")
        serves(monkeypatch, FakeResponse(status=503))
        page = client.post("/settings/calendars/new", data={
            "action": "check", "url": "https://calendar.example/feed.ics",
        }).get_data(as_text=True)
        assert "503" in page
        assert "Copy a fresh iCal / ICS sharing link" not in page


class TestANewCalendarComesWithAName:
    """The name is for the settings list, not the dashboard, so it is filled in.

    Somebody arriving with a link should be able to paste it and save. The
    suggestion is "Family" unless a calendar already has that name, and then a
    numbered one — two feeds sharing a name are filed together.
    """

    def test_the_first_calendar_is_called_family(self, client):
        page = client.get("/settings/calendars/new").get_data(as_text=True)
        assert 'name="label" value="Family"' in page
        assert "<h1" in page and "New calendar" in page

    def test_pasting_a_link_and_saving_is_enough(self, client, config_path):
        client.post("/settings/calendars/new", data={
            "label": "Family", "url": "https://calendar.example/private-xxxx/basic.ics",
            "enabled": "on"})
        [saved] = config_module.load_config(config_path)["calendars"]
        assert saved["label"] == "Family"

    def test_a_second_calendar_gets_a_number_rather_than_the_same_name(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text('calendars:\n  - id: fam12345\n    label: "Family"\n'
                        '    url: "https://calendar.example/private-xxxx/basic.ics"\n'
                        '    enabled: true\n')
        page = client_for(create_app(FileStore(path))).get(
            "/settings/calendars/new").get_data(as_text=True)
        assert 'name="label" value="Calendar 2"' in page

    def test_the_number_skips_names_already_taken(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text('calendars:\n  - id: fam12345\n    label: "family"\n'
                        '    url: "https://a.example/private-xxxx/a.ics"\n'
                        '  - id: two12345\n    label: "Calendar 2"\n'
                        '    url: "https://b.example/private-xxxx/b.ics"\n')
        page = client_for(create_app(FileStore(path))).get(
            "/settings/calendars/new").get_data(as_text=True)
        assert 'name="label" value="Calendar 3"' in page

    def test_an_existing_calendar_keeps_its_own_name_in_the_heading(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text('calendars:\n  - id: sch12345\n    label: "School"\n'
                        '    url: "https://a.example/private-xxxx/a.ics"\n')
        page = client_for(create_app(FileStore(path))).get(
            "/settings/calendars/sch12345").get_data(as_text=True)
        assert "New calendar" not in page
        assert 'name="label" value="School"' in page


class TestSavingACalendarForgetsWhatItFetched:
    """A guest list added after a fetch was never applied to what is stored.

    So the stored events of that calendar go when it is saved, and the fetch
    stamp with them, which makes the next tick fetch afresh. Otherwise the
    unfiltered events would stay on the dashboard — and in the next brief — until
    a refresh happened to succeed, and a failing feed would keep them for good.
    """

    @pytest.fixture
    def config_path(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(CALENDAR_CONFIG)
        return path

    @pytest.fixture
    def board(self, tmp_path):
        path = tmp_path / "dashboard_data.json"
        path.write_text(json.dumps({
            "generated_for_date": "2026-09-03", "headline": "Hi", "note": "There",
            "calendars_fetched_at": "2026-09-03T08:00:00+00:00",
            "calendar_statuses": [{"label": "School", "ok": True}, {"label": "Sam's", "ok": True}],
            "events": [
                {"title": "Sports day", "date": "2026-09-04", "calendar": "School"},
                {"title": "Therapy", "date": "2026-09-03", "calendar": "Sam's"},
            ],
        }))
        return lambda: json.loads(path.read_text())

    SAMS = {"label": "Sam's", "enabled": "on",
            "url": "https://calendar.google.com/calendar/ical/sam%40gmail.com/private-xxxx/basic.ics"}

    def test_saving_drops_that_calendars_stored_events(self, client, board):
        client.post("/settings/calendars/sams12345",
                    data={**self.SAMS, "shared_with": "jess@example.com"})
        payload = board()
        assert [e["title"] for e in payload["events"]] == ["Sports day"]
        assert [s["label"] for s in payload["calendar_statuses"]] == ["School"]
        assert "calendars_fetched_at" not in payload  # so the next tick fetches again
        assert payload["headline"] == "Hi"

    def test_a_rename_forgets_under_the_old_name_too(self, client, board):
        client.post("/settings/calendars/sams12345", data={**self.SAMS, "label": "Dad's"})
        assert [e["title"] for e in board()["events"]] == ["Sports day"]

    def test_removing_a_calendar_removes_its_events(self, client, board):
        client.post("/settings/calendars/sams12345/delete", data={"confirmed": "yes"})
        assert [e["title"] for e in board()["events"]] == ["Sports day"]

    def test_reordering_forgets_nothing(self, client, board):
        client.post("/settings/calendars/sams12345/move", data={"direction": "up"})
        assert len(board()["events"]) == 2
        assert "calendars_fetched_at" in board()

    def test_a_rejected_form_forgets_nothing(self, client, board):
        client.post("/settings/calendars/sams12345", data={**self.SAMS, "shared_with": "jess"})
        assert len(board()["events"]) == 2

    def test_the_message_says_when_it_shows(self, client, board):
        page = client.post("/settings/calendars/sams12345", data=self.SAMS,
                           follow_redirects=True).get_data(as_text=True)
        assert "picks up the change at the next refresh" in page


class TestRefreshingTheCalendarsByHand:
    """The cheap half of "Rewrite daily message": fetch the feeds, ask Claude nothing."""

    @pytest.fixture
    def config_path(self, tmp_path):
        # A family with calendars and a written dashboard: the running page, where
        # the button lives. With no calendar the slot offers "Add a calendar".
        path = tmp_path / "config.yaml"
        path.write_text(CALENDAR_CONFIG)
        (tmp_path / "dashboard_data.json").write_text(json.dumps({
            "generated_for_date": "2026-09-03", "headline": "Hi", "note": "There",
            "events": [], "calendars_fetched_at": "2026-09-03T08:00:00+00:00"}))
        return path

    @pytest.fixture
    def refreshed(self, monkeypatch):
        """Stub the runner, so the test touches neither the network nor a key."""
        calls = []

        def fake(config, store, **kwargs):
            calls.append(config)
            return {"events": [1, 2, 3], "calendar_statuses": [{"label": "Family", "ok": True}]}

        monkeypatch.setattr("web.routes.settings.refresh_calendars", fake)
        return calls

    def test_the_button_posts_to_the_refresh_route(self, client):
        page = client.get("/settings/").get_data(as_text=True)
        assert 'action="/settings/refresh-now"' in page
        assert "Refresh calendars" in page

    def test_with_nothing_to_refresh_the_slot_offers_a_calendar(self, tmp_path, config_path):
        # Same written dashboard, no calendars: "Refresh calendars" would fetch
        # nothing and say so, which is the button a new family was met with.
        config_path.write_text(CALENDAR_CONFIG.split("calendars:")[0])
        page = client_for(create_app(FileStore(config_path))).get("/settings/").get_data(as_text=True)
        assert "Refresh calendars" not in page
        assert "Add a calendar" in page
        assert 'href="/settings/calendars/new"' in page
        assert "Rewrite daily message" in page and "View dashboard" in page

    def test_it_reports_what_it_found(self, client, refreshed):
        page = client.post("/settings/refresh-now", follow_redirects=True)
        assert "Calendars refreshed — 3 events over the next 14 days." in \
            page.get_data(as_text=True)
        assert len(refreshed) == 1

    def test_a_broken_feed_is_named_without_its_url(self, client, monkeypatch):
        secret = "https://calendar.google.com/calendar/ical/private-abc123/basic.ics"

        def fake(config, store, **kwargs):
            return {"events": [],
                    "calendar_statuses": [{"label": "Dad's", "ok": False, "error": secret}]}

        monkeypatch.setattr("web.routes.settings.refresh_calendars", fake)
        page = client.post("/settings/refresh-now", follow_redirects=True).get_data(as_text=True)
        assert "1 didn&#39;t answer: Dad&#39;s." in page
        assert "private-abc123" not in page

    def test_a_failure_flashes_rather_than_500s(self, client, monkeypatch):
        def explode(config, store, **kwargs):
            raise OSError("the disk is full")

        monkeypatch.setattr("web.routes.settings.refresh_calendars", explode)
        page = client.post("/settings/refresh-now", follow_redirects=True)
        assert page.status_code == 200
        assert "Could not refresh the calendars: the disk is full" in page.get_data(as_text=True)


class TestTheAppBar:
    def test_the_title_heading_and_back_link(self, client):
        page = client.get("/settings/system").get_data(as_text=True)
        assert "<title>Family &amp; system · DinkyDash</title>" in page
        assert "<h1>Family &amp; system</h1>" in page
        assert '<a class="back" href="/settings/">' in page
        assert "<span>Settings</span>" in page
        assert 'class="back"' not in client.get("/settings/").get_data(as_text=True)

    def test_the_way_back_names_the_page_it_goes_to(self, client, config_path):
        client.get("/settings/people")
        pid = ids_for(config_path)[0]
        edit = client.get(f"/settings/people/{pid}").get_data(as_text=True)
        assert '<a class="back" href="/settings/people">' in edit
        assert "<span>People</span>" in edit
        confirm = client.post(f"/settings/people/{pid}/delete").get_data(as_text=True)
        assert f'<a class="back" href="/settings/people/{pid}">' in confirm
        assert "<span>Cancel</span>" in confirm

    def test_the_colours_page_is_called_that_in_the_tab_too(self, client):
        page = client.get("/settings/screen").get_data(as_text=True)
        assert "<title>Colours · DinkyDash</title>" in page
        assert "<h1>Colours</h1>" in page


class TestTheControlsUnderAPointer:
    def test_a_persons_name_toggles_their_box(self, client):
        page = client.get("/settings/recurring/new").get_data(as_text=True)
        assert '<label for="p-1">Mia</label>' in page
