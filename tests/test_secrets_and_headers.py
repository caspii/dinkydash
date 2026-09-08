"""What must not leak, and the headers that stop it.

Four things that all have to be true before a stranger's calendar is on our
infrastructure, and that are each invisible until they are not:

* a failed fetch must not publish the calendar's URL, which is a password;
* `/healthz` must answer without touching anything that can be slow or broken;
* every response must promise not to tell a third party what URL it was on;
* no page may ask Google for a font, which is how the URL would get told.
"""

import pathlib

import pytest
import requests

from dinkydash.calendars import FeedError, fetch_feed, zone
from dinkydash.store import FileStore
from tests.conftest import client_for
from web import create_app

from datetime import date

SECRET = "https://calendar.google.com/calendar/ical/x/private-3f9c1a7bDEADBEEF/basic.ics"
REPO = pathlib.Path(__file__).resolve().parent.parent

CONFIG = '''\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
people:
  - id: mia12345
    name: "Mia"
    date_of_birth: "2017-03-15"
'''


@pytest.fixture
def client(tmp_path):
    (tmp_path / "config.yaml").write_text(CONFIG)
    return client_for(create_app(FileStore(tmp_path / "config.yaml")))


def _raising(exc):
    """A `requests.get` stand-in that fails the way the real one does."""
    def _get(url, timeout=None, **kwargs):
        raise exc
    return _get


def _http_error(status, reason):
    """The exception `raise_for_status()` builds, URL and all."""
    response = requests.Response()
    response.status_code = status
    response.reason = reason
    response.url = SECRET
    return requests.HTTPError(
        f"{status} Client Error: {reason} for url: {SECRET}", response=response)


def _fetch(monkeypatch, exc):
    monkeypatch.setattr(requests, "get", _raising(exc))
    with pytest.raises(FeedError) as caught:
        fetch_feed(SECRET, date(2026, 9, 3), date(2026, 9, 17), zone("UTC"),
                   label="Dad's", timeout=1)
    return str(caught.value)


class TestTheCalendarUrlNeverEscapes:
    """PLAN.md bug 8. `requests` puts the whole URL in every error message.

    An iCal secret address is a password: whoever holds it reads that family's
    calendar indefinitely, and there is no way to see who has. This text reaches
    generate.log and the settings page.
    """

    def test_a_404_names_the_status_and_not_the_url(self, monkeypatch):
        message = _fetch(monkeypatch, _http_error(404, "Not Found"))
        assert "404" in message
        assert "private-3f9c1a7bDEADBEEF" not in message
        assert "calendar.google.com" not in message
        assert "https://" not in message

    def test_a_connection_failure_says_nothing_about_where(self, monkeypatch):
        message = _fetch(monkeypatch, requests.ConnectionError(f"failed to resolve {SECRET}"))
        assert "could not reach" in message
        assert "DEADBEEF" not in message

    def test_a_timeout_says_so(self, monkeypatch):
        message = _fetch(monkeypatch, requests.Timeout(f"timed out for url: {SECRET}"))
        assert "did not answer in time" in message
        assert "DEADBEEF" not in message

    def test_an_unexpected_failure_gives_only_its_class(self, monkeypatch):
        message = _fetch(monkeypatch, ValueError(SECRET))
        assert "ValueError" in message
        assert "DEADBEEF" not in message

    def test_a_parse_failure_does_not_quote_the_calendar(self):
        # A parser error normally quotes the line it choked on, which is
        # somebody's appointment.
        from dinkydash.calendars import parse_feed
        with pytest.raises(FeedError) as caught:
            parse_feed("BEGIN:VCALENDAR\nSUMMARY:Therapy appointment\nnonsense",
                       date(2026, 9, 3), date(2026, 9, 17), zone("UTC"))
        assert "Therapy" not in str(caught.value)

    def test_the_status_a_broken_feed_reports_is_safe_too(self, monkeypatch):
        # fetch_events puts the message into `calendar_statuses`, which the
        # settings page renders.
        from dinkydash import calendars
        monkeypatch.setattr(requests, "get", _raising(_http_error(403, "Forbidden")))
        _events, statuses = calendars.fetch_events(
            [{"label": "Dad's", "url": SECRET, "enabled": True}],
            date(2026, 9, 3), zone("UTC"), timeout=1)
        assert statuses[0]["label"] == "Dad's"
        assert "DEADBEEF" not in statuses[0]["detail"]


