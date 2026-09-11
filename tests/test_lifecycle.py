"""Trial deadlines, manual access and the dashboard after a lapse (DIN-52)."""

from datetime import datetime, timedelta, timezone

import pytest

from dinkydash import lifecycle, runner
from dinkydash.budget import PostgresBudget
from dinkydash.claude_client import GenerationError
from tests.conftest import board_path, client_for
from tests.test_generate import FakeClient


@pytest.mark.parametrize("elapsed,show", [
    (timedelta(0), True),
    (timedelta(days=30, microseconds=-1), True),
    (timedelta(days=30), False),
    (timedelta(days=31), False),
])
def test_frozen_period_ends_at_exactly_thirty_days(elapsed, show):
    ended = datetime(2026, 9, 9, tzinfo=timezone(timedelta(hours=2)))
    access = lifecycle.Access(ended, ended.astimezone(timezone.utc) + elapsed)
    assert access.ended
    assert access.show_last_board is show
    with pytest.raises(GenerationError, match="has ended"):
        access.require_live()


def test_active_access_has_no_display_grace_period():
    access = lifecycle.Access(None, datetime.now(timezone.utc))
    assert not access.ended and not access.show_last_board
    access.require_live()


def test_upgrade_gives_legacy_trials_deadlines_and_stamps_status_changes(pg_pool):
    from dinkydash import db

    with pg_pool.connection() as conn, conn.transaction(force_rollback=True), conn.cursor() as cur:
        cur.execute("CREATE SCHEMA lapse_migration_test")
        cur.execute("SET LOCAL search_path TO lapse_migration_test, public")
        upgrade = db.MIGRATIONS_DIR / "005_family_lapse.sql"
        for path in db.migrations():
            if path == upgrade:
                break
            cur.execute(path.read_text())
        cur.execute("""INSERT INTO families (screen_token, created_at)
                       VALUES ('legacy-trial-token', '2026-01-01T12:00:00+02:00') RETURNING id""")
        legacy = cur.fetchone()[0]
        cur.execute("""INSERT INTO families (screen_token, status)
                       VALUES ('legacy-lapsed-token', 'lapsed'), ('legacy-paid-token', 'active')""")
        cur.execute(upgrade.read_text())
        cur.execute("SELECT trial_ends_at FROM families WHERE id = %s", (legacy,))
        assert cur.fetchone() == (datetime(2026, 1, 15, 10, tzinfo=timezone.utc),)
        cur.execute("SELECT lapsed_at IS NOT NULL FROM families WHERE status = 'lapsed'")
        assert cur.fetchone() == (True,)
        cur.execute("UPDATE families SET status = 'lapsed' WHERE id = %s", (legacy,))
        cur.execute("SELECT lapsed_at = now() FROM families WHERE id = %s", (legacy,))
        assert cur.fetchone() == (True,)
        cur.execute("UPDATE families SET status = 'active' WHERE id = %s", (legacy,))
        cur.execute("SELECT lapsed_at FROM families WHERE id = %s", (legacy,))
        assert cur.fetchone() == (None,)
        cur.execute("""INSERT INTO families (screen_token) VALUES ('new-trial-token')
                       RETURNING trial_ends_at - created_at""")
        assert cur.fetchone() == (timedelta(days=14),)


def update_family(pool, family_id, assignments, values=()):
    # Only tests supply the SQL; values always remain bound parameters.
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(f"UPDATE families SET {assignments} WHERE id = %s",
                    (*values, family_id))


