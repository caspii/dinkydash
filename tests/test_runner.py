"""The two halves of the run, and the tick that decides between them.

Nothing here touches the network or the API: `fetch_events` is replaced with a
recorder, and the model call goes through the same fake client the generator
tests use. What is being asserted is the division of labour — a refresh must
not rewrite the brief, and a tick that owes nothing must do nothing.
"""

import json
from datetime import date, datetime, timezone

import pytest

import generate as cli
from dinkydash import runner
from dinkydash.claude_client import GenerationError
from dinkydash.store import FileStore

from test_generate import FakeClient  # the same stand-in the generator tests use

CONFIG_YAML = """\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
theme: light
refresh_minutes: 60
brief_time: "06:00"
calendars: []
people:
  - name: "Mia"
    date_of_birth: "2017-03-15"
recurring: []
special_dates: []
data_file: "dashboard_data.json"
content_history_file: "content_history.json"
"""

EVENTS = [
    {"title": "Swimming", "date": "2026-09-03", "time": "15:45", "all_day": False,
     "start": "2026-09-03T15:45:00+02:00", "location": None, "calendar": "Family"},
]
SCHOOL = [
    {"title": "Sports day", "date": "2026-09-04", "time": "09:00", "all_day": False,
     "start": "2026-09-04T09:00:00+02:00", "location": None, "calendar": "School"},
]
OK_STATUS = [{"label": "Family", "ok": True, "detail": "", "count": 1}]
FAILED_STATUS = [{"label": "Family", "ok": False, "detail": "could not fetch", "count": 0}]
# One feed answered, the other did not — the case a single dead URL must not freeze.
MIXED_STATUS = [{"label": "Family", "ok": False, "detail": "could not fetch", "count": 0},
                {"label": "School", "ok": True, "detail": "", "count": 1}]

# Pinned, because the window a refresh keeps is measured from `today`: a test
# that let the real clock decide would pass in September and fail in November.
NOW = datetime(2026, 9, 3, 8, tzinfo=timezone.utc)


@pytest.fixture
def home(tmp_path):
    """A config file and an empty data directory, together, as on a Pi."""
    (tmp_path / "config.yaml").write_text(CONFIG_YAML)
    return tmp_path


@pytest.fixture
def store(home):
    """The one way in and out of that directory."""
    return FileStore(home / "config.yaml")


@pytest.fixture
def config(store):
    return store.load_config()


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")


def stored(home):
    return json.loads((home / "dashboard_data.json").read_text())


def write_stored(home, payload):
    (home / "dashboard_data.json").write_text(json.dumps(payload))


def fake_fetch(events, statuses, seen=None):
    def _fetch(calendars, today, tzinfo, days_ahead=14, timeout=30):
        if seen is not None:
            seen.append({"calendars": calendars, "today": today, "days_ahead": days_ahead})
        return list(events), list(statuses)
    return _fetch


