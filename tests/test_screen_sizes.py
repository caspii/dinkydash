"""A hosted screen reports its size, and the operator's page shows it (DIN-149).

The dashboard fits itself to one window. Which windows the hosted dashboards
actually run in is recorded when a refresh sends `X-Viewport`, one row per
family and size, and removed with the family. Single mode has no table, so
these tests that need one skip without `DINKYDASH_TEST_DATABASE_URL`. The
header parser and the framed-page check do not need a database; the framed
page is asserted from the template in `tests/test_board_refresh.py`.
"""

import logging
from decimal import Decimal

import pytest
import yaml

from dinkydash import accounts, config as config_module, growth
from dinkydash.store import FileStore
from tests.conftest import client_for
from web import create_app
from web.routes.screen import parse_viewport

CONFIG = 'family_name: "The Wilsons"\ntimezone: "Europe/Berlin"\n'


def test_single_mode_ignores_the_header(tmp_path, monkeypatch):
    """The header is sent by the shared page. Single mode has nowhere to put it."""
    monkeypatch.delenv("DINKYDASH_MODE", raising=False)
    (tmp_path / "config.yaml").write_text(CONFIG)
    app = create_app(FileStore(tmp_path / "config.yaml"))
    page = client_for(app).get("/", headers={"X-Viewport": "1280x800@2"})
    assert page.status_code == 200


class TestTheHeaderIsParsed:
    @pytest.mark.parametrize("header,size", [
        ("1280x800@2", (1280, 800, Decimal("2"))),
        ("390x844@2.625", (390, 844, Decimal("2.625"))),
        ("800x480@1.5", (800, 480, Decimal("1.5"))),
        ("800x480@2.0", (800, 480, Decimal("2.0"))),
        ("800x480@2.000", (800, 480, Decimal("2.000"))),
        ("1x10000@0.25", (1, 10000, Decimal("0.25"))),
        ("10000x1@8", (10000, 1, Decimal("8"))),
        ("10000x1@8.000", (10000, 1, Decimal("8.000"))),
        ("  1280x800@2  ", (1280, 800, Decimal("2"))),
    ])
    def test_a_size_is_a_size(self, header, size):
        assert parse_viewport(header) == size

    @pytest.mark.parametrize("header", [
        None,
        "",
        "   ",
        "1280x800",
        "1280x800@",
        "@2",
        "1280*800@2",
        "1280X800@2",
        "1280 x 800 @ 2",
        "1280x800@2.6251",
        "1280x800@2.",
        "1280x800@.5",
        "0x800@1",
        "1280x0@1",
        "10001x800@1",
        "1280x10001@1",
        "100000x800@1",
        "1280x800@0",
        "1280x800@0.2",
        "1280x800@0.249",
        "1280x800@8.001",
        "1280x800@9",
        "1280x800@10",
        "01280x800@2",
        "1280x0800@2",
        "1280x800@02",
        "1280x800@02.0",
        "-1280x800@2",
        "1280x800@-2",
        "1280x800@2; extra",
        "١280x800@2",
        "1280x800@2\nSet-Cookie: a",
        "x" * 80,
    ])
    def test_anything_else_is_ignored(self, header):
        assert parse_viewport(header) is None

    def test_equivalent_ratios_are_one_number(self):
        assert parse_viewport("800x480@2")[2] == parse_viewport("800x480@2.000")[2]


# -- stored, in cloud mode --------------------------------------------------

