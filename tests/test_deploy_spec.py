"""What `.do/app.yaml` promises about the health check, held against the code.

The spec is reviewed like code, but a spec and a route drift apart in silence:
the probe path is a string in one file and a decorator in another, and the
first sign of a mismatch is a deploy that never goes live. Two other files
already read the spec — `test_auth.py` for the access-log format,
`test_tenancy.py` for the absence of a family id. This one is for the probe.

* **the probe arrives on the platform's own hostname**, which is in no
  `domains` block, so it is the *site* that has to answer it;
* **the board app answers it too**, with no session and no database — the same
  path on `app.dinkydash.co` must not redirect to `/login`;
* **it is never `/healthz/worker`.** That path reads the database and answers
  503 when the worker is quiet, which is what a monitor wants and what a probe
  must never do: three quiet probes restart the container, and a rolled-back
  deploy would be the answer to a dead worker.
"""

from pathlib import Path

import pytest
import yaml

from tests.conftest import client_for
from web import create_app
from website.site import create_site_app
from wsgi import dispatch

REPO = Path(__file__).resolve().parent.parent
PLATFORM_HOST = "clownfish-app-7xt89.ondigitalocean.app"


@pytest.fixture(scope="module")
def probe():
    spec = yaml.safe_load((REPO / ".do" / "app.yaml").read_text())
    (site,) = spec["services"]
    return site["health_check"]


class Exploding:
    """A pool that fails on any use: the probe must not touch it."""

    def __getattr__(self, name):
        raise AssertionError(f"the probe touched the pool ({name})")


def failing_board(environ, start_response):
    raise AssertionError("the probe reached the board app on an unknown host")


class TestTheProbePath:
    def test_the_site_answers_it_on_the_platforms_own_hostname(self, probe):
        application = dispatch(create_site_app(), failing_board, "app.dinkydash.co")
        client = create_site_app().test_client()
        response = client.get(probe["http_path"], headers={"Host": PLATFORM_HOST})
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"
        # And through the dispatcher, which is what gunicorn actually runs.
        status = []
        body = application({"HTTP_HOST": PLATFORM_HOST, "PATH_INFO": probe["http_path"],
                            "REQUEST_METHOD": "GET", "SERVER_NAME": "localhost",
                            "SERVER_PORT": "8080", "wsgi.url_scheme": "http"},
                           lambda s, h: status.append(s))
        assert b"".join(body) and status[0].startswith("200")

    def test_the_board_app_answers_it_with_no_session_and_no_database(self, probe, monkeypatch):
        pytest.importorskip("psycopg")
        monkeypatch.setenv("DINKYDASH_MODE", "cloud")
        monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
        client = client_for(create_app(pool=Exploding()))
        response = client.get(probe["http_path"])
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"

    def test_it_is_not_the_worker_status(self, probe):
        assert probe["http_path"] != "/healthz/worker"
        assert not probe["http_path"].startswith("/healthz/")

    def test_it_is_a_path_and_not_a_tcp_check(self, probe):
        """Without `http_path` App Platform falls back to a TCP check, which a
        process that binds the port and 500s every request would pass."""
        assert probe["http_path"].startswith("/")

    def test_the_container_has_time_to_wait_for_its_database(self, probe):
        """`db.ready` waits before the process comes up; the probe's patience
        has to outlast it, or a slow-but-healthy database fails every deploy."""
        db = pytest.importorskip("dinkydash.db")
        patience = (probe["initial_delay_seconds"]
                    + probe["period_seconds"] * probe["failure_threshold"])
        assert patience > db.STARTUP_TIMEOUT
