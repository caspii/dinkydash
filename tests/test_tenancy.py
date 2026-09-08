"""Two families, one process, and no way from one to the other.

PLAN.md's "done when" for phase 1:

> two different families can be configured independently through the UI, and a
> request carrying the wrong family's id in a URL gets a 404, never a row.

The claim being tested is stronger than "ids are checked". **Cloud mode reads
the family from the session and from nowhere else** — no path segment, no query
parameter, no form field and no header names one — so there is no id for a
caller to get wrong. What ids there *are* in URLs are item ids inside one
family's config document, and another family's is simply not in the list.

Skips without `DINKYDASH_TEST_DATABASE_URL`, like the rest of the Postgres
half. Single mode is asserted unchanged here too: a self-hoster has one family,
one file and no session, and none of this may reach them.
"""

import json
import pathlib
import subprocess

import pytest
import yaml

from dinkydash.store import FileStore
from tests.conftest import client_for
from web import create_app

REPO = pathlib.Path(__file__).resolve().parent.parent

# Two families with nothing in common, so anything leaking is obvious.
WILSONS = {
    "family_name": "The Wilsons",
    "timezone": "Europe/Berlin",
    "theme": "light",
    "people": [{"id": "mia11111", "name": "Mia", "date_of_birth": "2017-03-15"}],
    "pets": [{"id": "dog11111", "name": "Rolo", "type": "dog"}],
    "recurring": [{"id": "job11111", "title": "Set the table", "choices": ["Mia"]}],
    "special_dates": [{"id": "day11111", "title": "Camping", "date": "07/14"}],
    "calendars": [{"id": "cal11111", "label": "Wilson school",
                   "url": "https://example.com/private-wwww/basic.ics", "enabled": True}],
}

BAKERS = {
    "family_name": "The Bakers",
    "timezone": "Europe/London",
    "theme": "dark",
    "people": [{"id": "otto2222", "name": "Otto", "date_of_birth": "2015-08-02"}],
    "pets": [{"id": "cat22222", "name": "Smudge", "type": "cat"}],
    "recurring": [{"id": "job22222", "title": "Feed the cat", "choices": ["Otto"]}],
    "special_dates": [{"id": "day22222", "title": "Sailing", "date": "05/02"}],
    "calendars": [{"id": "cal22222", "label": "Baker swimming",
                   "url": "https://example.com/private-bbbb/basic.ics", "enabled": True}],
}

# Every section, and the item in each that belongs to the *other* family.
SECTIONS = ["people", "pets", "recurring", "special_dates", "calendars"]
BAKER_ITEMS = {
    "people": "otto2222",
    "pets": "cat22222",
    "recurring": "job22222",
    "special_dates": "day22222",
    "calendars": "cal22222",
}


# A board each, so the `generations` and `agendas` rows are scoped too and not
# only `families.config`.
BOARDS = {
    "wilsons": {"headline": "Swimming, then football", "note": "An octopus fact."},
    "bakers": {"headline": "Sailing at low tide", "note": "A puffin fact."},
}


@pytest.fixture
def families(pg_pool):
    """Two families, each with a parent and a written board, cleaned up afterwards.

    Returns `{"wilsons": (family_id, user_id), "bakers": (...)}`.
    """
    from dinkydash import config as config_module
    from dinkydash.pgstore import PostgresStore

    made = {}
    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            for name, config in (("wilsons", WILSONS), ("bakers", BAKERS)):
                cur.execute(
                    """INSERT INTO families (screen_token, config)
                       VALUES (%s, %s::jsonb) RETURNING id""",
                    # A real token, from `config.ID_ALPHABET`. `tok-wilsons`
                    # was unique and readable and is **not a shape this app
                    # issues** — no hyphen in the alphabet, and no `o` — so
                    # once `/s/<token>` started refusing malformed tokens
                    # before querying (DIN-42) it named nobody.
                    (config_module.new_screen_token(), json.dumps(config)),
                )
                family_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO users (family_id, email) VALUES (%s, %s) RETURNING id",
                    (family_id, f"{name}@example.com"),
                )
                made[name] = (family_id, cur.fetchone()[0])

    for name, config in (("wilsons", WILSONS), ("bakers", BAKERS)):
        # Dated from the real clock: a payload from a fixed date would be stale
        # by the time anybody ran this, and a stale board replaces the model's
        # headline with a computed one.
        today = config_module.today_for(config_module.with_defaults(dict(config)))
        store = PostgresStore(pg_pool, made[name][0])
        store.save_brief(config, {
            "generated_for_date": today.isoformat(),
            "generated_at": f"{today.isoformat()}T04:00:00+00:00",
            **BOARDS[name],
        })
    yield made
    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            for family_id, _ in made.values():
                cur.execute("DELETE FROM families WHERE id = %s", (family_id,))


