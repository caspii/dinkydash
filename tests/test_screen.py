"""The board on a wall: `/s/<token>`, rotation, and the redirects (DIN-42).

Five claims, and the first is what the whole feature exists for:

* **a screen needs no session.** A kitchen tablet cannot sign in, so the board
  is reached by an unguessable URL and nothing else;
* **the token is a bearer credential and is treated like one** — never in a log,
  never in an index, never in a shared cache, and never echoed back on a miss;
* **a wrong token is a 404 and never a 403**, whether it was mistyped, rotated
  away, or invented;
* **the rate limit counts misses, not requests.** A real screen reloads for
  years and must never be refused;
* **rotation is the only revocation there is**, so it has to work.

Skips without `DINKYDASH_TEST_DATABASE_URL`. Cloud mode is where the screen
exists at all: single mode serves the board at `/` and has no token, so the
route is a 404 there, which is asserted below with no database at all.
"""

import logging
import re

import pytest
import yaml

from dinkydash import config as config_module
from dinkydash import screens
from dinkydash.store import FileStore
from tests.conftest import board_path, client_for
from web import create_app
from web.routes.auth import NoTokens

CONFIG = '''\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
theme: dark
people:
  - id: mia12345
    name: "Mia"
    date_of_birth: "2017-03-15"
recurring:
  - id: job12345
    title: "Set the table"
    choices: ["Mia"]
'''


def a_board_for(today):
    """A written board, so these tests read a real one rather than the waiting
    screen. Chores and countdowns are recomputed from config on every render,
    but nothing is rendered at all until a payload exists."""
    return {"generated_for_date": today.isoformat(),
            "generated_at": f"{today.isoformat()}T04:00:00+00:00",
            "headline": "Swimming, then football",
            "note": "An octopus fact.",
            "events": [], "calendars_fetched_at": f"{today.isoformat()}T04:00:00+00:00"}


@pytest.fixture
def cloud(pg_pool, pg_family, monkeypatch):
    from dinkydash.pgstore import PostgresStore

    store = PostgresStore(pg_pool, pg_family)
    store.save_config(yaml.safe_load(CONFIG))
    config = store.load_config()
    board = a_board_for(config_module.today_for(config))
    store.save_agenda(config, board)
    store.save_brief(config, board)
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
    return create_app(pool=pg_pool)


@pytest.fixture
def anyone(cloud):
    """A client with no session at all. What a wall panel is."""
    return client_for(cloud)


@pytest.fixture
def parent(cloud, pg_family):
    """A signed-in client, for the settings half."""
    client = client_for(cloud)
    with client.session_transaction() as stored:
        stored["user_id"] = 1
        stored["family_id"] = str(pg_family)
    return client


@pytest.fixture
def path(pg_pool, pg_family):
    return board_path(pg_pool, pg_family)


# -- a screen signs in to nothing -------------------------------------------

class TestTheBoardNeedsNoSession:
    def test_an_anonymous_request_gets_the_board(self, anyone, path):
        page = anyone.get(path)
        assert page.status_code == 200
        body = page.get_data(as_text=True)
        assert "Set the table" in body and "Mia" in body

    def test_the_family_on_the_board_is_the_token_s_family(self, anyone, path):
        assert "The Wilsons" in anyone.get(path).get_data(as_text=True)

    def test_and_the_theme_comes_from_their_config(self, anyone, path):
        assert 'data-theme="dark"' in anyone.get(path).get_data(as_text=True)

    def test_the_manifest_is_reachable_without_one_too(self, anyone, path):
        """Otherwise "save to home screen" on the panel gets a login redirect
        and the saved icon is a browser default."""
        got = anyone.get(f"{path}/manifest.webmanifest")
        assert got.status_code == 200
        assert got.get_json()["start_url"] == path

    def test_the_board_links_to_that_manifest_and_not_the_private_one(
            self, anyone, path):
        body = anyone.get(path).get_data(as_text=True)
        assert f'href="{path}/manifest.webmanifest"' in body

    def test_the_page_asks_nothing_of_anybody_else(self, anyone, path):
        """A screen URL in a `Referer` is a screen URL given away. The board
        is already free of third-party requests (DIN-32); this is the assertion
        that keeps it that way on the one page a stranger can open."""
        body = anyone.get(path).get_data(as_text=True)
        for external in ("//fonts.googleapis.com", "//fonts.gstatic.com",
                         "http://", "https://"):
            assert external not in body


# -- and it is a credential -------------------------------------------------

