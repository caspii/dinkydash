"""Config loading, defaults, migration, and the round-trip the settings UI needs."""

from datetime import date

import pytest

from dinkydash import config as config_module

EXAMPLE = """\
# The family's name, shown on the board.
family_name: "The Wilsons"
timezone: "Europe/Berlin"

# One entry per feed.
calendars:
  - label: "Family"
    url: "https://example.com/basic.ics"
    enabled: true

people:
  - name: "Mia"          # the eldest
    date_of_birth: "2017-03-15"
"""


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(EXAMPLE)
    return path


class TestDefaults:
    def test_missing_keys_get_defaults(self, config_file):
        config = config_module.load_config(config_file)
        assert config["theme"] == "light"
        assert config["claude_model"] == "claude-haiku-4-5"
        assert config["pets"] == []
        assert config["recurring"] == []

    def test_an_unknown_theme_is_corrected(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text("theme: chartreuse\n")
        assert config_module.load_config(path)["theme"] == "light"

    def test_an_empty_file_still_loads(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text("")
        config = config_module.load_config(path)
        assert config["family_name"] == "Our family"
        assert config["calendars"] == []


class TestMigration:
    def test_a_single_calendar_url_becomes_a_feed(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text('calendar_url: "https://example.com/old.ics"\n')
        config = config_module.load_config(path)
        assert config["calendars"] == [
            {"label": "Calendar", "url": "https://example.com/old.ics", "enabled": True}
        ]
        assert "calendar_url" not in config

    def test_the_old_attendee_filter_moves_onto_the_migrated_feed(self, tmp_path):
        # calendar_filter_emails was one filter for the one calendar_url, and it
        # meant what `shared_with` means now. So it goes where that URL goes.
        path = tmp_path / "config.yaml"
        path.write_text(
            'calendar_url: "https://example.com/old.ics"\n'
            'calendar_filter_emails:\n  - "Spouse@Example.com"\n'
        )
        config = config_module.load_config(path)
        assert "calendar_filter_emails" not in config
        assert config["calendars"] == [{
            "label": "Calendar", "url": "https://example.com/old.ics", "enabled": True,
            "shared_with": ["spouse@example.com"],
        }]

    def test_the_old_attendee_filter_is_dropped_with_nowhere_to_go(self, tmp_path):
        # An explicit calendars list gives no way to tell which feed it meant.
        path = tmp_path / "config.yaml"
        path.write_text(
            'calendar_filter_emails:\n  - "spouse@example.com"\n'
            'calendars:\n  - label: "New"\n    url: "https://example.com/new.ics"\n'
        )
        config = config_module.load_config(path)
        assert "calendar_filter_emails" not in config
        assert "shared_with" not in config["calendars"][0]

    def test_an_explicit_calendars_list_wins_over_the_legacy_key(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(
            'calendar_url: "https://example.com/old.ics"\n'
            'calendars:\n  - label: "New"\n    url: "https://example.com/new.ics"\n'
        )
        config = config_module.load_config(path)
        assert [c["label"] for c in config["calendars"]] == ["New"]


class TestRoundTrip:
    """The settings UI writes this file back, so comments have to survive."""

    def test_comments_survive_an_edit(self, config_file):
        config = config_module.load_config(config_file)
        config["family_name"] = "The Smiths"
        config_module.save_config(config, config_file)
        written = config_file.read_text()
        assert "# The family's name, shown on the board." in written
        assert "# One entry per feed." in written
        assert "# the eldest" in written
        assert "The Smiths" in written

    def test_a_saved_file_loads_back_identically(self, config_file):
        config = config_module.load_config(config_file)
        config["people"].append({"name": "Theo", "date_of_birth": "2019-06-20"})
        config_module.save_config(config, config_file)

        reloaded = config_module.load_config(config_file)
        assert [p["name"] for p in reloaded["people"]] == ["Mia", "Theo"]

    def test_saving_does_not_reindent_the_whole_file(self, config_file):
        # A save that re-indents every list turns each later diff into noise.
        before = config_file.read_text()
        config = config_module.load_config(config_file)
        config["theme"] = "dark"
        config_module.save_config(config, config_file)
        after = config_file.read_text()

        changed = [
            (a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b
        ]
        assert changed == [], f"unexpected churn: {changed[:3]}"
        assert "theme: dark" in after

    def test_a_long_url_is_not_wrapped(self, config_file):
        long_url = "https://calendar.google.com/calendar/ical/" + "x" * 120 + "/basic.ics"
        config = config_module.load_config(config_file)
        config["calendars"][0]["url"] = long_url
        config_module.save_config(config, config_file)
        assert long_url in config_file.read_text()
        assert config_module.load_config(config_file)["calendars"][0]["url"] == long_url

    def test_the_write_is_atomic(self, config_file, monkeypatch):
        # A failed dump must leave the original file intact, not a truncated one.
        original = config_file.read_text()

        class Boom(Exception):
            pass

        def explode(*args, **kwargs):
            raise Boom()

        monkeypatch.setattr("dinkydash.config._yaml", explode)
        with pytest.raises(Boom):
            config_module.save_config({"family_name": "x"}, config_file)
        assert config_file.read_text() == original


class TestIds:
    """Positions renumber; ids do not. The settings UI addresses items by id."""

    def test_every_list_item_gets_one(self, config_file):
        config = config_module.load_config(config_file)
        assert config_module.ensure_ids(config) is True
        assert config["people"][0]["id"]
        assert config["calendars"][0]["id"]

    def test_running_twice_changes_nothing(self, config_file):
        config = config_module.load_config(config_file)
        config_module.ensure_ids(config)
        before = config["people"][0]["id"]
        assert config_module.ensure_ids(config) is False
        assert config["people"][0]["id"] == before

    def test_hand_written_ids_are_left_alone(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text('people:\n  - name: "Mia"\n    id: "mia"\n')
        config = config_module.load_config(path)
        assert config_module.ensure_ids(config) is False
        assert config["people"][0]["id"] == "mia"

    def test_ids_within_a_list_are_unique(self):
        config = {"people": [{"name": str(n)} for n in range(50)]}
        config_module.ensure_ids(config)
        assert len({p["id"] for p in config["people"]}) == 50

    def test_no_lookalike_characters(self):
        # Ids show up in URLs and get read aloud when something breaks.
        assert not set("01lOI") & set(config_module.ID_ALPHABET)

    def test_loading_does_not_add_them(self, config_file):
        # load_config must not mutate the file on disk, and the engine never
        # looks at ids — so backfilling is the settings UI's job, not load's.
        config = config_module.load_config(config_file)
        assert "id" not in config["people"][0]

    def test_find_item_returns_the_position_and_the_item(self):
        items = [{"id": "a", "name": "Mia"}, {"id": "b", "name": "Theo"}]
        assert config_module.find_item(items, "b") == (1, items[1])

    def test_find_item_on_a_stranger(self):
        assert config_module.find_item([{"id": "a"}], "zzz") == (None, None)

    def test_an_id_does_not_land_under_the_next_heading(self, tmp_path):
        # ruamel hangs the comment introducing the next section off the last
        # item of the previous one, so an id appended there ends up beneath
        # somebody else's heading. Valid YAML, unreadable file.
        path = tmp_path / "config.yaml"
        path.write_text(
            'calendars:\n'
            '  - label: "Family"\n'
            '    url: "https://example.com/basic.ics"\n'
            '\n'
            '# Birthdays here become countdowns.\n'
            'people:\n'
            '  - name: "Mia"\n'
        )
        config = config_module.load_config(path)
        config_module.ensure_ids(config)
        config_module.save_config(config, path)

        lines = [line for line in path.read_text().splitlines() if line.strip()]
        heading = lines.index("# Birthdays here become countdowns.")
        assert lines[heading + 1] == "people:"

    def test_an_inline_comment_stays_with_its_key(self, config_file):
        config = config_module.load_config(config_file)
        config_module.ensure_ids(config)
        config_module.save_config(config, config_file)
        written = config_file.read_text()
        assert 'name: "Mia"          # the eldest' in written


class TestTimezone:
    def test_today_uses_the_family_timezone(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text('timezone: "Pacific/Auckland"\n')
        config = config_module.load_config(path)
        assert isinstance(config_module.today_for(config), date)
        assert config_module.tzinfo_for(config).key == "Pacific/Auckland"

    def test_an_unknown_zone_does_not_crash_the_board(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text('timezone: "Middle/Earth"\n')
        config = config_module.load_config(path)
        assert config_module.tzinfo_for(config).key == "UTC"


class TestTheInventedHousehold:
    """`starter_config` marks what it invents, and set-up is "the marks are gone".

    The mark is how the settings home knows what still has to be replaced and
    how the tick knows not to write about it. It says "never touched" and
    nothing else: a hand-written config has none, whatever the names in it.
    """

    def test_the_starter_marks_every_person_and_pet(self):
        starter = config_module.starter_config()
        assert all(p[config_module.INVENTED] for p in starter["people"])
        assert all(p[config_module.INVENTED] for p in starter["pets"])
        assert config_module.invented_names(starter) == ["Mia", "Theo", "Biscuit"]

    def test_the_example_file_carries_the_same_marks(self):
        from pathlib import Path
        example = config_module.load_config(
            Path(__file__).resolve().parent.parent / "config.example.yaml")
        assert config_module.invented_names(example) == ["Mia", "Theo", "Biscuit"]

    def test_a_hand_written_config_has_no_marks_whatever_the_names(self, config_file):
        # The example's Mia, born on the example's date, is still theirs.
        config = config_module.load_config(config_file)
        assert config_module.invented_names(config) == []

    def test_the_starter_is_not_set_up(self):
        assert config_module.is_set_up(config_module.starter_config()) is False

    def test_replacing_the_household_is_only_half_of_it(self):
        home = config_module.starter_config()
        for item in home["people"] + home["pets"]:
            item.pop(config_module.INVENTED)
        assert config_module.timezone_is_set(home) is False
        assert config_module.is_set_up(home) is False
        home["timezone"] = "Europe/Berlin"
        assert config_module.is_set_up(home) is True

    def test_the_timezone_alone_is_not_enough_either(self):
        home = config_module.starter_config()
        home["timezone"] = "Europe/Berlin"
        assert config_module.is_set_up(home) is False

    def test_a_hand_written_config_with_a_timezone_is_set_up(self, config_file):
        assert config_module.is_set_up(config_module.load_config(config_file)) is True

    def test_utc_is_read_as_unset(self):
        # Nobody's kitchen: a family that really lives on it picks its named zone.
        assert config_module.timezone_is_set({"timezone": "UTC"}) is False
        assert config_module.timezone_is_set({}) is False
        assert config_module.timezone_is_set({"timezone": "Atlantic/Reykjavik"}) is True


class TestPeopleAndTheirChores:
    """Chores hold names as text, so a rename or a removal has to follow them."""

    def test_a_rename_follows_into_every_rotation(self):
        home = {"recurring": [{"title": "Table", "choices": ["Mia", "Theo"]},
                              {"title": "Dog", "choices": ["Theo", "Mia"]}]}
        config_module.rename_in_chores(home, "Mia", "Anna")
        assert [c["choices"] for c in home["recurring"]] == [["Anna", "Theo"], ["Theo", "Anna"]]

    def test_a_removal_leaves_every_rotation(self):
        home = {"recurring": [{"title": "Table", "choices": ["Mia", "Theo"]},
                              {"title": "Dog", "choices": ["Mia"]}]}
        config_module.drop_from_chores(home, "Mia")
        assert [c["choices"] for c in home["recurring"]] == [["Theo"], []]

    def test_a_chore_with_no_rotation_survives_both(self):
        home = {"recurring": [{"title": "Table"}]}
        config_module.rename_in_chores(home, "Mia", "Anna")
        config_module.drop_from_chores(home, "Mia")
        assert home["recurring"] == [{"title": "Table"}]

    def test_the_file_keeps_its_flow_style_lists(self, tmp_path):
        # Edited in place: `choices: ["Mia", "Theo"]` must not come back as a
        # block sequence the first time somebody is renamed.
        path = tmp_path / "config.yaml"
        path.write_text('recurring:\n  - title: "Table"\n    choices: ["Mia", "Theo"]\n')
        config = config_module.load_config(path)
        config_module.rename_in_chores(config, "Mia", "Anna")
        config_module.save_config(config, path)
        assert 'choices: ["Anna", "Theo"]' in path.read_text()


def test_people_names_skips_the_nameless(config_file):
    config = config_module.load_config(config_file)
    config["people"].append({"date_of_birth": "2020-01-01"})
    assert config_module.people_names(config) == ["Mia"]
