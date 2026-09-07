"""The storage seam.

`FileStore` is the only implementation today, so what is worth asserting is the
contract `PostgresStore` will have to keep: six operations, a payload that comes
back as the dict that went in, a history that trims itself, and nothing that
raises when the files are missing or corrupt. A board must not go dark because
somebody's disk filled up mid-write.
"""

import json

import pytest

from dinkydash.store import FileStore

CONFIG = """\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
people:
  - name: "Mia"
    date_of_birth: "2017-03-15"
"""

PAYLOAD = {
    "generated_for_date": "2026-09-03",
    "generated_at": "2026-09-03T04:00:00+00:00",
    "headline": "Big morning",
    "note": "An octopus fact.",
    "events": [{"title": "Swimming", "date": "2026-09-03"}],
}


@pytest.fixture
def store(tmp_path):
    (tmp_path / "config.yaml").write_text(CONFIG)
    return FileStore(tmp_path / "config.yaml")


@pytest.fixture
def config(store):
    return store.load_config()


def _explode(message):
    def _raise(*args, **kwargs):
        raise OSError(message)
    return _raise


class TestTheConfig:
    def test_it_loads_with_the_defaults_filled_in(self, store):
        config = store.load_config()
        assert config["family_name"] == "The Wilsons"
        assert config["refresh_minutes"] == 60

    def test_a_save_comes_back_on_the_next_load(self, store):
        config = store.load_config()
        config["family_name"] = "The Bakers"
        store.save_config(config)
        assert store.load_config()["family_name"] == "The Bakers"


class TestTheBoard:
    def test_a_payload_comes_back_as_the_dict_that_went_in(self, store, config):
        store.save_payload(config, PAYLOAD)
        assert store.load_payload(config) == PAYLOAD

    def test_nothing_generated_yet_is_none_rather_than_an_error(self, store, config):
        assert store.load_payload(config) is None

    def test_an_unreadable_payload_reads_as_no_board_at_all(self, store, config, tmp_path):
        # Truncated by a power cut mid-write. The board shows its first-run
        # screen and the next generation replaces the file.
        (tmp_path / "dashboard_data.json").write_text("{not json")
        assert store.load_payload(config) is None

    def test_something_that_is_not_a_payload_is_ignored(self, store, config, tmp_path):
        (tmp_path / "dashboard_data.json").write_text("[1, 2, 3]")
        assert store.load_payload(config) is None


class TestTheNoteHistory:
    def test_a_recorded_note_comes_back(self, store, config):
        store.record_note(config, {"date": "2026-09-03", "note": "An octopus fact."})
        assert store.recent_notes(config, 30) == ["An octopus fact."]

    def test_notes_accumulate_oldest_first(self, store, config):
        for day in range(1, 4):
            store.record_note(config, {"date": f"2026-09-0{day}", "note": f"Note {day}"})
        assert store.recent_notes(config, 30) == ["Note 1", "Note 2", "Note 3"]

    def test_only_the_last_kept_entries_survive(self, store, config, tmp_path):
        for day in range(1, 6):
            store.record_note(config, {"date": f"2026-09-0{day}", "note": f"Note {day}"},
                              keep=3)
        assert store.recent_notes(config, 30) == ["Note 3", "Note 4", "Note 5"]
        assert len(json.loads((tmp_path / "content_history.json").read_text())) == 3

    def test_asking_for_fewer_days_gives_the_most_recent(self, store, config):
        for day in range(1, 4):
            store.record_note(config, {"date": f"2026-09-0{day}", "note": f"Note {day}"})
        assert store.recent_notes(config, 2) == ["Note 2", "Note 3"]

    def test_no_history_yet_is_an_empty_list(self, store, config):
        assert store.recent_notes(config, 30) == []

    def test_a_corrupt_history_does_not_stop_a_board_being_written(self, store, config,
                                                                   tmp_path):
        # The cost of losing this file is one repeated octopus fact, so it must
        # never be the reason a generation fails.
        (tmp_path / "content_history.json").write_text("{not json")
        assert store.recent_notes(config, 30) == []
        store.record_note(config, {"date": "2026-09-03", "note": "Fresh start"})
        assert store.recent_notes(config, 30) == ["Fresh start"]

    def test_an_unwritable_history_is_a_warning_not_a_failure(self, store, config,
                                                              monkeypatch):
        monkeypatch.setattr("dinkydash.store._write_json",
                            _explode("the disk is full"))
        store.record_note(config, {"date": "2026-09-03", "note": "Lost"})  # no exception


class TestWhereTheFilesGo:
    def test_generated_files_sit_beside_their_own_config(self, tmp_path):
        # `generate.py --config /tmp/scratch.yaml` keeps its board with it,
        # rather than in whatever directory it happened to be run from.
        elsewhere = tmp_path / "scratch"
        elsewhere.mkdir()
        (elsewhere / "config.yaml").write_text(CONFIG)
        store = FileStore(elsewhere / "config.yaml")
        store.save_payload(store.load_config(), PAYLOAD)
        assert (elsewhere / "dashboard_data.json").exists()
        assert not (tmp_path / "dashboard_data.json").exists()

    def test_an_absolute_data_file_is_left_where_it_says(self, store, config, tmp_path):
        config["data_file"] = str(tmp_path / "elsewhere.json")
        store.save_payload(config, PAYLOAD)
        assert json.loads((tmp_path / "elsewhere.json").read_text()) == PAYLOAD

    def test_a_half_written_board_is_never_visible(self, store, config, tmp_path):
        # The write goes to a temporary file and is renamed, so a browser
        # loading the board mid-write reads the old one or the new one.
        store.save_payload(config, PAYLOAD)
        with pytest.raises(TypeError):
            store.save_payload(config, {"headline": object()})  # not JSON
        assert store.load_payload(config) == PAYLOAD
        assert list(tmp_path.glob("*.tmp")) == []
