"""One container, two hostnames: what `wsgi.py` must route where.

The dispatcher is four lines of logic guarding a $5-a-month decision, and every
way it can be wrong is quiet. A board served on the marketing hostname is a
family's calendar on a page Google crawls. A marketing page served on the board
hostname is a broken product. An unknown hostname that 404s takes the whole
deploy down, because App Platform's health check arrives on a name nobody
configured.

`dispatch` takes both apps as arguments precisely so this file can use stubs:
building the real board app in cloud mode wants a database, and none of these
assertions is about a database.
"""

import pytest

from wsgi import _board_host, _normalise, create_application, dispatch

SITE, BOARD = "the site", "the board"


def stub(name):
    """A WSGI app that answers with its own name, so the route is the assertion."""
    def application(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [name.encode()]
    return application


def route(host, board_host="app.dinkydash.co"):
    """Send a request carrying `host` through the dispatcher; return which app answered."""
    application = dispatch(stub(SITE), stub(BOARD), board_host)
    body = application({"HTTP_HOST": host}, lambda status, headers: None)
    return b"".join(body).decode()


class TestRouting:
    def test_the_board_hostname_gets_the_board(self):
        assert route("app.dinkydash.co") == BOARD

    def test_the_marketing_hostname_gets_the_site(self):
        assert route("dinkydash.co") == SITE

    def test_www_gets_the_site(self):
        """The site redirects www to the apex itself; the dispatcher must let it."""
        assert route("www.dinkydash.co") == SITE

    def test_an_unknown_hostname_gets_the_site_not_the_board(self):
        """App Platform's own name is not in the spec, and its health check uses it.

        Answering is not optional — a 404 here fails the health check and rolls
        the deploy back. Answering *with the site* is the safe half of the
        choice: it holds no family's data.
        """
        assert route("clownfish-app-7xt89.ondigitalocean.app") == SITE

    def test_a_missing_host_header_gets_the_site(self):
        application = dispatch(stub(SITE), stub(BOARD), "app.dinkydash.co")
        body = application({}, lambda status, headers: None)
        assert b"".join(body).decode() == SITE

    def test_the_forwarded_host_header_cannot_choose_the_app(self):
        """Upstream of App Platform is the public internet.

        If `X-Forwarded-Host` picked the app, anyone could ask for the board by
        setting a header. Only `Host` counts, and App Platform matches its
        custom domains on that anyway.
        """
        application = dispatch(stub(SITE), stub(BOARD), "app.dinkydash.co")
        environ = {"HTTP_HOST": "dinkydash.co",
                   "HTTP_X_FORWARDED_HOST": "app.dinkydash.co"}
        assert b"".join(application(environ, lambda s, h: None)).decode() == SITE


class TestHostNormalisation:
    def test_the_port_is_ignored(self):
        """gunicorn listens on 8080 behind the proxy, so the port is often present."""
        assert route("app.dinkydash.co:8080") == BOARD

    def test_case_is_ignored(self):
        assert route("App.DinkyDash.co") == BOARD

    def test_surrounding_whitespace_is_ignored(self):
        assert route(" app.dinkydash.co ") == BOARD

    def test_the_configured_host_is_normalised_too(self):
        """A stray capital or port in the app spec must not break routing."""
        assert route("app.dinkydash.co", board_host="APP.DinkyDash.co:443") == BOARD

    @pytest.mark.parametrize("host", ["", None, "   "])
    def test_nothing_normalises_to_empty(self, host):
        assert _normalise(host) == ""


class TestRefusals:
    def test_no_board_host_is_a_refusal_to_start(self, monkeypatch):
        """Silently unreachable is the failure this prevents."""
        monkeypatch.delenv("DINKYDASH_APP_HOST", raising=False)
        with pytest.raises(RuntimeError, match="DINKYDASH_APP_HOST"):
            _board_host()

    def test_an_empty_board_host_is_the_same_refusal(self, monkeypatch):
        monkeypatch.setenv("DINKYDASH_APP_HOST", "")
        with pytest.raises(RuntimeError, match="DINKYDASH_APP_HOST"):
            _board_host()

    def test_the_board_host_is_read_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("DINKYDASH_APP_HOST", "app.example.test")
        assert _board_host() == "app.example.test"

    def test_single_mode_refuses_to_build_the_dispatcher(self, monkeypatch):
        """A Pi runs app.py. Importing the site's renderer onto it is not a feature."""
        monkeypatch.delenv("DINKYDASH_MODE", raising=False)
        with pytest.raises(RuntimeError, match="app.py"):
            create_application()


class TestReporting:
    def test_the_cloud_entry_point_starts_reporting_before_building_either_app(self, monkeypatch):
        """A container that cannot build its apps should say so somewhere other
        than a log nobody is reading. No DSN in this test: `init` is replaced."""
        calls = []
        monkeypatch.setenv("DINKYDASH_MODE", "cloud")
        monkeypatch.setenv("DINKYDASH_APP_HOST", "app.example.test")
        monkeypatch.setattr("dinkydash.sentry.init",
                            lambda component, **kw: calls.append(("init", component)) or True)
        monkeypatch.setattr("web.create_app",
                            lambda *a, **k: calls.append("app") or stub(BOARD))
        monkeypatch.setattr("website.site.create_site_app",
                            lambda *a, **k: calls.append("site") or stub(SITE))
        create_application()
        assert calls[0] == ("init", "web")
        assert set(calls[1:]) == {"app", "site"}
