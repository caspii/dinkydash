"""What is true of `FileStore` and only `FileStore`.

The six operations themselves are asserted in `test_store_contract.py`, against
both implementations with the same assertions. What is left here is the part
that is genuinely about files: where they land, what happens when one is
corrupt, and that a reader never sees half of one.
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


def _explode(message):
    def _raise(*args, **kwargs):
        raise OSError(message)
    return _raise


@pytest.fixture
def store(tmp_path):
    (tmp_path / "config.yaml").write_text(CONFIG)
    return FileStore(tmp_path / "config.yaml")


@pytest.fixture
def config(store):
    return store.load_config()


class TestAFileThatIsNotReadable:
    """None of these may take the board down. The next write replaces the file."""

    def test_a_truncated_payload_reads_as_no_board_at_all(self, store, config, tmp_path):
        # Cut off by a power cut mid-write. The board shows its first-run screen.
        (tmp_path / "dashboard_data.json").write_text("{not json")
        assert store.load_payload(config) is None

    def test_something_that_is_not_a_payload_is_ignored(self, store, config, tmp_path):
        (tmp_path / "dashboard_data.json").write_text("[1, 2, 3]")
        assert store.load_payload(config) is None

    def test_a_corrupt_history_does_not_stop_a_board_being_written(self, store, config,
                                                                   tmp_path):
        # The cost of losing this file is one repeated octopus fact, so it must
        # never be the reason a generation fails.
        (tmp_path / "content_history.json").write_text("{not json")
        assert store.recent_notes(config, 30) == []
        store.record_note(config, {"date": "2026-09-03", "note": "Fresh start"})
        assert store.recent_notes(config, 30) == ["Fresh start"]

    def test_a_history_that_is_not_a_list_is_ignored(self, store, config, tmp_path):
        (tmp_path / "content_history.json").write_text('{"note": "not a list"}')
        assert store.recent_notes(config, 30) == []

    def test_an_unwritable_history_is_a_warning_not_a_failure(self, store, config,
                                                              monkeypatch):
        monkeypatch.setattr("dinkydash.store._write_json", _explode("the disk is full"))
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

    def test_the_history_file_is_really_trimmed_on_disk(self, store, config, tmp_path):
        # Not just what `recent_notes` returns — the file itself, because this
        # one lives on a Pi's SD card for years.
        for day in range(1, 6):
            store.record_note(config, {"date": f"2026-09-0{day}", "note": f"Note {day}"},
                              keep=3)
        assert len(json.loads((tmp_path / "content_history.json").read_text())) == 3


class TestWritingIsAtomic:
    def test_a_half_written_board_is_never_visible(self, store, config, tmp_path):
        # The write goes to a temporary file and is renamed, so a browser
        # loading the board mid-write reads the old one or the new one.
        store.save_payload(config, PAYLOAD)
        with pytest.raises(TypeError):
            store.save_payload(config, {"headline": object()})  # not JSON
        assert store.load_payload(config) == PAYLOAD
        assert list(tmp_path.glob("*.tmp")) == []