class TestItIsTreatedAsACredential:
    def test_it_is_not_indexed_and_not_cached(self, anyone, path):
        headers = anyone.get(path).headers
        assert headers["X-Robots-Tag"] == "noindex, nofollow"
        assert "no-store" in headers["Cache-Control"]

    def test_the_refusal_carries_the_same_headers(self, anyone):
        headers = anyone.get("/s/zzzzzzzzzzzz").headers
        assert headers["X-Robots-Tag"] == "noindex, nofollow"
        assert "no-store" in headers["Cache-Control"]

    def test_no_referrer_on_it_like_everything_else(self, anyone, path):
        assert anyone.get(path).headers["Referrer-Policy"] == "no-referrer"

    def test_a_wrong_token_is_never_echoed_back(self, anyone):
        """A typo of a real token is nearly a real token."""
        page = anyone.get("/s/zzzzzzzzzzzz")
        assert "zzzzzzzzzzzz" not in page.get_data(as_text=True)

    def test_the_log_filter_takes_the_token_out_of_a_request_line(self):
        """The one place `%(U)s` cannot help. Gunicorn's access format is built
        from the path *without* the query string, which is what keeps a magic
        link's `?t=` out of the platform's log — and exactly what would put a
        screen token in it, thousands of times, from one panel."""
        record = logging.LogRecord("gunicorn.access", logging.INFO, "", 0,
                                   'GET /s/abcdefgh2345 HTTP/1.1', None, None)
        NoTokens().filter(record)
        assert "abcdefgh2345" not in record.getMessage()
        assert "/s/[redacted]" in record.getMessage()

    def test_and_leaves_ordinary_paths_alone(self):
        """The /s/ route prefix distinguishes credentials from ordinary paths."""
        for line in ('GET /settings/people HTTP/1.1', 'GET /static/fonts.css'):
            record = logging.LogRecord("gunicorn.access", logging.INFO, "", 0,
                                       line, None, None)
            NoTokens().filter(record)
            assert record.getMessage() == line

    def test_it_still_scrubs_a_sign_in_link_as_well(self):
        """Two credentials travel in URLs here; one filter covers both."""
        record = logging.LogRecord("werkzeug", logging.INFO, "", 0,
                                   'GET /login/link?t=SECRETTOKEN HTTP/1.1',
                                   None, None)
        NoTokens().filter(record)
        assert "SECRETTOKEN" not in record.getMessage()


# -- a wrong token ----------------------------------------------------------

class TestAWrongToken:
    @pytest.mark.parametrize("token,why", [
        ("zzzzzzzzzzzz", "well-formed and never issued"),
        ("short", "too short for the column"),
        ("z" * 40, "longer than the column allows"),
        ("WP-ADMIN-PHP", "not the alphabet"),
        ("abcd0123efgh", "hex digits the alphabet excludes"),
    ])
    def test_is_a_404(self, anyone, token, why):
        assert anyone.get(f"/s/{token}").status_code == 404, why

    def test_never_a_403(self, anyone):
        """"Forbidden" would confirm the token exists and is merely not allowed,
        which is the one thing a guess must not learn."""
        assert anyone.get("/s/zzzzzzzzzzzz").status_code != 403

    def test_a_rotated_token_stops_working(self, anyone, pg_pool, pg_family, path):
        assert anyone.get(path).status_code == 200
        screens.rotate(pg_pool, pg_family)
        assert anyone.get(path).status_code == 404

    def test_and_the_new_one_works(self, anyone, pg_pool, pg_family):
        token = screens.rotate(pg_pool, pg_family)
        assert anyone.get(f"/s/{token}").status_code == 200

    def test_a_malformed_token_costs_no_query(self, anyone, monkeypatch):
        """A crawler walking `/s/wp-login.php` should cost a string comparison,
        not a connection from a pool with 22 of them behind it."""
        def explode(*args, **kwargs):
            raise AssertionError("a malformed token reached the database")

        monkeypatch.setattr(screens, "family_for_token", explode)
        # `looks_like_a_token` runs first, inside `family_for_token`... so the
        # check that matters is the one it makes before touching the pool.
        assert not screens.looks_like_a_token("wp-login.php")


# -- the limit is on the misses ---------------------------------------------

class TestTheRateLimit:
    CALLER = {"DO-Connecting-IP": "93.184.216.34"}

    def test_a_real_screen_is_never_refused(self, anyone, path):
        """It reloads every few minutes for years. Counting its requests would
        put a rate limit on somebody's kitchen wall."""
        from web.routes.screen import MOST_MISSES

        for _ in range(MOST_MISSES * 2):
            assert anyone.get(path, headers=self.CALLER).status_code == 200

    def test_misses_are_counted_and_then_refused(self, anyone):
        from web.routes.screen import MOST_MISSES

        codes = [anyone.get("/s/zzzzzzzzzzzz", headers=self.CALLER).status_code
                 for _ in range(MOST_MISSES + 2)]
        assert codes[:MOST_MISSES] == [404] * MOST_MISSES
        assert codes[MOST_MISSES:] == [429, 429]

    def test_a_valid_token_still_works_while_a_caller_is_over_the_limit(
            self, anyone, path):
        """The limiter is about making somebody else do the looking, not about
        the family whose screen it is."""
        from web.routes.screen import MOST_MISSES

        for _ in range(MOST_MISSES + 1):
            anyone.get("/s/zzzzzzzzzzzz", headers=self.CALLER)
        assert anyone.get(path, headers=self.CALLER).status_code == 200

    def test_the_refusal_says_nothing_about_what_was_asked_for(self, anyone):
        from web.routes.screen import MOST_MISSES

        for _ in range(MOST_MISSES + 1):
            anyone.get("/s/zzzzzzzzzzzz", headers=self.CALLER)
        page = anyone.get("/s/zzzzzzzzzzzz", headers=self.CALLER)
        assert page.status_code == 429
        assert "zzzzzzzzzzzz" not in page.get_data(as_text=True)