class TestRefreshCalendars:
    def test_stores_the_events_and_stamps_the_fetch(self, home, store, config, monkeypatch):
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(EVENTS, OK_STATUS))
        runner.refresh_calendars(config, store,
                                 now=datetime(2026, 9, 3, 8, tzinfo=timezone.utc))
        payload = stored(home)
        assert payload["events"] == EVENTS
        assert payload["calendar_statuses"] == OK_STATUS
        assert payload["calendars_fetched_at"] == "2026-09-03T08:00:00+00:00"

    def test_the_stamp_is_utc_whatever_the_clock_was(self, home, store, config, monkeypatch):
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(EVENTS, OK_STATUS))
        local = datetime.fromisoformat("2026-09-03T10:00:00+02:00")
        runner.refresh_calendars(config, store, now=local)
        assert stored(home)["calendars_fetched_at"] == "2026-09-03T08:00:00+00:00"

    def test_the_window_starts_on_the_familys_today(self, store, config, monkeypatch):
        seen = []
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(EVENTS, OK_STATUS, seen))
        # 23:30 UTC is already the 4th in Berlin.
        runner.refresh_calendars(config, store,
                                 now=datetime(2026, 9, 3, 23, 30, tzinfo=timezone.utc))
        assert seen[0]["today"] == date(2026, 9, 4)
        assert seen[0]["days_ahead"] == 14

    def test_it_leaves_the_brief_alone(self, home, store, config, monkeypatch):
        # The state the board labels amber: today's times under yesterday's words.
        write_stored(home, {
            "generated_for_date": "2026-09-02", "generated_at": "2026-09-02T04:00:00+00:00",
            "headline": "Yesterday's headline", "note": "Yesterday's note",
            "note_kind": "fact", "events": [], "model": "claude-haiku-4-5",
        })
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(EVENTS, OK_STATUS))
        runner.refresh_calendars(config, store)
        payload = stored(home)
        assert payload["generated_for_date"] == "2026-09-02"
        assert payload["generated_at"] == "2026-09-02T04:00:00+00:00"
        assert payload["headline"] == "Yesterday's headline"
        assert payload["note"] == "Yesterday's note"
        assert payload["events"] == EVENTS

    def test_a_failed_feed_leaves_its_own_events_up(self, home, store, config, monkeypatch):
        # A missing event is invisible; a stale one is at least on the wall.
        write_stored(home, {"generated_for_date": "2026-09-03", "headline": "Hi",
                            "note": "There", "events": EVENTS})
        monkeypatch.setattr(runner, "fetch_events", fake_fetch([], FAILED_STATUS))
        runner.refresh_calendars(config, store, now=NOW)
        payload = stored(home)
        assert payload["events"] == EVENTS
        assert payload["calendar_statuses"] == FAILED_STATUS

    def test_one_dead_feed_does_not_freeze_the_healthy_ones(self, home, store, config,
                                                            monkeypatch):
        # The whole point of merging per feed: School answered, so School is
        # fresh, while Family holds what it last gave us. Freezing everything
        # would hide a new event behind somebody else's broken URL for as long
        # as nobody fixed it.
        write_stored(home, {"generated_for_date": "2026-09-03", "headline": "Hi",
                            "note": "There", "events": EVENTS})
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(SCHOOL, MIXED_STATUS))
        runner.refresh_calendars(config, store, now=NOW)
        titles = [(e["calendar"], e["title"]) for e in stored(home)["events"]]
        assert titles == [("Family", "Swimming"), ("School", "Sports day")]

    def test_a_healthy_feed_that_dropped_an_event_really_drops_it(self, home, store,
                                                                  config, monkeypatch):
        # Nothing stale is kept for a feed that answered, or a deleted
        # appointment would live on the board for ever.
        write_stored(home, {"events": EVENTS + SCHOOL})
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(SCHOOL, MIXED_STATUS))
        runner.refresh_calendars(config, store, now=NOW)
        assert [e["title"] for e in stored(home)["events"]] == ["Swimming", "Sports day"]

        # Now Family answers too, with nothing in it. Swimming is gone.
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(SCHOOL, [
            {"label": "Family", "ok": True, "detail": "", "count": 0},
            {"label": "School", "ok": True, "detail": "", "count": 1}]))
        runner.refresh_calendars(config, store, now=NOW)
        assert [e["title"] for e in stored(home)["events"]] == ["Sports day"]

    def test_stale_events_outside_the_window_are_dropped(self, home, store, config, monkeypatch):
        # A permanently broken feed empties out as the days pass rather than
        # keeping a growing tail of appointments that already happened.
        write_stored(home, {"events": EVENTS})
        monkeypatch.setattr(runner, "fetch_events", fake_fetch([], FAILED_STATUS))
        # A month on, 2026-09-03 is behind the fourteen-day window.
        runner.refresh_calendars(config, store,
                                 now=datetime(2026, 10, 3, 8, tzinfo=timezone.utc))
        assert stored(home)["events"] == []

    def test_a_paused_feed_does_not_keep_its_old_events(self, home, store, config, monkeypatch):
        # Switching a calendar off means switching it off.
        write_stored(home, {"events": EVENTS})
        paused = [{"label": "Family", "ok": None, "detail": "paused", "count": 0}]
        monkeypatch.setattr(runner, "fetch_events", fake_fetch([], paused))
        runner.refresh_calendars(config, store, now=NOW)
        assert stored(home)["events"] == []

    def test_two_feeds_sharing_a_label_are_not_doubled(self, home, store, config, monkeypatch):
        # Labels are the only identity an event carries, so a duplicate label
        # must degrade to one copy rather than two.
        write_stored(home, {"events": EVENTS})
        both = [{"label": "Family", "ok": False, "detail": "could not fetch", "count": 0},
                {"label": "Family", "ok": True, "detail": "", "count": 1}]
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(EVENTS, both))
        runner.refresh_calendars(config, store, now=NOW)
        assert stored(home)["events"] == EVENTS

    def test_a_failed_feed_on_the_first_run_stores_what_there_is(self, home, store,
                                                                 config, monkeypatch):
        monkeypatch.setattr(runner, "fetch_events", fake_fetch([], FAILED_STATUS))
        runner.refresh_calendars(config, store, now=NOW)
        assert stored(home)["events"] == []

    def test_no_calendars_configured_touches_nothing_but_the_stamp(self, store, config):
        # fetch_events is the real one here: with an empty list it must not
        # reach the network at all.
        config["calendars"] = []
        payload = runner.refresh_calendars(config, store)
        assert payload["events"] == []
        assert payload["calendar_statuses"] == []
        assert payload["calendars_fetched_at"]

    def test_it_needs_no_api_key(self, home, store, config, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(EVENTS, OK_STATUS))
        runner.refresh_calendars(config, store)  # a fetch costs nothing
        assert stored(home)["events"] == EVENTS


