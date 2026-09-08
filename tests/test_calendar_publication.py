"""A settings edit must invalidate both stored and in-flight calendar results."""

from concurrent.futures import ThreadPoolExecutor
from copy import copy, deepcopy
from datetime import datetime, timezone
from threading import Event

import pytest

import generate as cli
from dinkydash import board, runner
from dinkydash.claude_client import GenerationError
from dinkydash.schedule import due
from test_generate import FakeClient
from test_store_contract import store  # noqa: F401 - run against both backends

NOW = datetime(2026, 9, 3, 8, tzinfo=timezone.utc)
PRIVATE = "Private appointment marker"
FAMILY = {"id": "family", "label": "Family", "url": "https://example.com/family.ics",
          "enabled": True}
SCHOOL = {"id": "school", "label": "School", "url": "https://example.com/school.ics",
          "enabled": True}


def event(title, label):
    return {"title": title, "calendar": label, "date": "2026-09-03",
            "time": "15:45", "all_day": False, "start": "2026-09-03T15:45:00+02:00",
            "location": None}


@pytest.fixture
def seeded(store, tmp_path):
    config = store.load_config()
    # File mode must coordinate settings and agenda even in different directories.
    (tmp_path / "payload").mkdir()
    config["data_file"] = "payload/data.json"
    config["calendars"] = deepcopy([FAMILY, SCHOOL])
    store.save_config(config)
    agenda = {"events": [event(PRIVATE, "Family"), event("Sports day", "School")],
              "calendar_statuses": [{"label": name, "ok": True, "count": 1}
                                    for name in ("Family", "School")],
              "calendars_fetched_at": NOW.isoformat()}
    store.save_agenda(config, agenda)
    store.save_brief(config, {"generated_for_date": "2026-09-02",
                             "headline": "Previous headline", "note": "Previous note"})
    return config, agenda


def change(config, kind):
    updated = deepcopy(config)
    if kind == "remove":
        updated["calendars"].pop(0)
    else:
        field, value = {
            "filter": ("shared_with", ["parent@example.com"]),
            "pause": ("enabled", False),
            "rename": ("label", "Renamed family"),
            "url": ("url", "https://example.com/replacement.ics"),
        }[kind]
        updated["calendars"][0][field] = value
    return updated


@pytest.mark.parametrize("kind", ["filter", "remove", "pause", "rename", "url"])
@pytest.mark.parametrize("failed", [False, True], ids=["in-flight-fetch", "cached-fallback"])
def test_an_old_refresh_cannot_restore_events_after_a_calendar_edit(
        store, seeded, kind, failed, monkeypatch):
    config, agenda = seeded
    paused, resume = Event(), Event()
    load_payload = store.load_payload
    editor = copy(store)

    def fetch(*args, **kwargs):
        if failed:
            return [], [{"label": "Family", "ok": False},
                        {"label": "School", "ok": False}]
        paused.set()
        assert resume.wait(5), "settings did not finish while the fetch was paused"
        return deepcopy(agenda["events"]), deepcopy(agenda["calendar_statuses"])

    def read_previous(config):
        previous = load_payload(config)
        if failed:
            # The failure fallback already has the private events in hand.
            paused.set()
            assert resume.wait(5), "settings did not finish while fallback was paused"
        return previous

    monkeypatch.setattr(runner, "fetch_events", fetch)
    monkeypatch.setattr(store, "load_payload", read_previous)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(runner.refresh_calendars, config, store, now=NOW)
        try:
            assert paused.wait(5)
            updated = change(config, kind)
            # Use a second store object, as a concurrent web request does.
            editor.save_config(updated)
            after_edit = load_payload(updated)
        finally:
            resume.set()
        with pytest.raises(GenerationError, match="Calendar settings changed"):
            pending.result(timeout=5)

    monkeypatch.setattr(store, "load_payload", load_payload)
    assert after_edit["events"] == [event("Sports day", "School")]
    assert not after_edit.get("calendars_fetched_at")
    payload = store.load_payload(updated)
    assert payload["events"] == after_edit["events"]
    assert payload["headline"] == "Previous headline"
    assert due(updated, payload, NOW)["refresh"]
    assert PRIVATE not in str(board.build_view(updated, payload, NOW.date()))

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    client = FakeClient()
    runner.write_brief(updated, store, today=NOW.date(), client=client)
    assert PRIVATE not in client.messages.calls[0]["messages"][0]["content"]


def test_a_failed_fetch_under_the_new_filter_cannot_reuse_old_events(
        store, seeded, monkeypatch):
    config, _ = seeded
    updated = change(config, "filter")
    store.save_config(updated)
    monkeypatch.setattr(runner, "fetch_events", lambda *a, **k: (
        [], [{"label": "Family", "ok": False}, {"label": "School", "ok": False}]))
    runner.refresh_calendars(updated, store, now=NOW)
    assert store.load_payload(updated)["events"] == [event("Sports day", "School")]


def test_a_stale_tick_skips_the_model_and_retries_with_current_settings(
        store, seeded, monkeypatch):
    config, agenda = seeded
    store.save_agenda(config, dict(agenda, calendars_fetched_at="2026-09-03T06:00:00+00:00"))
    updated = change(config, "filter")
    client = FakeClient()
    calls = []

    class Clock:
        @staticmethod
        def now(tz):
            return NOW

    def fetch(feeds, *args, **kwargs):
        calls.append(feeds)
        if len(calls) == 1:
            store.save_config(updated)
            return agenda["events"], agenda["calendar_statuses"]
        return [event("Sports day", "School")], agenda["calendar_statuses"]

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    monkeypatch.setattr(cli, "datetime", Clock)
    monkeypatch.setattr(runner, "fetch_events", fetch)
    monkeypatch.setattr(cli, "write_brief", lambda *args, **kwargs:
                        runner.write_brief(*args, client=client, **kwargs))

    assert cli.tick(config, store) == 1
    assert client.messages.calls == []
    assert store.load_payload(updated)["headline"] == "Previous headline"
    assert cli.tick(store.load_config(), store) == 0
    assert calls[1] == updated["calendars"]
    assert len(client.messages.calls) == 1
    assert PRIVATE not in client.messages.calls[0]["messages"][0]["content"]


def test_unrelated_edits_and_id_backfilling_keep_the_agenda(store, seeded):
    config, agenda = seeded
    updated = deepcopy(config)
    updated["theme"] = "dark"
    updated["calendars"][0]["id"] = "backfilled-id"
    store.save_config(updated)
    assert store.load_payload(updated)["events"] == agenda["events"]
    # An in-flight refresh is still usable when only unrelated settings changed.
    assert store.save_agenda(config, agenda) is True


def test_explicitly_saving_a_calendar_still_clears_its_cache(store, seeded):
    config, _ = seeded
    store.save_config(config, invalidate_calendars=("Family",))
    payload = store.load_payload(config)
    assert payload["events"] == [event("Sports day", "School")]
    assert not payload.get("calendars_fetched_at")


@pytest.mark.parametrize("field,value", [("timezone", "Pacific/Auckland"),
                                         ("calendar_days_ahead", 7)])
def test_a_changed_calendar_window_invalidates_the_old_results(store, seeded, field, value):
    config, agenda = seeded
    updated = dict(config, **{field: value})
    store.save_config(updated)
    assert store.load_payload(updated)["events"] == []
    assert store.save_agenda(config, agenda) is False
