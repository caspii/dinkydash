"""Static files are versioned and cached, and the pages are quick to move between.

A settings page used to cost three round trips in a row before it could draw a
word — the page, then the stylesheet, then the font — because Flask serves a
static file with `no-cache` and every navigation re-asked for both. What holds
the fix in place: every static URL a template emits carries the file's content
version, a request with that version is cached for a year, and nothing rides
on the response that would stop a cache matching it.
"""

import hashlib
import json
import os
import pathlib
import re

import pytest

from dinkydash.store import FileStore
from tests.conftest import client_for
from web import create_app
from web.assets import CACHED_FOR_A_YEAR, VERSION_LENGTH, static_url, version_of

REPO = pathlib.Path(__file__).resolve().parent.parent
STATIC = REPO / "web" / "static"

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


def expected_version(name):
    return hashlib.sha256((STATIC / name).read_bytes()).hexdigest()[:VERSION_LENGTH]


def preload_href(page):
    match = re.search(r'<link rel="preload" href="([^"]+)" as="font" type="font/woff2" crossorigin>', page)
    assert match, "the Latin font is preloaded from the head"
    return match.group(1)


# -- the URL --------------------------------------------------------------------

class TestVersionedUrls:
    def test_static_url_carries_the_files_content_version(self, client):
        with client.application.test_request_context():
            assert static_url("favicon.svg") == f"/static/favicon.svg?v={expected_version('favicon.svg')}"

    def test_a_missing_file_gets_the_bare_url(self, client):
        """So the 404 happens in the open, where it always did."""
        with client.application.test_request_context():
            assert static_url("no-such-file.png") == "/static/no-such-file.png"
            assert static_url("fonts") == "/static/fonts"  # a directory is not a file
            assert version_of("../config.yaml") is None  # and nothing outside static

    def test_the_version_follows_the_content(self, client, tmp_path):
        """Same name, new bytes, new URL — that is what lets the old one be cached for a year."""
        app = client.application
        app.static_folder = str(tmp_path)
        asset = tmp_path / "a.css"
        with app.test_request_context():
            asset.write_text("a { color: red }")
            first = version_of("a.css")
            asset.write_text("a { color: blue }")  # same length: only the mtime moves
            os.utime(asset, ns=(asset.stat().st_atime_ns, asset.stat().st_mtime_ns + 1_000_000))
            second = version_of("a.css")
            asset.write_text("a { color: green }")  # a different length
            third = version_of("a.css")
        assert len({first, second, third}) == 3
        assert all(re.fullmatch(r"[0-9a-f]{12}", v) for v in (first, second, third))

    def test_nothing_in_web_uses_a_bare_static_url(self):
        """A `url_for('static', ...)` outside assets.py is a file cached for a year under a
        URL that never changes — or, without the version, one never cached at all."""
        offenders = []
        for path in list((REPO / "web").rglob("*.html")) + list((REPO / "web").rglob("*.py")):
            if path.name == "assets.py":
                continue
            text = path.read_text()
            if "url_for('static'" in text or 'url_for("static"' in text:
                offenders.append(str(path.relative_to(REPO)))
        assert offenders == []


# -- the header -------------------------------------------------------------------

class TestTheCacheHeader:
    def test_the_current_version_is_cached_for_a_year(self, client):
        response = client.get(f"/static/favicon.svg?v={expected_version('favicon.svg')}")
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == CACHED_FOR_A_YEAR

    def test_a_bare_url_keeps_flasks_default(self, client):
        """Somebody typing the URL by hand always sees the current file."""
        response = client.get("/static/favicon.svg")
        assert response.status_code == 200
        assert "no-cache" in response.headers["Cache-Control"]
        assert "max-age" not in response.headers["Cache-Control"]

    def test_and_so_does_a_stale_version(self, client):
        """A page rendered before a deploy must not pin the new file for a year."""
        response = client.get("/static/favicon.svg?v=000000000000")
        assert response.status_code == 200
        assert "no-cache" in response.headers["Cache-Control"]

    def test_a_conditional_request_keeps_the_year(self, client):
        url = f"/static/favicon.svg?v={expected_version('favicon.svg')}"
        etag = client.get(url).headers["ETag"]
        again = client.get(url, headers={"If-None-Match": etag})
        assert again.status_code == 304
        assert again.headers["Cache-Control"] == CACHED_FOR_A_YEAR

    def test_a_static_file_never_carries_the_session(self, client):
        """`Vary: Cookie` on a font is a font no cache can match, because Flask re-signs a
        permanent session — a new cookie value — on every page. Pages keep the cookie."""
        client.get("/settings/")  # mints the CSRF token into the session
        with client.session_transaction() as sess:
            sess.permanent = True
        static = client.get(f"/static/favicon.svg?v={expected_version('favicon.svg')}")
        assert "Set-Cookie" not in static.headers
        assert "Cookie" not in static.headers.get("Vary", "")
        page = client.get("/settings/")
        assert "Set-Cookie" in page.headers
        assert "Cookie" in page.headers["Vary"]


# -- the font ---------------------------------------------------------------------

class TestTheFont:
    @pytest.mark.parametrize("path", ["/", "/settings/", "/preview"])
    def test_the_rules_are_inline_and_the_latin_file_is_preloaded(self, client, path):
        """One round trip fewer on a cold load: no stylesheet to fetch before the font."""
        page = client.get(path).get_data(as_text=True)
        assert "@font-face" in page
        assert "fonts.css" not in page
        href = preload_href(page)
        assert href == f"/static/fonts/nunito-latin.woff2?v={expected_version('fonts/nunito-latin.woff2')}"
        assert page.count(href) == 2, "the preload and the @font-face name the same URL"
        assert f"nunito-latin-ext.woff2?v={expected_version('fonts/nunito-latin-ext.woff2')}" in page

    def test_the_preloaded_font_is_served_for_a_year(self, client):
        page = client.get("/settings/").get_data(as_text=True)
        response = client.get(preload_href(page))
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == CACHED_FOR_A_YEAR
        assert response.get_data()[:4] == b"wOF2"

    def test_the_manifest_icons_are_versioned(self, client):
        manifest = client.get("/settings/manifest.webmanifest").get_json()
        assert manifest["icons"]
        for icon in manifest["icons"]:
            assert re.search(r"\?v=[0-9a-f]{12}$", icon["src"]), icon
            assert client.get(icon["src"]).headers["Cache-Control"] == CACHED_FOR_A_YEAR


# -- moving between pages ----------------------------------------------------------

class TestMovingBetweenPages:
    def test_the_settings_shell_crossfades(self, client):
        page = client.get("/settings/").get_data(as_text=True)
        assert "@view-transition { navigation: auto; }" in page
        assert "prefers-reduced-motion: reduce" in page

    def test_the_board_does_not(self, client):
        """It reloads itself, and a reload is not a navigation worth animating."""
        assert "@view-transition" not in client.get("/").get_data(as_text=True)

    def test_settings_links_are_prerendered_and_the_export_is_not(self, client):
        page = client.get("/settings/people").get_data(as_text=True)
        match = re.search(r'<script type="speculationrules">\s*(.*?)\s*</script>', page, re.S)
        assert match, "the settings shell carries speculation rules"
        rules = json.loads(match.group(1))
        assert set(rules) == {"prefetch", "prerender"}
        for kind in ("prefetch", "prerender"):
            [rule] = rules[kind]
            assert rule["eagerness"] == "moderate"
            clauses = rule["where"]["and"]
            assert {"href_matches": "/settings/*"} in clauses
            # A hover must not download a family's data.
            assert {"not": {"href_matches": "/settings/account/export"}} in clauses