@pytest.fixture
def hosted(pg_pool, pg_family, monkeypatch):
    import anthropic
    from dinkydash.pgstore import PostgresStore
    from web import create_app

    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "test-session-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    model = FakeClient()
    monkeypatch.setattr(anthropic, "Anthropic", lambda: model)
    store = PostgresStore(pg_pool, pg_family)
    store.save_config({"family_name": "Invented family", "timezone": "Europe/Berlin",
                       "brief_time": "00:00", "people": [],
                       "recurring": [{"title": "Set the table", "choices": ["Alex", "Sam"]}],
                       "special_dates": [{"title": "A holiday", "date": "12/25"}],
                       "calendars": [{"label": "Family", "enabled": True,
                                      "url": "https://example.com/private-xxxx/basic.ics"}]})
    config = store.load_config()
    store.save_agenda(config, {"events": [{"title": "Saved appointment", "all_day": False,
                                          "time": "09:00", "date": "2026-09-08",
                                          "start": "2026-09-08T09:00:00+02:00"}]})
    store.save_brief(config, {"generated_for_date": "2026-09-08",
                              "generated_at": "2026-09-08T04:00:00+00:00",
                              "headline": "Saved headline", "note": "Saved note"})
    parent = client_for(create_app(pool=pg_pool))
    with parent.session_transaction() as session:
        session["user_id"] = 1
        session["family_id"] = str(pg_family)
    return parent, store, model


@pytest.mark.parametrize("offset,ended", [("1 day", False), ("0 seconds", True), ("-1 day", True)])
def test_trial_deadline_is_enforced_before_the_worker_sweep(pg_pool, pg_family, offset, ended):
    update_family(pg_pool, pg_family, "trial_ends_at = now() + %s::interval", (offset,))
    access = lifecycle.access_for(pg_pool, pg_family)
    assert access.ended is ended
    from worker import family_ids
    assert (pg_family in family_ids(pg_pool)) is not ended


def test_sweep_preserves_the_deadline_and_is_repeatable(pg_pool, pg_family):
    # Same instant expressed in a non-UTC timezone.
    deadline = datetime(2026, 1, 2, 1, tzinfo=timezone(timedelta(hours=9)))
    update_family(pg_pool, pg_family, "trial_ends_at = %s", (deadline,))
    assert lifecycle.expire_trials(pg_pool) == 1
    assert lifecycle.expire_trials(pg_pool) == 0
    with pg_pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, lapsed_at FROM families WHERE id = %s", (pg_family,))
        assert cur.fetchone() == ("lapsed", deadline)


@pytest.mark.parametrize("action", ["worker", "rewrite", "refresh", "check"])
@pytest.mark.parametrize("persisted", [False, True])
def test_expired_accounts_cannot_fetch_or_generate(
        hosted, pg_pool, pg_family, monkeypatch, action, persisted):
    from worker import tick_all

    parent, store, model = hosted
    update_family(pg_pool, pg_family, "trial_ends_at = now()")
    if persisted:
        lifecycle.expire_trials(pg_pool)
    before = store.load_payload(store.load_config())
    fetched = []

    def fetch(*args, **kwargs):
        fetched.append(True)
        raise AssertionError("A lapsed family fetched a calendar")

    monkeypatch.setattr(runner, "fetch_events", fetch)
    monkeypatch.setattr("web.routes.settings.describe_feed", fetch)
    if action == "worker":
        # Even a family selected just before its deadline must be refused.
        monkeypatch.setattr("worker.family_ids", lambda _: [pg_family])
        tick_all(pg_pool)
    elif action == "check":
        response = parent.post("/settings/calendars/new", data={
            "action": "check", "url": "https://example.com/private-xxxx/basic.ics"})
        assert "has ended" in response.get_data(as_text=True)
    else:
        path = "/settings/generate" if action == "rewrite" else "/settings/refresh-now"
        response = parent.post(path, follow_redirects=True)
        assert "has ended" in response.get_data(as_text=True)
    assert fetched == []
    assert model.messages.calls == []
    assert PostgresBudget(pg_pool, pg_family).used_today() == (0, 0)
    assert store.load_payload(store.load_config()) == before


def test_deadline_is_checked_again_after_a_slow_calendar_fetch(
        hosted, pg_pool, pg_family, monkeypatch):
    parent, store, model = hosted
    update_family(pg_pool, pg_family, "trial_ends_at = now() + interval '1 day'")

    def fetch(*args, **kwargs):
        update_family(pg_pool, pg_family, "trial_ends_at = now()")
        return [], []

    monkeypatch.setattr(runner, "fetch_events", fetch)
    parent.post("/settings/generate")
    assert model.messages.calls == []
    assert store.load_payload(store.load_config())["headline"] == "Saved headline"
    assert PostgresBudget(pg_pool, pg_family).used_today() == (0, 0)