@pytest.fixture
def app(pg_pool, monkeypatch):
    """One cloud app, the way production builds it: a pool and no store."""
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
    return create_app(pool=pg_pool)


def signed_in_as(app, family):
    """A client carrying a session for that family. The login itself is test_auth's."""
    family_id, user_id = family
    client = client_for(app)
    with client.session_transaction() as stored:
        stored["user_id"] = user_id
        stored["family_id"] = str(family_id)
    return client


@pytest.fixture
def boards(pg_pool, families):
    """Each family's screen URL — where the board lives in cloud mode."""
    from tests.conftest import board_path

    return {name: board_path(pg_pool, family[0])
            for name, family in families.items()}


@pytest.fixture
def wilson(app, families):
    return signed_in_as(app, families["wilsons"])


@pytest.fixture
def baker(app, families):
    return signed_in_as(app, families["bakers"])


def config_of(pg_pool, family_id):
    with pg_pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT config FROM families WHERE id = %s", (family_id,))
        return cur.fetchone()[0]


# -- each family sees their own -------------------------------------------

class TestTwoFamiliesSideBySide:
    """One app, one process, two sessions. The oldest multi-tenancy bug is a
    module-level cache of "the" config, so both clients are used in one test."""

    def test_the_settings_home_shows_each_their_own_name(self, wilson, baker):
        assert "The Wilsons" in wilson.get("/settings/").get_data(as_text=True)
        assert "The Bakers" in baker.get("/settings/").get_data(as_text=True)

    def test_and_never_the_other_one(self, wilson, baker):
        assert "The Bakers" not in wilson.get("/settings/").get_data(as_text=True)
        assert "The Wilsons" not in baker.get("/settings/").get_data(as_text=True)

    @pytest.mark.parametrize("section,mine,theirs", [
        ("people", "Mia", "Otto"),
        ("pets", "Rolo", "Smudge"),
        ("recurring", "Set the table", "Feed the cat"),
        ("special_dates", "Camping", "Sailing"),
        ("calendars", "Wilson school", "Baker swimming"),
    ])
    def test_every_list_holds_only_one_familys_items(self, wilson, section, mine, theirs):
        page = wilson.get(f"/settings/{section}").get_data(as_text=True)
        assert mine in page
        assert theirs not in page

    def test_the_board_is_each_familys_own(self, wilson, baker, boards):
        """The headline comes out of `generations`, and the chore is recomputed
        from `families.config` — so this covers both tables at once.

        Read at each family's screen URL rather than at `/`, because that is
        where a board lives in cloud mode now (DIN-42). **The clients are still
        the signed-in ones** — a screen URL needs no session, and using them
        here checks the stronger thing: holding one family's cookie does not
        change what the other family's token shows.
        """
        ours = wilson.get(boards["wilsons"]).get_data(as_text=True)
        theirs = baker.get(boards["bakers"]).get_data(as_text=True)
        assert "Swimming, then football" in ours and "Set the table" in ours
        assert "Sailing at low tide" in theirs and "Feed the cat" in theirs

    def test_and_neither_board_carries_the_others_words(self, wilson, baker, boards):
        assert "Sailing at low tide" not in wilson.get(boards["wilsons"]).get_data(as_text=True)
        assert "Swimming, then football" not in baker.get(boards["bakers"]).get_data(as_text=True)

    def test_a_screen_token_shows_its_own_family_and_no_session_changes_that(
            self, wilson, boards):
        """The token decides which board, not the cookie that happens to be on
        the request. A screen has no session at all, so if a signed-in one could
        steer this the anonymous case would be the odd one out."""
        theirs = wilson.get(boards["bakers"]).get_data(as_text=True)
        assert "Sailing at low tide" in theirs
        assert "Swimming, then football" not in theirs

    def test_even_the_theme_follows_the_board(self, wilson, baker, boards):
        # The Bakers are on dark and the Wilsons on light. A shared store would
        # give both the same one.
        assert 'data-theme="light"' in wilson.get(boards["wilsons"]).get_data(as_text=True)
        assert 'data-theme="dark"' in baker.get(boards["bakers"]).get_data(as_text=True)

    def test_a_calendar_url_never_crosses(self, wilson, boards):
        """The one value in a config that is a password."""
        for path in ("/settings/", "/settings/calendars", boards["wilsons"]):
            assert "private-bbbb" not in wilson.get(path).get_data(as_text=True)


