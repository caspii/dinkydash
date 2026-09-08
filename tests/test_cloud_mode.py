"""What `DINKYDASH_MODE=cloud` changes, and what it must not.

Mode gates four things across the product — authentication, billing, where the
config is stored, and what drives the scheduler. Two of them are here: the
storage backend, and the refusal to start on a fallback session key. The third,
authentication, has its own file — `tests/test_auth.py`. Everything else is
asserted to be identical, because a mode check anywhere else would mean the
change went in the wrong layer.
"""

import pytest

from dinkydash import config as config_module
from tests.conftest import board_path, client_for
from web import create_app

CONFIG = {
    "family_name": "The Wilsons",
    "timezone": "Europe/Berlin",
    "theme": "light",
    "people": [{"id": "mia12345", "name": "Mia", "date_of_birth": "2017-03-15"}],
    "recurring": [{"id": "job12345", "title": "Set the table",
                   "choices": ["Mia"], "emoji": "🍽"}],
}

def payload_for_today():
    """A board written this morning, on the family's clock.

    Dated from the real clock rather than pinned, because a payload from a fixed
    date would be *stale* by the time anybody ran this — and a stale board
    replaces the model's headline with a computed one, which is correct
    behaviour and would make this test look broken for the wrong reason.
    """
    today = config_module.today_for(config_module.with_defaults(dict(CONFIG)))
    return {
        "generated_for_date": today.isoformat(),
        "generated_at": f"{today.isoformat()}T04:00:00+00:00",
        "headline": "Swimming, then football",
        "note": "An octopus fact.",
        "note_kind": "fact",
        "model": "claude-haiku-4-5",
        "input_tokens": 100,
        "output_tokens": 40,
        "events": [{"title": "Swimming", "date": today.isoformat(), "time": "15:45",
                    "all_day": False, "start": f"{today.isoformat()}T15:45:00+02:00",
                    "location": None, "calendar": "Family"}],
        "calendar_statuses": [{"label": "Family", "ok": True, "detail": "", "count": 1}],
        "calendars_fetched_at": f"{today.isoformat()}T03:50:00+00:00",
    }