def test_lapsed_board_dates_and_turns_do_not_advance(hosted, pg_pool, pg_family, monkeypatch):
    from dinkydash import config as config_module

    parent, _, model = hosted
    update_family(pg_pool, pg_family, "trial_ends_at = now() - interval '1 day'")
    path = board_path(pg_pool, pg_family)
    first = parent.get(path)
    monkeypatch.setattr(config_module, "today_for", lambda _: datetime(2030, 1, 1).date())
    second = parent.get(path)
    assert first.data == second.data
    text = first.get_data(as_text=True)
    for saved in ("Saved headline", "Saved appointment", "Saved note", "Tuesday, 8 September",
                  "Set the table", "has ended", "dates and turns are paused"):
        assert saved in text
    assert "no-store" in first.headers["Cache-Control"]
    assert first.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert model.messages.calls == []


def test_thirty_days_later_only_the_ended_message_is_rendered(hosted, pg_pool, pg_family):
    parent, _, model = hosted
    update_family(pg_pool, pg_family, "trial_ends_at = now() - interval '30 days'")
    page = parent.get(board_path(pg_pool, pg_family)).get_data(as_text=True)
    assert "Your trial or subscription has ended" in page
    for content in ("Invented family", "Saved headline", "Saved appointment", "Saved note",
                    "Set the table", "A holiday"):
        assert content not in page
    # An eventual reactivation reaches the wall: the script's timer, and the
    # <noscript> reload for a browser without one.
    assert 'data-reload="300"' in page and 'http-equiv="refresh"' in page
    assert model.messages.calls == []


def test_an_expired_family_with_no_brief_gets_a_message_not_a_waiting_screen(
        hosted, pg_pool, pg_family):
    parent, _, _ = hosted
    with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM generations WHERE family_id = %s", (pg_family,))
    update_family(pg_pool, pg_family, "trial_ends_at = now()")
    page = parent.get(board_path(pg_pool, pg_family)).get_data(as_text=True)
    assert "has ended" in page
    assert "Writing" not in page and "Saved appointment" not in page


def test_paid_reactivation_clears_lapse_and_ignores_the_old_trial_deadline(
        hosted, pg_pool, pg_family, monkeypatch):
    parent, _, model = hosted
    update_family(pg_pool, pg_family, "trial_ends_at = now() - interval '40 days'")
    lifecycle.expire_trials(pg_pool)
    update_family(pg_pool, pg_family, "status = 'active'")
    assert lifecycle.expire_trials(pg_pool) == 0
    assert not lifecycle.access_for(pg_pool, pg_family).ended
    with pg_pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT lapsed_at FROM families WHERE id = %s", (pg_family,))
        assert cur.fetchone() == (None,)
    monkeypatch.setattr(runner, "fetch_events", lambda *a, **kw: ([], []))
    parent.post("/settings/generate")
    assert len(model.messages.calls) == 1
    page = parent.get(board_path(pg_pool, pg_family)).get_data(as_text=True)
    assert "has ended" not in page and "Big morning" in page
    # A later subscription lapse starts a fresh grace period.
    update_family(pg_pool, pg_family, "status = 'lapsed'")
    access = lifecycle.access_for(pg_pool, pg_family)
    assert access.show_last_board
    assert access.now - access.lapsed_at < timedelta(minutes=1)


def test_expiry_keeps_settings_and_export_access(hosted, pg_pool, pg_family):
    parent, _, _ = hosted
    update_family(pg_pool, pg_family, "trial_ends_at = now()")
    home = parent.get("/settings/").get_data(as_text=True)
    assert "has ended" in home
    assert 'type="submit" disabled' in home
    assert parent.get("/settings/account/export").status_code == 200
    assert parent.post("/settings/system", data={"family_name": "Updated family"}).status_code == 302