class TestWriteBrief:
    def test_it_uses_the_stored_events_rather_than_fetching_again(self, home, store,
                                                                  config, api_key, monkeypatch):
        monkeypatch.setattr(runner, "fetch_events",
                            lambda *a, **k: pytest.fail("write_brief must not fetch"))
        write_stored(home, {"events": EVENTS, "calendar_statuses": OK_STATUS,
                            "calendars_fetched_at": "2026-09-03T05:00:00+00:00"})
        client = FakeClient()
        runner.write_brief(config, store, today=date(2026, 9, 3), client=client)
        payload = stored(home)
        assert payload["headline"] == "Big morning"
        assert payload["events"] == EVENTS
        assert "Swimming" in client.messages.calls[0]["messages"][0]["content"]

    def test_it_carries_the_refresh_keys_forward(self, home, store, config, api_key):
        write_stored(home, {"events": EVENTS, "calendar_statuses": FAILED_STATUS,
                            "calendars_fetched_at": "2026-09-03T05:00:00+00:00"})
        runner.write_brief(config, store, today=date(2026, 9, 3), client=FakeClient())
        payload = stored(home)
        assert payload["calendars_fetched_at"] == "2026-09-03T05:00:00+00:00"
        assert payload["calendar_statuses"] == FAILED_STATUS

    def test_it_records_the_note_in_the_history(self, home, store, config, api_key):
        runner.write_brief(config, store, today=date(2026, 9, 3), client=FakeClient())
        history = json.loads((home / "content_history.json").read_text())
        assert history[-1]["note"] == "An octopus fact."
        assert history[-1]["date"] == "2026-09-03"

    def test_it_works_with_no_payload_at_all(self, store, config, api_key):
        payload = runner.write_brief(config, store, today=date(2026, 9, 3),
                                     client=FakeClient())
        assert payload["events"] == []
        assert payload["generated_for_date"] == "2026-09-03"

    def test_a_failure_leaves_the_previous_board_untouched(self, home, store, config, api_key):
        write_stored(home, {"generated_for_date": "2026-09-02", "headline": "Kept",
                            "note": "Kept", "events": EVENTS})
        client = FakeClient(raises=RuntimeError("the API is down"))
        with pytest.raises(GenerationError):
            runner.write_brief(config, store, today=date(2026, 9, 3), client=client)
        assert stored(home)["headline"] == "Kept"

    def test_it_refuses_without_an_api_key(self, store, config, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(GenerationError, match="ANTHROPIC_API_KEY"):
            runner.write_brief(config, store, today=date(2026, 9, 3), client=FakeClient())


class TestRun:
    def test_it_still_does_both(self, home, store, config, api_key, monkeypatch):
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(EVENTS, OK_STATUS))
        runner.run(config, store, today=date(2026, 9, 3), client=FakeClient())
        payload = stored(home)
        assert payload["events"] == EVENTS
        assert payload["headline"] == "Big morning"
        assert payload["generated_for_date"] == "2026-09-03"
        assert payload["calendars_fetched_at"]

    def test_the_date_override_moves_the_fetch_window(self, store, config, api_key,
                                                      monkeypatch):
        seen = []
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(EVENTS, OK_STATUS, seen))
        runner.run(config, store, today=date(2026, 12, 24), client=FakeClient())
        assert seen[0]["today"] == date(2026, 12, 24)

    def test_a_missing_key_fails_before_the_fetch(self, store, config, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setattr(runner, "fetch_events",
                            lambda *a, **k: pytest.fail("should not have fetched"))
        with pytest.raises(GenerationError, match="ANTHROPIC_API_KEY"):
            runner.run(config, store, today=date(2026, 9, 3))


def refuse(what):
    def _refuse(*args, **kwargs):
        pytest.fail(f"{what} should not have run")
    return _refuse


class TestTick:
    def run_tick(self, home, monkeypatch, now):
        """`generate.py --tick` with the clock pinned."""
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return now if tz is None else now.astimezone(tz)
        monkeypatch.setattr(cli, "datetime", Clock)
        return cli.main(["--tick", "--config", str(home / "config.yaml")])

    def test_nothing_due_calls_nothing(self, home, monkeypatch):
        # Fetched ten minutes ago, brief written for today: the normal case on
        # a five-minute cron line, and it must cost nothing at all.
        write_stored(home, {"generated_for_date": "2026-09-03",
                            "calendars_fetched_at": "2026-09-03T05:50:00+00:00",
                            "headline": "Kept", "note": "Kept", "events": EVENTS})
        monkeypatch.setattr(cli, "refresh_calendars", refuse("the fetch"))
        monkeypatch.setattr(cli, "write_brief", refuse("the model call"))
        # 08:00 Berlin.
        assert self.run_tick(home, monkeypatch, datetime(2026, 9, 3, 6, tzinfo=timezone.utc)) == 0
        assert stored(home)["headline"] == "Kept"

    def test_a_due_refresh_runs_without_the_model(self, home, monkeypatch):
        write_stored(home, {"generated_for_date": "2026-09-03",
                            "calendars_fetched_at": "2026-09-03T04:00:00+00:00",
                            "headline": "Kept", "note": "Kept", "events": []})
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(EVENTS, OK_STATUS))
        monkeypatch.setattr(cli, "write_brief", refuse("the model call"))
        assert self.run_tick(home, monkeypatch, datetime(2026, 9, 3, 6, tzinfo=timezone.utc)) == 0
        payload = stored(home)
        assert payload["events"] == EVENTS
        assert payload["headline"] == "Kept"

    def test_a_due_brief_is_written_once(self, home, monkeypatch, api_key):
        write_stored(home, {"generated_for_date": "2026-09-02",
                            "calendars_fetched_at": "2026-09-03T05:50:00+00:00",
                            "headline": "Yesterday", "note": "Yesterday", "events": EVENTS})
        client = FakeClient()
        monkeypatch.setattr(cli, "write_brief",
                            lambda config, store, **kw: runner.write_brief(
                                config, store, client=client, **kw))
        # 08:00 Berlin, so the brief is owed and the fetch is not.
        assert self.run_tick(home, monkeypatch, datetime(2026, 9, 3, 6, tzinfo=timezone.utc)) == 0
        payload = stored(home)
        assert payload["headline"] == "Big morning"
        assert payload["generated_for_date"] == "2026-09-03"
        assert len(client.messages.calls) == 1

    def test_a_failed_brief_reports_but_keeps_the_board(self, home, monkeypatch, api_key):
        write_stored(home, {"generated_for_date": "2026-09-02",
                            "calendars_fetched_at": "2026-09-03T05:50:00+00:00",
                            "headline": "Yesterday", "note": "Yesterday", "events": EVENTS})
        client = FakeClient(raises=RuntimeError("the API is down"))
        monkeypatch.setattr(cli, "write_brief",
                            lambda config, store, **kw: runner.write_brief(
                                config, store, client=client, **kw))
        assert self.run_tick(home, monkeypatch, datetime(2026, 9, 3, 6, tzinfo=timezone.utc)) == 1
        # Untouched, so the next tick five minutes later asks again.
        assert stored(home)["headline"] == "Yesterday"

    def test_the_first_tick_of_a_new_pi_fetches_and_writes(self, home, monkeypatch, api_key):
        monkeypatch.setattr(runner, "fetch_events", fake_fetch(EVENTS, OK_STATUS))
        client = FakeClient()
        monkeypatch.setattr(cli, "write_brief",
                            lambda config, store, **kw: runner.write_brief(
                                config, store, client=client, **kw))
        assert self.run_tick(home, monkeypatch, datetime(2026, 9, 3, 6, tzinfo=timezone.utc)) == 0
        payload = stored(home)
        assert payload["events"] == EVENTS
        assert payload["headline"] == "Big morning"

    def test_tick_and_date_are_refused(self, home):
        with pytest.raises(SystemExit):
            cli.main(["--tick", "--date", "2026-12-24", "--config", str(home / "config.yaml")])


class TestOnlyOneTickAtATime:
    """A tick can outlive its five-minute slot; the next one must not pay twice."""

    def test_the_second_holder_is_turned_away(self, tmp_path):
        lock = tmp_path / ".tick.lock"
        with cli.only_one_tick(lock) as first:
            assert first is True
            # A second process, same file. flock is per open file description,
            # so this is what a second cron run would see.
            with cli.only_one_tick(lock) as second:
                assert second is False

    def test_the_lock_is_released_when_the_tick_finishes(self, tmp_path):
        lock = tmp_path / ".tick.lock"
        with cli.only_one_tick(lock) as first:
            assert first is True
        with cli.only_one_tick(lock) as again:
            assert again is True

    def test_an_overlapping_tick_does_nothing_and_does_not_fail(self, home, monkeypatch):
        monkeypatch.setattr(runner, "fetch_events", refuse("the fetch"))
        monkeypatch.setattr(cli, "write_brief", refuse("the model call"))
        with cli.only_one_tick(home / cli.LOCK_FILE):
            # Nothing has ever been generated, so everything would be owed.
            assert cli.main(["--tick", "--config", str(home / "config.yaml")]) == 0
        assert not (home / "dashboard_data.json").exists()