class TestTheSessionKey:
    """In cloud mode the session *is* the authentication (CLAUDE.md)."""

    def test_cloud_mode_refuses_to_start_without_a_real_key(self, monkeypatch):
        monkeypatch.setenv("DINKYDASH_MODE", "cloud")
        monkeypatch.delenv("DINKYDASH_SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError, match="DINKYDASH_SECRET_KEY"):
            create_app()

    def test_it_refuses_before_it_tries_to_reach_a_database(self, monkeypatch):
        # The order matters: a missing key must be the error a deploy sees,
        # not a connection timeout that hides it.
        monkeypatch.setenv("DINKYDASH_MODE", "cloud")
        monkeypatch.delenv("DINKYDASH_SECRET_KEY", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="DINKYDASH_SECRET_KEY"):
            create_app()

    def test_cloud_mode_starts_with_one(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DINKYDASH_MODE", "cloud")
        monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
        # A store is supplied, so nothing tries to connect.
        from dinkydash.store import FileStore
        (tmp_path / "config.yaml").write_text('family_name: "The Wilsons"\n')
        app = create_app(FileStore(tmp_path / "config.yaml"))
        assert app.secret_key == "a-real-one"

    def test_single_mode_still_has_its_fallback(self, monkeypatch, tmp_path):
        # A self-hoster is not made to invent a secret for a LAN-local app that
        # only signs flash messages.
        monkeypatch.delenv("DINKYDASH_MODE", raising=False)
        monkeypatch.delenv("DINKYDASH_SECRET_KEY", raising=False)
        from dinkydash.store import FileStore
        (tmp_path / "config.yaml").write_text('family_name: "The Wilsons"\n')
        app = create_app(FileStore(tmp_path / "config.yaml"))
        assert app.secret_key == "dinkydash-self-hosted"

    def test_an_explicit_key_wins_in_single_mode_too(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DINKYDASH_SECRET_KEY", "mine")
        from dinkydash.store import FileStore
        (tmp_path / "config.yaml").write_text('family_name: "The Wilsons"\n')
        assert create_app(FileStore(tmp_path / "config.yaml")).secret_key == "mine"


class TestABoardOutOfPostgres:
    """DIN-31's "done when": a board renders in cloud mode, from rows."""

    @pytest.fixture
    def client(self, pg_pool, pg_family, monkeypatch):
        from dinkydash.pgstore import PostgresStore

        store = PostgresStore(pg_pool, pg_family)
        store.save_config(dict(CONFIG))
        today = payload_for_today()
        store.save_agenda(store.load_config(), today)
        store.save_brief(store.load_config(), today)

        monkeypatch.setenv("DINKYDASH_MODE", "cloud")
        monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
        # The pool, not the store. Cloud mode builds a `PostgresStore` per
        # request from the family on the session, so handing one in would
        # test a path production does not have.
        client = client_for(create_app(pool=pg_pool))
        # These tests are about the rows, not the login. Signing in by hand is
        # what keeps them that way; `tests/test_auth.py` is where the gate
        # itself is tested, and `tests/test_tenancy.py` the scoping.
        with client.session_transaction() as stored:
            stored["user_id"] = 1
            stored["family_id"] = str(pg_family)
        return client

    def test_the_board_renders_the_stored_brief(self, client, pg_pool, pg_family):
        page = client.get(board_path(pg_pool, pg_family)).get_data(as_text=True)
        assert "Swimming, then football" in page
        assert "An octopus fact." in page

    def test_it_recomputes_the_chore_rather_than_reading_it(
            self, client, pg_pool, pg_family):
        # Chores are a pure function of config + date and are not in the
        # payload, so seeing one proves build_view ran over the database config.
        page = client.get(board_path(pg_pool, pg_family)).get_data(as_text=True)
        assert "Set the table" in page
        assert "Mia" in page

    def test_and_the_root_is_the_way_in_to_the_settings(self, client):
        """In cloud mode `/` is not the board — a wall panel cannot sign in, so
        the board is at the screen URL and `/` belongs to the signed-in area."""
        landed = client.get("/")
        assert landed.status_code == 302
        assert landed.headers["Location"].endswith("/settings/")

    def test_the_settings_home_reads_the_same_rows(self, client):
        page = client.get("/settings/").get_data(as_text=True)
        assert "The Wilsons" in page
        assert "Calendars refreshed" in page

    def test_a_settings_save_lands_in_the_database(self, client, pg_pool, pg_family):
        client.post("/settings/system",
                    data={"family_name": "The Bakers", "timezone": "Europe/Berlin"})
        with pg_pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT config ->> 'family_name' FROM families WHERE id = %s",
                        (pg_family,))
            assert cur.fetchone()[0] == "The Bakers"

    def test_the_board_is_identical_to_the_one_a_file_would_render(
            self, client, pg_pool, pg_family, tmp_path, monkeypatch):
        """The template, the CSS and build_view are shared verbatim.

        If cloud mode ever rendered a different board, the mode check would have
        leaked below the storage layer — which is the thing CLAUDE.md's "every
        change must work in both" exists to prevent.

        **One line is allowed to differ, and exactly one**: the `<link
        rel=manifest>`. A wall panel reaches its manifest at
        `/s/<token>/manifest.webmanifest`, because the signed-in one is behind
        the session and would hand a tablet a redirect to `/login` instead of a
        name and an icon (DIN-42). Normalising that href rather than dropping
        the assertion is the point — every other byte still has to match, so a
        second divergence fails here rather than being absorbed.
        """
        import re

        import yaml

        from dinkydash.store import FileStore
        # A genuinely self-hosted app for the other side of the comparison. The
        # fixture above set cloud mode for the whole test, and a cloud app with
        # no session redirects to `/login` rather than rendering anything.
        monkeypatch.delenv("DINKYDASH_MODE", raising=False)
        (tmp_path / "config.yaml").write_text(yaml.safe_dump(CONFIG, allow_unicode=True))
        file_store = FileStore(tmp_path / "config.yaml")
        today = payload_for_today()
        file_store.save_agenda(file_store.load_config(), today)
        file_store.save_brief(file_store.load_config(), today)
        from_file = create_app(file_store).test_client().get("/").get_data(as_text=True)
        from_rows = client.get(board_path(pg_pool, pg_family)).get_data(as_text=True)

        manifest = re.compile(r'<link rel="manifest" href="[^"]+">')
        assert manifest.search(from_file) and manifest.search(from_rows)
        assert manifest.sub("[manifest]", from_rows) == manifest.sub("[manifest]", from_file)