# -- another family's id in a URL -----------------------------------------

class TestTheOtherFamilysIds:
    """404, never a row — and never a 403 either, which would confirm it exists."""

    @pytest.mark.parametrize("section", SECTIONS)
    def test_opening_their_item_is_a_404(self, wilson, section):
        response = wilson.get(f"/settings/{section}/{BAKER_ITEMS[section]}")
        assert response.status_code == 404

    @pytest.mark.parametrize("section", SECTIONS)
    def test_saving_over_their_item_is_a_404(self, wilson, section):
        response = wilson.post(f"/settings/{section}/{BAKER_ITEMS[section]}",
                               data={"name": "Taken", "title": "Taken", "label": "Taken"})
        assert response.status_code == 404

    @pytest.mark.parametrize("section", SECTIONS)
    def test_deleting_their_item_is_a_404(self, wilson, section):
        response = wilson.post(f"/settings/{section}/{BAKER_ITEMS[section]}/delete")
        assert response.status_code == 404

    @pytest.mark.parametrize("section", SECTIONS)
    def test_reordering_their_item_is_a_404(self, wilson, section):
        response = wilson.post(f"/settings/{section}/{BAKER_ITEMS[section]}/move",
                               data={"direction": "up"})
        assert response.status_code == 404

    def test_none_of_it_changed_a_thing(self, wilson, families, pg_pool):
        """The 404s above must be refusals, not writes that happened to 404."""
        before = config_of(pg_pool, families["bakers"][0])
        for section in SECTIONS:
            item = BAKER_ITEMS[section]
            wilson.get(f"/settings/{section}/{item}")
            wilson.post(f"/settings/{section}/{item}", data={"name": "Taken"})
            wilson.post(f"/settings/{section}/{item}/delete")
            wilson.post(f"/settings/{section}/{item}/move", data={"direction": "up"})
        assert config_of(pg_pool, families["bakers"][0]) == before

    def test_it_is_a_404_and_not_a_403(self, wilson):
        """"Forbidden" would tell one family that another family's row exists."""
        assert wilson.get("/settings/people/otto2222").status_code == 404


# -- writes land on one family only ---------------------------------------

class TestWritesStayHome:
    def test_renaming_one_family_leaves_the_other(self, wilson, families, pg_pool):
        before = config_of(pg_pool, families["bakers"][0])
        wilson.post("/settings/system",
                    data={"family_name": "The Wilsons of Ealing", "timezone": "Europe/Berlin"})
        assert config_of(pg_pool, families["wilsons"][0])["family_name"] \
            == "The Wilsons of Ealing"
        assert config_of(pg_pool, families["bakers"][0]) == before

    def test_adding_a_person_adds_them_to_one_family(self, wilson, families, pg_pool):
        wilson.post("/settings/people/new",
                    data={"name": "Bo", "date_of_birth": "2020-04-01"})
        assert len(config_of(pg_pool, families["wilsons"][0])["people"]) == 2
        assert len(config_of(pg_pool, families["bakers"][0])["people"]) == 1

    def test_deleting_your_own_still_works(self, wilson, families, pg_pool):
        assert wilson.post("/settings/people/mia11111/delete").status_code == 302
        assert config_of(pg_pool, families["wilsons"][0])["people"] == []
        assert len(config_of(pg_pool, families["bakers"][0])["people"]) == 1


# -- what the session may say ---------------------------------------------

class TestWhatTheSessionMaySay:
    def test_no_session_means_no_board(self, app):
        response = client_for(app).get("/")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_no_session_means_no_settings(self, app):
        assert client_for(app).get("/settings/").status_code == 302

    def test_a_cookie_we_did_not_sign_is_not_a_session(self, app, families):
        """Flask signs the cookie; an invented one is discarded, not trusted."""
        client = client_for(app)
        client.set_cookie("session", "eyJmYW1pbHlfaWQiOiAiYW55dGhpbmcifQ.forged")
        assert client.get("/settings/").status_code == 302

    def test_a_family_id_that_is_not_a_uuid_never_reaches_a_query(self, app):
        client = client_for(app)
        with client.session_transaction() as stored:
            stored["user_id"] = 1
            stored["family_id"] = "'; DROP TABLE families; --"
        assert client.get("/settings/").status_code == 404

    def test_a_family_that_has_been_deleted_signs_you_out(self, app, pg_pool, families):
        """A session lasts thirty days and an account can be deleted inside one."""
        client = signed_in_as(app, families["wilsons"])
        with pg_pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DELETE FROM families WHERE id = %s", (families["wilsons"][0],))
        response = client.get("/settings/")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
        with client.session_transaction() as stored:
            assert "user_id" not in stored


