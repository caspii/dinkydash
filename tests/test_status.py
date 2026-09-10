"""`/healthz/worker`: the worker's pulse for whoever is watching from outside (DIN-54).

* **single mode has no such path.** No worker, and no database to read;
* **cloud mode answers it with no session, no family and no token**, because
  the monitor has none of those and the row it reads names nobody;
* **200 means a pass finished within the allowance; 503 means never, or too
  long ago.** The allowance comes from `DINKYDASH_WORKER_STALE_AFTER`;
* **it is neither cached nor indexed**, and it is never the platform's probe
  (`tests/test_deploy_spec.py` holds that line).

The parsing tests run everywhere; the rest skips without
`DINKYDASH_TEST_DATABASE_URL`.
"""

from datetime import datetime, timedelta, timezone

import pytest

from dinkydash import heartbeat
from dinkydash.store import FileStore
from tests.conftest import client_for, forget_unowned_rows
from web import create_app
from web.routes import status


def test_single_mode_has_no_worker_status(tmp_path, monkeypatch):
    monkeypatch.delenv("DINKYDASH_MODE", raising=False)
    (tmp_path / "config.yaml").write_text('family_name: "The Wilsons"\n')
    client = client_for(create_app(FileStore(tmp_path / "config.yaml")))
    assert client.get("/healthz/worker").status_code == 404


class TestTheAllowance:
    def test_it_defaults_to_three_missed_passes(self, monkeypatch):
        monkeypatch.delenv(status.STALE_AFTER, raising=False)
        assert status.stale_after() == heartbeat.DEFAULT_STALE_AFTER == 900

    def test_the_environment_overrides_it(self, monkeypatch):
        monkeypatch.setenv(status.STALE_AFTER, "1800")
        assert status.stale_after() == 1800

    def test_nonsense_falls_back_rather_than_failing_every_request(self, monkeypatch):
        monkeypatch.setenv(status.STALE_AFTER, "fifteen minutes")
        assert status.stale_after() == heartbeat.DEFAULT_STALE_AFTER

    @pytest.mark.parametrize("value", ["0", "-60"])
    def test_it_is_never_zero(self, monkeypatch, value):
        monkeypatch.setenv(status.STALE_AFTER, value)
        assert status.stale_after() == 1


# -- in cloud mode -----------------------------------------------------------

@pytest.fixture
def cloud(pg_pool, monkeypatch):
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
    monkeypatch.delenv(status.STALE_AFTER, raising=False)
    forget_unowned_rows(pg_pool)
    yield client_for(create_app(pool=pg_pool))
    forget_unowned_rows(pg_pool)


class TestWhatItSays:
    def test_before_any_pass_it_is_never_and_a_503(self, cloud):
        response = cloud.get("/healthz/worker")
        assert response.status_code == 503
        assert response.get_json() == {
            "status": "never", "age_seconds": None, "last_pass": None}

    def test_after_a_pass_it_is_alive(self, cloud, pg_pool):
        heartbeat.beat(pg_pool, 3, 1, 1234)
        response = cloud.get("/healthz/worker")
        assert response.status_code == 200
        said = response.get_json()
        assert said["status"] == "ok"
        assert 0 <= said["age_seconds"] < 60
        assert said["last_pass"]["families"] == 3
        assert said["last_pass"]["failed"] == 1
        assert said["last_pass"]["took_ms"] == 1234

    def test_a_pass_too_long_ago_is_stale_and_a_503(self, cloud, pg_pool):
        heartbeat.beat(pg_pool, 3, 0, 1234,
                       now=datetime.now(timezone.utc) - timedelta(hours=2))
        response = cloud.get("/healthz/worker")
        assert response.status_code == 503
        said = response.get_json()
        assert said["status"] == "stale"
        assert 7100 <= said["age_seconds"] <= 7300

    def test_the_allowance_is_read_from_the_environment(self, cloud, pg_pool, monkeypatch):
        heartbeat.beat(pg_pool, 3, 0, 1234,
                       now=datetime.now(timezone.utc) - timedelta(hours=2))
        monkeypatch.setenv(status.STALE_AFTER, str(3 * 3600))
        assert cloud.get("/healthz/worker").status_code == 200

    def test_the_row_it_serves_is_a_time_and_three_counts(self, cloud, pg_pool):
        heartbeat.beat(pg_pool, 3, 0, 1234)
        said = cloud.get("/healthz/worker").get_json()
        assert set(said) == {"status", "age_seconds", "last_pass"}
        assert set(said["last_pass"]) == {"passed_at", "families", "failed", "took_ms"}


class TestHowItAnswers:
    def test_it_needs_no_session(self, cloud):
        """A redirect to `/login` here would be a monitor that alerts for ever."""
        response = cloud.get("/healthz/worker")
        assert response.status_code in (200, 503)
        assert "Location" not in response.headers

    def test_it_is_neither_cached_nor_indexed(self, cloud, pg_pool):
        for _ in ("never", "ok"):
            headers = cloud.get("/healthz/worker").headers
            assert headers["Cache-Control"] == "no-store"
            assert headers["X-Robots-Tag"] == "noindex"
            heartbeat.beat(pg_pool, 1, 0, 10)

    def test_it_promises_not_to_tell_a_referrer(self, cloud):
        assert cloud.get("/healthz/worker").headers["Referrer-Policy"] == "no-referrer"

    def test_the_platforms_own_probe_is_untouched_by_it(self, cloud):
        """`/healthz` still reads nothing, so it still answers before any pass."""
        assert cloud.get("/healthz").status_code == 200
        assert cloud.get("/healthz/worker").status_code == 503
