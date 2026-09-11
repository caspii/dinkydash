"""How the dashboard refreshes itself, and what a screen shows when it cannot.

The dashboard used to reload itself with a `<meta http-equiv="refresh">`. A
reload that fails — the Wi-Fi dropped, the hosted app is mid-deploy — replaces
the dashboard with the browser's error page, and a kiosk on a wall has nobody
to press Back. So the page now fetches its next copy in the background and
swaps the body in only when one arrives; a copy that never arrives leaves the
last good dashboard on the wall with a "Reconnecting" badge saying when it was
last updated (DIN-60). The tag survives only inside `<noscript>`, for a browser
with scripting off.

The swapping and the badge need a browser, and are checked by hand — see
"Measuring the dashboard" in `web/CLAUDE.md`. What pytest can pin is the
contract between the template and its script: the values the script reads,
the element it fills in, and that the reload is not two mechanisms racing.
"""

import json
import re
from pathlib import Path

import pytest

from dinkydash import config as config_module
from dinkydash.store import FileStore
from tests.conftest import client_for
from web import create_app

SET_UP = 'family_name: "The Wilsons"\ntimezone: "Europe/Berlin"\n'


def page_for(directory, payload=None):
    """A single-mode dashboard for a set-up family, with or without a board.

    Each caller gets its own directory: a test that asks for both pages must
    not have the waiting one find the ready one's `dashboard_data.json`.
    """
    directory.mkdir()
    path = directory / "config.yaml"
    path.write_text(SET_UP)
    if payload is not None:
        (directory / "dashboard_data.json").write_text(json.dumps(payload))
    return client_for(create_app(FileStore(path))).get("/").get_data(as_text=True)


@pytest.fixture
def today(tmp_path):
    (tmp_path / "config.yaml").write_text(SET_UP)
    return config_module.today_for(config_module.load_config(tmp_path / "config.yaml"))


@pytest.fixture
def ready(tmp_path, today):
    return page_for(tmp_path / "ready", {"generated_for_date": today.isoformat(),
                                         "headline": "Hi", "note": "There", "events": []})


@pytest.fixture
def waiting(tmp_path):
    return page_for(tmp_path / "waiting")


def script_of(page):
    return page.split("<script>", 1)[1].split("</script>", 1)[0]


class TestOneReloadNotTwo:
    def test_the_meta_refresh_survives_only_as_the_no_script_fallback(self, ready):
        """Two timers would race: the tag's reload would land the error page
        the script exists to avoid. So the tag lives inside <noscript>, where
        a browser running the script never sees it."""
        tags = [m.start() for m in re.finditer(r'http-equiv="refresh"', ready)]
        assert tags, "a browser with scripting off still needs the reload"
        for at in tags:
            before = ready[:at]
            assert before.count("<noscript>") == before.count("</noscript>") + 1, \
                "a meta refresh outside <noscript> races the script"

    def test_the_body_carries_the_reload_interval(self, ready, waiting):
        assert 'data-reload="300"' in ready
        assert 'data-reload="60"' in waiting

    def test_the_script_fetches_its_own_url_and_nothing_else(self, ready):
        """`location.href`, so the same script serves `/` on a Pi and
        `/s/<token>` on a wall, and the token is never written into the page a
        second time. No host is named: the dashboard makes no third-party
        request, and a screen token in a Referer would be one."""
        script = script_of(ready)
        assert "fetch(location.href" in script
        for external in ("http://", "https://"):
            assert external not in script


class TestWhatTheBadgeCanSay:
    def test_it_is_in_every_page_and_hidden_until_needed(self, ready, waiting):
        for page in (ready, waiting):
            assert '<div class="offline" role="status" hidden></div>' in page

    def test_a_dated_dashboard_says_which_day_it_is_for(self, ready, today):
        """Once that day is over, the badge escalates from "Last updated 08:20"
        to "Showing Thursday's dashboard" — the date in the corner and the
        turns beside it are then yesterday's, and the page has to say so.
        The zone is the family's, because the device's clock may not be."""
        assert f'data-today="{today.isoformat()}"' in ready
        assert 'data-timezone="Europe/Berlin"' in ready

    def test_a_waiting_screen_is_for_no_day_and_says_so(self, waiting):
        assert "data-today=" not in waiting
        assert 'data-timezone="Europe/Berlin"' in waiting

    def test_the_badge_offers_no_way_out(self, ready):
        """It sits on a wall, in a page that deliberately has no link out
        (`tests/test_settings.py` asserts the same of the whole page)."""
        assert "/settings" not in ready
        assert "<a " not in ready


class TestADeployReachesTheWall:
    """A swap keeps the <head> — the CSS, the fonts, this script — so without
    this a panel loaded in March would run March's page for ever, and could
    draw a new body with old styles. The body carries the page's own version;
    a copy whose version differs is a deploy and gets a real reload, at the one
    moment a reload is safe: a copy has just arrived."""

    def test_the_body_carries_the_page_version(self, ready, waiting):
        from web import assets

        page_version = re.search(r'data-version="([0-9a-f]{12})"', ready)
        assert page_version, "no version on the body"
        assert page_version.group(1) in waiting
        with create_app(FileStore()).app_context():
            assert page_version.group(1) == assets.board_version()

    def test_the_version_follows_the_files_it_names(self, tmp_path):
        """Content, not commit: a Pi has no GIT_SHA, and a deploy that changes
        none of these files should not reload a wall."""
        from web import assets

        one = tmp_path / "board.html"
        one.write_text("<body>v1</body>")
        before = assets._version_at(str(one))
        one.write_text("<body>v2 with more</body>")
        assert assets._version_at(str(one)) != before
        assert assets._version_at(str(tmp_path / "missing.html")) is None

    def test_every_dashboard_file_the_version_names_exists(self):
        """A name that drifts — a font renamed, a template moved — would
        silently hash to nothing, and every deploy would then look like no
        deploy."""
        from web import assets

        app = create_app(FileStore())
        with app.app_context():
            for name in assets.BOARD_TEMPLATES:
                assert (Path(app.root_path) / app.template_folder / name).is_file(), name
            for name in assets.BOARD_STATIC:
                assert assets.version_of(name), name


class TestTheServerSideOfTheContract:
    def test_build_view_carries_the_day_and_the_zone(self):
        from datetime import date

        from dinkydash.board import build_view

        config = {"family_name": "The Wilsons", "timezone": "Europe/Berlin",
                  "people": [{"name": "Mia", "date_of_birth": "2017-03-15"}]}
        view = build_view(config, {"generated_for_date": "2026-09-03", "events": []},
                          date(2026, 9, 3))
        assert view["today"] == "2026-09-03"
        assert view["timezone"] == "Europe/Berlin"

    def test_an_unset_zone_is_utc_which_is_what_the_engine_uses_too(self):
        from datetime import date

        from dinkydash.board import build_view

        view = build_view({"family_name": "x"}, None, date(2026, 9, 3))
        assert view["timezone"] == "UTC"