# -- the shape of the thing ------------------------------------------------

class TestOneStorePerRequestAndOnePoolPerProcess:
    def test_cloud_mode_holds_no_store_of_its_own(self, app):
        """A store built at start-up could only be built from an environment
        variable, which is what this replaced."""
        assert app.config["STORE"] is None

    def test_it_holds_exactly_one_pool(self, app, pg_pool):
        assert app.config["POOL"] is pg_pool

    def test_two_requests_get_two_stores_over_that_one_pool(self, app, families):
        from web.family import current_store

        seen = []
        for family in (families["wilsons"], families["bakers"]):
            with app.test_request_context("/"):
                from flask import session as flask_session
                flask_session["family_id"] = str(family[0])
                store = current_store()
                seen.append((store.family_id, store.pool))
        assert seen[0][0] != seen[1][0]
        assert seen[0][1] is seen[1][1]

    def test_one_request_gets_one_store(self, app, families):
        from web.family import current_store

        with app.test_request_context("/"):
            from flask import session as flask_session
            flask_session["family_id"] = str(families["wilsons"][0])
            assert current_store() is current_store()


class TestSingleModeIsUntouched:
    """A self-hoster has one family, one file and no session."""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DINKYDASH_MODE", raising=False)
        (tmp_path / "config.yaml").write_text(yaml.safe_dump(WILSONS, allow_unicode=True))
        return client_for(create_app(FileStore(tmp_path / "config.yaml")))

    def test_the_board_needs_no_session(self, client):
        assert client.get("/").status_code == 200

    def test_the_settings_need_no_session(self, client):
        assert "The Wilsons" in client.get("/settings/").get_data(as_text=True)

    def test_it_still_uses_the_one_store_it_was_given(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DINKYDASH_MODE", raising=False)
        (tmp_path / "config.yaml").write_text("family_name: The Wilsons\n")
        store = FileStore(tmp_path / "config.yaml")
        app = create_app(store)
        assert app.config["STORE"] is store
        assert app.config["POOL"] is None

    def test_and_writes_still_land(self, client, tmp_path):
        client.post("/settings/system",
                    data={"family_name": "The Wilsons of Ealing", "timezone": "UTC"})
        assert "The Wilsons of Ealing" in (tmp_path / "config.yaml").read_text()


class TestTheHardcodedFamilyIsGone:
    """`grep -rn DINKYDASH_FAMILY_ID` returning nothing is the acceptance test.

    A single surviving reference is a route that serves whoever the environment
    says, to whoever asked.
    """

    def test_nothing_mentions_it_anywhere(self):
        """Prose included, deliberately.

        The dated notes in PLAN.md and doc/operations.md were rewritten rather
        than left, because "cloud mode serves one family from an environment
        variable" stopped being true — a log that records a fact is worth
        keeping, and one that records a stale fact is worth correcting. This
        file is excluded because a test asserting a name is gone has to say it.
        """
        found = subprocess.run(
            ["git", "grep", "-l", "DINKYDASH_FAMILY_ID",
             "--", ".", ":!tests/test_tenancy.py"],
            cwd=REPO, capture_output=True, text=True,
        )
        # `git grep` exits 1 with no matches, which is the passing case.
        assert found.stdout.strip() == "", found.stdout

    def test_the_app_spec_does_not_set_it(self):
        spec = yaml.safe_load((REPO / ".do" / "app.yaml").read_text())
        assert "DINKYDASH_FAMILY_ID" not in {e["key"] for e in spec["envs"]}


class TestHealthzStaysOpen:
    """**Not a detail.** The health check arrives with no cookie, on a hostname
    nobody signed in on. A 302 there fails it three times and App Platform
    rolls the release back."""

    def test_it_answers_with_no_session_in_cloud_mode(self, app):
        response = client_for(app).get("/healthz")
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"

    def test_it_still_touches_nothing(self, app, pg_pool):
        # No store, no family, no query — so it cannot be made to fail by
        # anything that is slow or broken behind it.
        assert client_for(app).get("/healthz").status_code == 200