def _rows(pool, family_id):
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT width, height, pixel_ratio, user_agent, first_seen_at, last_seen_at
               FROM screen_sizes WHERE family_id = %s
               ORDER BY width, height, pixel_ratio""",
            (family_id,),
        )
        return cur.fetchall()


def _shift_last_seen(pool, family_id, interval):
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """UPDATE screen_sizes
               SET last_seen_at = last_seen_at - %s::interval
               WHERE family_id = %s""",
            (interval, family_id),
        )


@pytest.fixture
def cloud(pg_pool, pg_family, monkeypatch):
    from dinkydash.pgstore import PostgresStore

    store = PostgresStore(pg_pool, pg_family)
    store.save_config(yaml.safe_load(CONFIG))
    config = store.load_config()
    today = config_module.today_for(config).isoformat()
    board = {"generated_for_date": today, "headline": "Hello", "note": "",
             "events": [], "generated_at": f"{today}T04:00:00+00:00",
             "calendars_fetched_at": f"{today}T04:00:00+00:00"}
    store.save_agenda(config, board)
    store.save_brief(config, board)
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
    monkeypatch.delenv("DINKYDASH_ADMIN_EMAILS", raising=False)
    app = create_app(pool=pg_pool)
    return app


@pytest.fixture
def anyone(cloud):
    return client_for(cloud)


@pytest.fixture
def path(pg_pool, pg_family):
    from tests.conftest import board_path
    return board_path(pg_pool, pg_family)


class TestARefreshIsRemembered:
    def test_the_first_load_stores_nothing(self, anyone, path, pg_pool, pg_family):
        assert anyone.get(path).status_code == 200
        assert _rows(pg_pool, pg_family) == []

    def test_a_size_is_stored_with_the_browser(self, anyone, path, pg_pool, pg_family):
        headers = {"X-Viewport": "1280x800@2", "User-Agent": "KitchenTablet/1"}
        assert anyone.get(path, headers=headers).status_code == 200
        width, height, ratio, agent, first, last = _rows(pg_pool, pg_family)[0]
        assert (width, height, ratio, agent) == (1280, 800, Decimal("2"), "KitchenTablet/1")
        assert first == last

    def test_junk_is_not_stored(self, anyone, path, pg_pool, pg_family):
        token = path.rsplit("/", 1)[-1]
        for junk in ("nope", token, f"1280x800@2 {token}", "0x1@1", "1280x800@99"):
            assert anyone.get(path, headers={"X-Viewport": junk}).status_code == 200
        assert _rows(pg_pool, pg_family) == []

    def test_the_manifest_does_not_record_one(self, anyone, path, pg_pool, pg_family):
        got = anyone.get(f"{path}/manifest.webmanifest",
                         headers={"X-Viewport": "640x480@1"})
        assert got.status_code == 200
        assert _rows(pg_pool, pg_family) == []

    def test_a_wrong_token_records_nothing(self, anyone, pg_pool, pg_family):
        assert anyone.get("/s/zzzzzzzzzzzz",
                          headers={"X-Viewport": "640x480@1"}).status_code == 404
        assert _rows(pg_pool, pg_family) == []

    def test_a_long_browser_string_is_clipped(self, anyone, path, pg_pool, pg_family):
        agent = "Kitchen " + ("x" * 400)
        anyone.get(path, headers={"X-Viewport": "800x480@1", "User-Agent": agent})
        stored = _rows(pg_pool, pg_family)[0][3]
        assert len(stored) == 300
        assert stored.startswith("Kitchen ")

    def test_a_browser_string_is_one_line(self, pg_pool, pg_family):
        from dinkydash.pgstore import PostgresStore

        PostgresStore(pg_pool, pg_family).record_viewport(
            800, 480, Decimal("1"), "Kitchen\nTablet\t/1\x00extra")
        stored = _rows(pg_pool, pg_family)[0][3]
        assert stored == "Kitchen Tablet /1 extra"

    def test_the_same_size_within_the_hour_does_not_write(
            self, pg_pool, pg_family):
        from dinkydash.pgstore import PostgresStore

        store = PostgresStore(pg_pool, pg_family)
        assert store.record_viewport(800, 480, Decimal("1"), "First browser") is True
        assert store.record_viewport(800, 480, Decimal("1"), "Second browser") is False
        _width, _height, _ratio, agent, first, last = _rows(pg_pool, pg_family)[0]
        assert agent == "First browser"
        assert first == last

        _shift_last_seen(pg_pool, pg_family, "1 minute")
        assert store.record_viewport(800, 480, Decimal("1"), "Second browser") is False
        assert _rows(pg_pool, pg_family)[0][3] == "First browser"

    def test_an_hour_later_the_same_size_is_updated(self, pg_pool, pg_family):
        from dinkydash.pgstore import PostgresStore

        store = PostgresStore(pg_pool, pg_family)
        store.record_viewport(800, 480, Decimal("1"), "First browser")
        first = _rows(pg_pool, pg_family)[0][4]
        _shift_last_seen(pg_pool, pg_family, "2 hours")
        aged = _rows(pg_pool, pg_family)[0][5]
        assert store.record_viewport(800, 480, Decimal("1.0"), "Second browser") is True
        _width, _height, ratio, agent, still_first, last = _rows(pg_pool, pg_family)[0]
        assert agent == "Second browser"
        assert ratio == Decimal("1")
        assert still_first == first
        assert last > aged

    def test_a_different_size_is_a_different_row(self, pg_pool, pg_family):
        from dinkydash.pgstore import PostgresStore

        store = PostgresStore(pg_pool, pg_family)
        store.record_viewport(800, 480, Decimal("1"), "One")
        assert store.record_viewport(1280, 800, Decimal("2"), "Two") is True
        assert store.record_viewport(800, 480, Decimal("2"), "Three") is True
        assert len(_rows(pg_pool, pg_family)) == 3

    def test_two_spellings_of_one_ratio_are_one_row(self, pg_pool, pg_family):
        from dinkydash.pgstore import PostgresStore

        store = PostgresStore(pg_pool, pg_family)
        store.record_viewport(800, 480, Decimal("2"), "One")
        assert store.record_viewport(800, 480, Decimal("2.000"), "Two") is False
        assert len(_rows(pg_pool, pg_family)) == 1
        assert _rows(pg_pool, pg_family)[0][3] == "One"

    def test_deleting_the_family_removes_its_screens_and_leaves_the_other(
            self, pg_pool, pg_family):
        from dinkydash.pgstore import PostgresStore

        PostgresStore(pg_pool, pg_family).record_viewport(
            1280, 800, Decimal("2"), "KitchenTablet/1")
        with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "INSERT INTO families (screen_token) VALUES (%s) RETURNING id",
                (config_module.new_screen_token(),),
            )
            other = cur.fetchone()[0]
        try:
            PostgresStore(pg_pool, other).record_viewport(
                1280, 800, Decimal("2"), "OtherTablet/1")
            assert accounts.delete_family(pg_pool, pg_family) is True
            assert _rows(pg_pool, pg_family) == []
            assert len(_rows(pg_pool, other)) == 1
        finally:
            accounts.delete_family(pg_pool, other)

    def test_no_token_appears_in_any_log_line(
            self, anyone, path, pg_pool, pg_family, monkeypatch, caplog):
        from dinkydash.pgstore import PostgresStore

        token = path.rsplit("/", 1)[-1]
        with caplog.at_level(logging.DEBUG):
            assert anyone.get(path, headers={
                "X-Viewport": "1280x800@2", "User-Agent": token,
            }).status_code == 200
        assert _rows(pg_pool, pg_family)[0][3] == token

        def boom(self, *args, **kwargs):
            raise RuntimeError(token)

        monkeypatch.setattr(PostgresStore, "record_viewport", boom)
        with caplog.at_level(logging.DEBUG):
            page = anyone.get(path, headers={
                "X-Viewport": "800x480@1", "User-Agent": token,
            })
        assert page.status_code == 200
        assert "Could not record a screen size" in caplog.text
        for record in caplog.records:
            assert token not in record.getMessage()
            assert token not in str(record.args or "")
        # The failed write did not replace the row, and did not add another.
        assert [row[0] for row in _rows(pg_pool, pg_family)] == [1280]


class TestTheOperatorPageShowsTheSizes:
    @pytest.fixture
    def admin_client(self, cloud, pg_pool, pg_family, monkeypatch):
        monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", "owner@example.com")
        with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (family_id, email) VALUES (%s, %s) RETURNING id",
                (pg_family, "owner@example.com"),
            )
            user_id = cur.fetchone()[0]
        client = client_for(cloud)
        with client.session_transaction() as stored:
            stored["user_id"] = user_id
            stored["family_id"] = str(pg_family)
        return client

    def test_the_table_and_the_roster_name_the_size(
            self, admin_client, anyone, path, pg_pool, pg_family):
        anyone.get(path, headers={
            "X-Viewport": "1280x800@2.625",
            "User-Agent": "DinkyDashTestBrowser/149",
        })
        anyone.get(path, headers={"X-Viewport": "800x480@1"})
        html = admin_client.get("/admin").get_data(as_text=True)
        assert "Screen sizes" in html
        assert "1280×800 @2.625" in html
        assert "800×480 @1" in html
        # The table and the roster each name them. The later report is first
        # on the roster, because that is the screen seen most recently.
        assert html.count("1280×800 @2.625") >= 2
        assert "800×480 @1, 1280×800 @2.625" in html
        assert "DinkyDashTestBrowser/149" not in html
        assert path.rsplit("/", 1)[-1] not in html
        assert str(pg_family) not in html

        counts = {(row.width, row.height): row.count
                  for row in growth.screen_sizes(pg_pool)}
        assert counts[(1280, 800)] == 1
        assert counts[(800, 480)] == 1

    def test_two_families_at_one_size_count_as_two(
            self, admin_client, pg_pool, pg_family):
        from dinkydash.pgstore import PostgresStore

        PostgresStore(pg_pool, pg_family).record_viewport(
            1920, 1080, Decimal("1"), "One")
        with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute(
                "INSERT INTO families (screen_token) VALUES (%s) RETURNING id",
                (config_module.new_screen_token(),),
            )
            other = cur.fetchone()[0]
        try:
            PostgresStore(pg_pool, other).record_viewport(
                1920, 1080, Decimal("1"), "Two")
            html = admin_client.get("/admin").get_data(as_text=True)
            assert "1920×1080 @1" in html
            row = next(row for row in growth.screen_sizes(pg_pool)
                       if (row.width, row.height) == (1920, 1080))
            assert row.count == 2
            # The other family has no address. Its size is still on the roster.
            assert html.count("1920×1080 @1") >= 2
        finally:
            accounts.delete_family(pg_pool, other)