# -- rotation ---------------------------------------------------------------

class TestRotation:
    def test_link_and_qr_use_the_configured_https_origin(
            self, parent, cloud, path, monkeypatch):
        from web.routes import settings

        cloud.config["APP_HOST"] = "app.dinkydash.co"
        drawn = []
        monkeypatch.setattr(settings, "qr_svg", lambda link: drawn.append(link))
        page = parent.get("/settings/screen")
        link = f"https://app.dinkydash.co{path}"
        assert link in page.get_data(as_text=True)
        assert drawn == [link]

    def test_the_settings_page_shows_the_link_and_a_qr(self, parent, path):
        page = parent.get("/settings/screen").get_data(as_text=True)
        assert path in page
        assert "<svg" in page and 'class="qr"' in page

    def test_and_says_plainly_what_the_link_is(self, parent):
        page = parent.get("/settings/screen").get_data(as_text=True)
        assert "Anyone with this link can see your board" in page

    def test_the_qr_is_drawn_here_and_not_fetched(self, parent):
        """Handing this URL to a QR service would be publishing the credential."""
        page = parent.get("/settings/screen").get_data(as_text=True)
        assert "chart.googleapis.com" not in page
        assert "api.qrserver.com" not in page

    def test_pressing_the_button_changes_the_link(self, parent, pg_pool, pg_family):
        before = screens.token_for(pg_pool, pg_family)
        parent.post("/settings/screen", data={"action": "rotate"})
        assert screens.token_for(pg_pool, pg_family) != before

    def test_and_says_every_screen_needs_the_new_one(self, parent):
        landed = parent.post("/settings/screen", data={"action": "rotate"},
                             follow_redirects=True)
        assert "the old link has stopped working" in landed.get_data(as_text=True)

    def test_rotating_needs_a_csrf_token_like_every_other_write(self, cloud, pg_family):
        """A plain client, so the form carries nothing. `web/session.py` has no
        switch to turn this off, in either mode."""
        bare = cloud.test_client()
        with bare.session_transaction() as stored:
            stored["user_id"] = 1
            stored["family_id"] = str(pg_family)
        assert bare.post("/settings/screen", data={"action": "rotate"}).status_code == 400

    def test_the_new_token_is_the_shape_the_column_allows(self, pg_pool, pg_family):
        token = screens.rotate(pg_pool, pg_family)
        assert 10 <= len(token) <= 32
        assert set(token) <= set(config_module.ID_ALPHABET)

    def test_rotating_a_family_that_is_gone_says_so_rather_than_raising(self, pg_pool):
        import uuid

        assert screens.rotate(pg_pool, uuid.uuid4()) is None


# -- where the board is, now that it moved ----------------------------------

class TestTheRootAndThePreview:
    def test_the_root_sends_a_signed_in_parent_to_the_settings(self, parent):
        landed = parent.get("/")
        assert landed.status_code == 302
        assert landed.headers["Location"].endswith("/settings/")

    def test_and_a_signed_out_visitor_to_the_login(self, anyone):
        landed = anyone.get("/")
        assert landed.status_code == 302
        assert landed.headers["Location"].endswith("/login")

    def test_view_board_on_the_settings_home_points_at_the_screen(
            self, parent, path, monkeypatch):
        from web.routes import settings

        def unused_qr(link):
            pytest.fail("The settings home should not generate a QR code")

        monkeypatch.setattr(settings, "qr_svg", unused_qr)
        assert f'href="{path}"' in parent.get("/settings/").get_data(as_text=True)

    def test_the_preview_frames_the_board_rather_than_the_redirect(
            self, parent, path):
        page = parent.get("/preview").get_data(as_text=True)
        assert f'src="{path}"' in page
        assert len(re.findall(re.escape(f'src="{path}"'), page)) == 3


# -- and none of it reaches a self-hoster -----------------------------------

class TestSingleModeIsUntouched:
    @pytest.fixture
    def single(self, tmp_path):
        (tmp_path / "config.yaml").write_text(CONFIG)
        store = FileStore(tmp_path / "config.yaml")
        config = store.load_config()
        board = a_board_for(config_module.today_for(config))
        store.save_agenda(config, board)
        store.save_brief(config, board)
        return create_app(store)

    def test_the_board_is_still_at_the_root(self, single):
        page = single.test_client().get("/")
        assert page.status_code == 200
        assert "Set the table" in page.get_data(as_text=True)

    def test_and_there_is_no_screen_route_at_all(self, single):
        """A 404 rather than a route that exists and refuses. One family on
        their own network has no token and nothing to rotate."""
        assert single.test_client().get("/s/abcdefgh2345").status_code == 404

    def test_the_screen_page_still_says_what_a_home_network_means(self, single):
        page = single.test_client().get("/settings/screen").get_data(as_text=True)
        assert "There is no password on this" in page
        assert "Change the link" not in page