class TestHealthz:
    def test_it_says_ok(self, client):
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"

    def test_it_reports_a_commit(self, client, monkeypatch):
        monkeypatch.setenv("GIT_SHA", "abc1234")
        assert client.get("/healthz").get_json()["commit"] == "abc1234"

    def test_an_unknown_commit_is_not_an_error(self, client, monkeypatch):
        monkeypatch.delenv("GIT_SHA", raising=False)
        assert client.get("/healthz").get_json()["commit"] == "unknown"

    def test_it_touches_no_storage(self, client, monkeypatch):
        """A health check that reads the config turns a slow disk into a failed
        deploy, and hands anyone who can reach the port a way to restart the app."""
        def explode(*args, **kwargs):
            raise AssertionError("/healthz must not read the store")
        monkeypatch.setattr(FileStore, "load_config", explode)
        monkeypatch.setattr(FileStore, "load_payload", explode)
        assert client.get("/healthz").status_code == 200

    def test_it_is_not_indexed_or_cached(self, client):
        headers = client.get("/healthz").headers
        assert headers["X-Robots-Tag"] == "noindex"
        assert headers["Cache-Control"] == "no-store"

    def test_it_says_nothing_about_the_family(self, client):
        assert "Wilsons" not in client.get("/healthz").get_data(as_text=True)


class TestReferrerPolicy:
    """Cloud mode puts the board at /s/<token>, and the token is the credential."""

    @pytest.mark.parametrize("path", ["/", "/settings/", "/healthz", "/preview",
                                      "/manifest.webmanifest", "/no-such-page"])
    def test_every_response_promises_not_to_tell(self, client, path):
        assert client.get(path).headers["Referrer-Policy"] == "no-referrer"

    def test_a_redirect_carries_it_too(self, client):
        # Where a Referer would otherwise be sent by the browser following it.
        response = client.post("/settings/system",
                               data={"family_name": "The Bakers", "timezone": "UTC"})
        assert response.status_code == 302
        assert response.headers["Referrer-Policy"] == "no-referrer"


class TestNothingAsksGoogleForAFont:
    """Self-hosted Nunito. The board reloads every five minutes; each request to
    fonts.gstatic.com from a tokenised URL would hand it to Google."""

    @pytest.mark.parametrize("directory", ["web/templates", "website/templates"])
    def test_no_template_links_google_fonts(self, directory):
        offenders = [
            str(path.relative_to(REPO))
            for path in (REPO / directory).rglob("*.html")
            if "fonts.googleapis.com" in path.read_text()
            or "fonts.gstatic.com" in path.read_text()
        ]
        assert offenders == []

    def test_the_font_files_are_really_there(self):
        fonts = REPO / "web" / "static" / "fonts"
        for name in ("nunito-latin.woff2", "nunito-latin-ext.woff2"):
            path = fonts / name
            assert path.exists(), name
            # wOF2, so a failed download committed as an HTML error page fails here.
            assert path.read_bytes()[:4] == b"wOF2", name
        assert (fonts / "OFL.txt").exists(), "the licence ships with the font"

    def test_the_board_serves_them_itself(self, client):
        page = client.get("/").get_data(as_text=True)
        assert "/static/fonts.css" in page
        assert client.get("/static/fonts.css").status_code == 200
        assert client.get("/static/fonts/nunito-latin.woff2").status_code == 200
