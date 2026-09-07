"""The storage contract, asserted identically against both implementations.

Every test here runs twice: once over `FileStore` on `tmp_path`, once over
`PostgresStore` against a real database. Same assertions, no branching — that
parity is most of the value of having named the seam at all, because a suite
that only ever ran against files would not notice the day the two drifted.

The Postgres half skips when `DINKYDASH_TEST_DATABASE_URL` is unset, so a
self-hoster with no database still gets a green suite. CI sets it.
"""

from datetime import datetime, timezone

import pytest

from dinkydash.store import FileStore

CONFIG_YAML = """\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
people:
  - name: "Mia"
    date_of_birth: "2017-03-15"
"""

CONFIG_DICT = {
    "family_name": "The Wilsons",
    "timezone": "Europe/Berlin",
    "people": [{"name": "Mia", "date_of_birth": "2017-03-15"}],
}

EVENTS = [{"title": "Swimming", "date": "2026-09-03", "time": "15:45",
           "all_day": False, "start": "2026-09-03T15:45:00+02:00",
           "location": None, "calendar": "Family"}]
STATUSES = [{"label": "Family", "ok": True, "detail": "", "count": 1}]

PAYLOAD = {
    "generated_for_date": "2026-09-03",
    "generated_at": "2026-09-03T04:00:00+00:00",
    "headline": "Big morning",
    "note": "An octopus fact.",
    "note_kind": "fact",
    "model": "claude-haiku-4-5",
    "input_tokens": 120,
    "output_tokens": 45,
    "events": EVENTS,
    "calendar_statuses": STATUSES,
    "calendars_fetched_at": "2026-09-03T03:50:00+00:00",
}


@pytest.fixture(params=["file", "postgres"])
def store(request, tmp_path):
    """The same seeded family, once as files and once as rows."""
    if request.param == "file":
        (tmp_path / "config.yaml").write_text(CONFIG_YAML)
        return FileStore(tmp_path / "config.yaml")

    # Pulled lazily, so the file run never asks for a database.
    pool = request.getfixturevalue("pg_pool")
    family_id = request.getfixturevalue("pg_family")
    from dinkydash.pgstore import PostgresStore

    store = PostgresStore(pool, family_id)
    store.save_config(dict(CONFIG_DICT))
    return store


@pytest.fixture
def config(store):
    return store.load_config()


class TestTheConfig:
    def test_it_loads_with_the_defaults_filled_in(self, store):
        config = store.load_config()
        assert config["family_name"] == "The Wilsons"
        assert config["timezone"] == "Europe/Berlin"
        assert config["refresh_minutes"] == 60      # from DEFAULTS, not the source
        assert config["brief_time"] == "06:00"

    def test_the_edited_lists_survive(self, store):
        assert [p["name"] for p in store.load_config()["people"]] == ["Mia"]

    def test_a_save_comes_back_on_the_next_load(self, store):
        config = store.load_config()
        config["family_name"] = "The Bakers"
        store.save_config(config)
        assert store.load_config()["family_name"] == "The Bakers"

    def test_a_new_key_survives_a_round_trip(self, store):
        # `with_defaults` migrates the dict on load in both modes, so a setting
        # added tomorrow needs no migration on either side.
        config = store.load_config()
        config["something_new"] = 42
        store.save_config(config)
        assert store.load_config()["something_new"] == 42


