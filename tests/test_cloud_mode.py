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

    def test_cloud_mode_starts_with_one(self, monkeypatch, pg_pool):
        monkeypatch.setenv("DINKYDASH_MODE", "cloud")
        monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
        app = create_app(pool=pg_pool)
        assert app.secret_key == "a-real-one"
        assert app.config["POOL"] is pg_pool
        assert app.config["STORE"] is None

    def test_cloud_mode_rejects_a_store(self, monkeypatch, tmp_path):
        from dinkydash.store import FileStore

        monkeypatch.setenv("DINKYDASH_MODE", "cloud")
        monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
        with pytest.raises(ValueError, match="Cloud mode accepts a pool"):
            create_app(FileStore(tmp_path / "config.yaml"))

    def test_single_mode_rejects_a_pool(self, monkeypatch):
        monkeypatch.setenv("DINKYDASH_MODE", "single")
        with pytest.raises(ValueError, match="Single mode accepts a store"):
            create_app(pool=object())

    def test_unknown_mode_cannot_silently_disable_authentication(self, monkeypatch):
        monkeypatch.setenv("DINKYDASH_MODE", "cluod")
        with pytest.raises(ValueError, match="DINKYDASH_MODE"):
            create_app()

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


@pytest.fixture
def client(pg_pool, pg_family, monkeypatch):
    """A signed-in cloud app with one family's board already written.

    Module level rather than nested, because more than one class below needs
    the same thing: a real cloud app, over a real pool, with a session on it.
    """
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


class TestCloudModeWaitsForTheDatabase:
    """A wrong `DATABASE_URL` used to start cleanly and fail every request.

    The pool opens in the background and only warns, so the process came up,
    `/healthz` answered, the deploy was declared healthy, and every board then
    waited thirty seconds and 500'd. Now the process refuses to start, which
    is a deploy that never goes live while the previous one carries on.
    Nothing here needs a real database, except the last test, which needs a
    closed port.
    """

    @pytest.fixture(autouse=True)
    def cloud(self, monkeypatch):
        pytest.importorskip("psycopg_pool")
        monkeypatch.setenv("DINKYDASH_MODE", "cloud")
        monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
        monkeypatch.setenv("DATABASE_URL", "postgresql://nobody:hunter2@127.0.0.1:1/nowhere")

    def test_a_database_that_never_answers_is_a_refusal_to_start(self, monkeypatch):
        from psycopg_pool import PoolTimeout

        from dinkydash import db

        class NeverReady:
            def wait(self, timeout):
                raise PoolTimeout("pool initialization incomplete")

        monkeypatch.setattr(db, "pool", lambda *args, **kwargs: NeverReady())
        with pytest.raises(RuntimeError, match="DATABASE_URL") as refused:
            create_app()
        # The variable's name, never its value: a connection string is a password.
        assert "hunter2" not in str(refused.value)
        assert "nowhere" not in str(refused.value)

    def test_a_database_that_answers_lets_it_start(self, monkeypatch):
        from dinkydash import db

        class Ready:
            waited = None

            def wait(self, timeout):
                self.waited = timeout

        pool = Ready()
        monkeypatch.setattr(db, "pool", lambda *args, **kwargs: pool)
        app = create_app()
        assert app.config["POOL"] is pool
        assert pool.waited == db.STARTUP_TIMEOUT

    def test_the_wait_is_bounded_and_shorter_than_the_probes_patience(self):
        from dinkydash import db

        assert 0 < db.STARTUP_TIMEOUT <= 15

    def test_the_real_pool_really_does_refuse(self, monkeypatch):
        """End to end: a real pool against a closed port, with the wait cut short."""
        from dinkydash import db

        monkeypatch.setattr(db, "STARTUP_TIMEOUT", 0.5)
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            create_app()


class TestABoardOutOfPostgres:
    """DIN-31's "done when": a board renders in cloud mode, from rows."""

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


class TestWhichModelRunsIsNotAHostedSetting:
    """The model box is self-hosted only, and the route is what enforces it.

    Self-hosted, the API key is the family's own: the model is their choice and
    the price beside the field is theirs to read. Hosted, the key is ours, so a
    free text box naming a model is a way to move an account onto an expensive
    one at our expense — and `budget.py` counts *calls*, deliberately, so it
    would not see it. Hiding the input is the courtesy; ignoring the field is
    the control, which is why both are asserted here.
    """

    def test_the_field_is_not_offered(self, client):
        page = client.get("/settings/system").get_data(as_text=True)
        assert 'name="claude_model"' not in page
        assert "claude-sonnet-5" not in page

    def test_nor_is_a_key_a_hosted_family_does_not_have(self, client):
        page = client.get("/settings/system").get_data(as_text=True)
        assert "ANTHROPIC_API_KEY" not in page

    def test_and_a_posted_one_is_ignored(self, client, pg_pool, pg_family):
        client.post("/settings/system",
                    data={"family_name": "The Wilsons", "timezone": "Europe/Berlin",
                          "claude_model": "claude-opus-5"})
        with pg_pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT config ->> 'claude_model' FROM families WHERE id = %s",
                        (pg_family,))
            assert cur.fetchone()[0] == "claude-haiku-4-5"
        # The rest of the form still saved, so this is a dropped field rather
        # than a rejected request.
        assert "The Wilsons" in client.get("/settings/system").get_data(as_text=True)

    def test_but_a_self_hoster_still_chooses(self, tmp_path, monkeypatch):
        """The same page on a Pi keeps the field, the price and the key note."""
        import yaml

        from dinkydash.store import FileStore

        monkeypatch.delenv("DINKYDASH_MODE", raising=False)
        (tmp_path / "config.yaml").write_text(yaml.safe_dump(CONFIG, allow_unicode=True))
        app = create_app(FileStore(tmp_path / "config.yaml"))
        page = app.test_client().get("/settings/system").get_data(as_text=True)
        assert 'name="claude_model"' in page
        assert "ANTHROPIC_API_KEY" in page

        client_for(app).post("/settings/system",
                             data={"family_name": "The Wilsons",
                                   "timezone": "Europe/Berlin",
                                   "claude_model": "claude-sonnet-5"})
        saved = yaml.safe_load((tmp_path / "config.yaml").read_text())
        assert saved["claude_model"] == "claude-sonnet-5"


class TestSelfHostingInstructionsStayThere:
    """Copy that tells a self-hoster what to do is not shown to a hosted one.

    The crontab note on /settings/refresh is the case that matters: what drives
    the scheduler is one of the four things mode gates, so hosted there is no
    crontab — and the note does not say "ignore this", it says nothing on the
    page has any effect. Wrong, and alarming, to somebody paying for it.
    """

    def test_the_crontab_note_is_not_shown_to_a_hosted_family(self, client):
        page = client.get("/settings/refresh").get_data(as_text=True)
        assert "crontab" not in page
        # The settings themselves are still there — this is one note box, not
        # the page.
        assert 'name="brief_time"' in page

    def test_but_a_self_hoster_is_still_told(self, tmp_path, monkeypatch):
        import yaml

        from dinkydash.store import FileStore

        monkeypatch.delenv("DINKYDASH_MODE", raising=False)
        (tmp_path / "config.yaml").write_text(yaml.safe_dump(CONFIG, allow_unicode=True))
        app = create_app(FileStore(tmp_path / "config.yaml"))
        page = app.test_client().get("/settings/refresh").get_data(as_text=True)
        assert "crontab" in page