class TestTheBoard:
    def test_nothing_generated_yet_is_none_rather_than_an_error(self, store, config):
        assert store.load_payload(config) is None

    def test_a_payload_comes_back_as_the_dict_that_went_in(self, store, config):
        store.save_payload(config, dict(PAYLOAD))
        assert store.load_payload(config) == PAYLOAD

    def test_saving_twice_replaces_rather_than_accumulates(self, store, config):
        store.save_payload(config, dict(PAYLOAD))
        second = dict(PAYLOAD, headline="A quieter morning")
        store.save_payload(config, second)
        assert store.load_payload(config) == second

    def test_a_refresh_before_the_first_brief_stores_only_the_agenda(self, store, config):
        # What a first `--tick` writes before brief_time: times, no words. The
        # board shows its waiting screen rather than claiming a date.
        agenda_only = {"events": EVENTS, "calendar_statuses": STATUSES,
                       "calendars_fetched_at": "2026-09-03T03:50:00+00:00"}
        store.save_payload(config, agenda_only)
        assert store.load_payload(config) == agenda_only

    def test_a_fresh_agenda_under_yesterdays_brief(self, store, config):
        # The amber-banner state: a refresh must not disturb the brief.
        store.save_payload(config, dict(PAYLOAD))
        stored = store.load_payload(config)
        stored["events"] = []
        stored["calendars_fetched_at"] = "2026-09-04T07:00:00+00:00"
        store.save_payload(config, stored)

        after = store.load_payload(config)
        assert after["events"] == []
        assert after["calendars_fetched_at"] == "2026-09-04T07:00:00+00:00"
        assert after["headline"] == "Big morning"
        assert after["generated_for_date"] == "2026-09-03"
        assert after["generated_at"] == "2026-09-03T04:00:00+00:00"

    def test_stamps_come_back_in_utc(self, store, config):
        # The two stores must agree about what time a board was written, or the
        # settings page renders the wrong clock on one of them (PLAN.md bug 9).
        store.save_payload(config, dict(PAYLOAD))
        written = store.load_payload(config)["generated_at"]
        assert datetime.fromisoformat(written) == datetime(
            2026, 9, 3, 4, 0, tzinfo=timezone.utc)

    def test_a_payload_with_no_stamps_at_all_is_fine(self, store, config):
        """A missing stamp must not be a write error on either side.

        The contract is that `.get()` agrees, not that the dicts are identical:
        `FileStore` returns what was written, so an absent key stays absent,
        while `PostgresStore` reassembles from columns and hands back None. Every
        consumer — `board.build_view`, `schedule.due`, the settings page — reads
        through `.get()`, so the two are the same answer.
        """
        bare = {"generated_for_date": "2026-09-03", "headline": "Hi",
                "note": "There", "note_kind": "fact", "events": []}
        store.save_payload(config, bare)
        after = store.load_payload(config)
        assert after["headline"] == "Hi"
        assert after["generated_for_date"] == "2026-09-03"
        assert after.get("generated_at") is None
        assert after.get("calendars_fetched_at") is None


class TestTheNoteHistory:
    def test_no_history_yet_is_an_empty_list(self, store, config):
        assert store.recent_notes(config, 30) == []

    def test_a_recorded_note_comes_back(self, store, config):
        store.record_note(config, {"date": "2026-09-03", "headline": "Big morning",
                                   "note": "An octopus fact.", "note_kind": "fact"})
        assert store.recent_notes(config, 30) == ["An octopus fact."]

    def test_notes_accumulate_oldest_first(self, store, config):
        for day in range(1, 4):
            store.record_note(config, {"date": f"2026-09-0{day}", "note": f"Note {day}",
                                       "headline": "H", "note_kind": "fact"})
        assert store.recent_notes(config, 30) == ["Note 1", "Note 2", "Note 3"]

    def test_only_the_last_kept_entries_survive(self, store, config):
        for day in range(1, 6):
            store.record_note(config, {"date": f"2026-09-0{day}", "note": f"Note {day}",
                                       "headline": "H", "note_kind": "fact"}, keep=3)
        assert store.recent_notes(config, 30) == ["Note 3", "Note 4", "Note 5"]

    def test_asking_for_fewer_days_gives_the_most_recent(self, store, config):
        for day in range(1, 4):
            store.record_note(config, {"date": f"2026-09-0{day}", "note": f"Note {day}",
                                       "headline": "H", "note_kind": "fact"})
        assert store.recent_notes(config, 2) == ["Note 2", "Note 3"]

    def test_an_entry_with_no_note_is_skipped_rather_than_blank(self, store, config):
        store.record_note(config, {"date": "2026-09-03", "headline": "H",
                                   "note": "", "note_kind": "fact"})
        assert store.recent_notes(config, 30) == []


def test_the_two_stores_agree_on_which_keys_a_refresh_owns():
    """`pgstore` copies REFRESH_KEYS rather than importing upwards from `runner`.

    That copy is deliberate — the store sits below the runner — but a copy is
    only safe if something notices when it stops matching.
    """
    pytest.importorskip("psycopg")
    from dinkydash import pgstore, runner

    assert pgstore.REFRESH_KEYS == runner.REFRESH_KEYS
