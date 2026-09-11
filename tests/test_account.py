"""Export and hard delete: the two rights the privacy policy promises (DIN-44).

A policy is a claim about what the code does, so these are the assertions that
keep the two in step:

* **delete means gone**, out of every table, including the one row no cascade
  reaches — a sign-up token has no user to hang off;
* **delete is hard to do by accident** and impossible to do to somebody else;
* **export is everything.** The family's own data comes from the store, which is
  the only thing that knows what it is; the two things the store deliberately
  cannot answer — the platform's bookkeeping, and the *full* written history
  rather than the note text the prompt needs — are read directly and named;
* **export carries no live credential.** It is a file that gets emailed to
  somebody and forgotten;
* **a self-hoster sees none of it.** There is no account to delete and their
  data is three files they already have.

Skips without `DINKYDASH_TEST_DATABASE_URL`.
"""

import json
from datetime import date, timedelta

import pytest
import yaml

from dinkydash import accounts, screens
from dinkydash.store import FileStore
from tests.conftest import client_for
from web import create_app

CONFIG = '''\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
people:
  - id: mia12345
    name: "Mia"
    date_of_birth: "2017-03-15"
calendars:
  - id: cal12345
    label: "School"
    url: "https://example.com/private-xxxx/basic.ics"
    enabled: true
'''

ADDRESS = "parent@example.com"


@pytest.fixture
def family(pg_pool, pg_family):
    """One family with a parent, a dashboard and a written line behind it."""
    from dinkydash.pgstore import PostgresStore

    store = PostgresStore(pg_pool, pg_family)
    store.save_config(yaml.safe_load(CONFIG))
    config = store.load_config()
    store.save_brief(config, {"generated_for_date": "2026-09-08",
                              "generated_at": "2026-09-08T04:00:00+00:00",
                              "headline": "Swimming, then football",
                              "note": "An octopus fact."})
    store.save_agenda(config, {"events": [],
                               "calendars_fetched_at": "2026-09-08T04:00:00+00:00"})
    store.record_note(config, {"date": "2026-09-08",
                               "headline": "Swimming, then football",
                               "note": "An octopus fact.", "note_kind": "fact"})
    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (family_id, email) VALUES (%s, %s) RETURNING id",
                (pg_family, ADDRESS),
            )
            user_id = cur.fetchone()[0]
    return pg_family, user_id


@pytest.fixture
def cloud(pg_pool, monkeypatch):
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
    return create_app(pool=pg_pool)


@pytest.fixture
def parent(cloud, family):
    family_id, user_id = family
    client = client_for(cloud)
    with client.session_transaction() as stored:
        stored["user_id"] = user_id
        stored["family_id"] = str(family_id)
    return client


def rows(pg_pool, sql, args=()):
    with pg_pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


# -- export -----------------------------------------------------------------

class TestExport:
    def test_older_daily_briefs_and_recent_rewrites_are_exported_only_for_this_family(
            self, parent, pg_pool, family):
        from dinkydash import config as config_module
        from dinkydash.pgstore import PostgresStore

        store = PostgresStore(pg_pool, family[0])
        config = store.load_config()
        for offset in range(31):
            day = (date(2026, 9, 8) + timedelta(days=offset)).isoformat()
            brief = {"generated_for_date": day, "generated_at": f"{day}T04:00:00+00:00",
                     "headline": f"Retained day {offset}", "note": f"Fact {offset}",
                     "note_kind": "fact", "model": "test-model",
                     "input_tokens": 1200, "output_tokens": 90}
            store.save_brief(config, brief)
            store.record_note(config, dict(brief, date=day))
        store.record_note(config, {"date": day, "headline": "An additional rewrite",
                                  "note": "A retained alternative.", "note_kind": "fact"})

        with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("INSERT INTO families (screen_token) VALUES (%s) RETURNING id",
                        (config_module.new_screen_token(),))
            other = cur.fetchone()[0]
        try:
            neighbour = PostgresStore(pg_pool, other)
            neighbour.save_brief({}, dict(brief, headline="Other family's private headline"))
            neighbour.record_note({}, {"date": day, "note": "Other family's private note"})
            # A requested family id cannot override the authenticated session.
            response = parent.get(f"/settings/account/export?family_id={other}")
            exported = json.loads(response.get_data())
            generations = exported["generations"]
            assert len(generations) == 31
            assert generations[0]["generated_for_date"] == "2026-09-08"
            assert generations[0]["brief"]["headline"] == "Retained day 0"
            assert generations[0]["model"] == "test-model"
            assert generations[0]["input_tokens"] == 1200
            assert len(exported["written_lines"]) == 30
            assert exported["written_lines"][-1]["headline"] == "An additional rewrite"
            assert "Retained day 0" not in json.dumps(exported["written_lines"])
            assert "Other family's private" not in response.get_data(as_text=True)
            assert response.headers["Cache-Control"] == "no-store"
        finally:
            accounts.delete_family(pg_pool, other)

    def test_it_comes_back_as_a_file(self, parent):
        got = parent.get("/settings/account/export")
        assert got.status_code == 200
        assert "attachment" in got.headers["Content-Disposition"]
        assert "dinkydash-export.json" in got.headers["Content-Disposition"]

    def test_and_is_not_cached_anywhere(self, parent):
        """The most concentrated copy of a family's data the app ever makes."""
        got = parent.get("/settings/account/export")
        assert got.headers["Cache-Control"] == "no-store"
        assert got.headers["X-Robots-Tag"] == "noindex"

    def test_it_holds_the_settings_the_board_and_the_written_lines(self, parent):
        export = json.loads(parent.get("/settings/account/export").get_data())
        assert export["settings"]["family_name"] == "The Wilsons"
        assert export["settings"]["people"][0]["name"] == "Mia"
        assert export["board"]["headline"] == "Swimming, then football"
        assert export["written_lines"][0]["note"] == "An octopus fact."
        # The date and the headline with it. `recent_notes` returns note text
        # alone because that is all the prompt needs; an export that did the
        # same would hand somebody a list of sentences with no days on them.
        assert export["written_lines"][0]["date"] == "2026-09-08"
        assert export["written_lines"][0]["headline"] == "Swimming, then football"

    def test_including_the_calendar_links(self, parent):
        """Portability means the links too — they are the thing that would take
        longest to reassemble by hand."""
        export = json.loads(parent.get("/settings/account/export").get_data())
        assert export["settings"]["calendars"][0]["url"].endswith("basic.ics")

    def test_and_the_platform_s_own_facts(self, parent):
        export = json.loads(parent.get("/settings/account/export").get_data())
        assert export["family"]["plan"] == "standard"
        assert export["family"]["status"] == "trialing"

    def test_but_never_the_screen_token(self, parent, pg_pool, family):
        """A live credential must not ride along in a file that gets emailed to
        somebody and forgotten. It is on the screen page, where reading it and
        rotating it are one gesture."""
        token = screens.token_for(pg_pool, family[0])
        body = parent.get("/settings/account/export").get_data(as_text=True)
        assert token not in body

    def test_a_signed_out_visitor_gets_nothing(self, cloud):
        landed = client_for(cloud).get("/settings/account/export")
        assert landed.status_code == 302
        assert landed.headers["Location"].endswith("/login")


# -- delete -----------------------------------------------------------------

class TestDelete:
    TABLES = ("agendas", "generations", "content_history", "calendar_health",
              "model_spend")

    def test_typing_the_address_deletes_the_family(self, parent, pg_pool, family):
        parent.post("/settings/account", data={"confirm": ADDRESS})
        assert rows(pg_pool, "SELECT id FROM families WHERE id = %s", (family[0],)) == []

    def test_and_the_user_with_it(self, parent, pg_pool):
        parent.post("/settings/account", data={"confirm": ADDRESS})
        assert rows(pg_pool, "SELECT id FROM users WHERE email = %s", (ADDRESS,)) == []

    @pytest.mark.parametrize("table", TABLES)
    def test_every_table_cascades(self, parent, pg_pool, family, table):
        """The foreign keys promise this. Asserting it is what turns the promise
        into something the privacy policy can say out loud."""
        parent.post("/settings/account", data={"confirm": ADDRESS})
        assert rows(pg_pool, f"SELECT 1 FROM {table} WHERE family_id = %s",
                    (family[0],)) == []

    def test_a_signup_token_goes_too_and_nothing_cascades_to_it(
            self, parent, pg_pool, family):
        """**The one row outside every cascade.** A sign-up token has no
        `user_id` — that is the whole point of it (DIN-41) — so deleting the
        family does not reach it. Left alone it would expire in fifteen minutes
        and be swept, which makes this the difference between "deleted" meaning
        what the policy says and meaning nearly that."""
        assert accounts.issue_signup_link(pg_pool, ADDRESS) is not None
        parent.post("/settings/account", data={"confirm": ADDRESS})
        assert rows(pg_pool, "SELECT id FROM login_tokens WHERE email = %s",
                    (ADDRESS,)) == []

    def test_a_sign_in_token_goes_with_its_user(self, parent, pg_pool, family):
        assert accounts.issue_link(pg_pool, family[1]) is not None
        parent.post("/settings/account", data={"confirm": ADDRESS})
        assert rows(pg_pool, "SELECT id FROM login_tokens WHERE user_id = %s",
                    (family[1],)) == []

    def test_it_signs_them_out(self, parent, pg_pool):
        parent.post("/settings/account", data={"confirm": ADDRESS})
        with parent.session_transaction() as stored:
            assert "user_id" not in stored
            assert "family_id" not in stored

    def test_and_the_board_stops_working(self, parent, pg_pool, family):
        """"Every screen showing your dashboard stops working" is what the page
        promises, and a screen that kept serving a deleted family's day would be
        the worst possible way to find out otherwise."""
        path = f"/s/{screens.token_for(pg_pool, family[0])}"
        assert parent.get(path).status_code == 200
        parent.post("/settings/account", data={"confirm": ADDRESS})
        assert parent.get(path).status_code == 404


class TestDeleteIsHardToDoByAccident:
    def test_the_wrong_address_deletes_nothing(self, parent, pg_pool, family):
        parent.post("/settings/account", data={"confirm": "someone@else.example"})
        assert rows(pg_pool, "SELECT id FROM families WHERE id = %s", (family[0],))

    def test_an_empty_confirmation_deletes_nothing(self, parent, pg_pool, family):
        parent.post("/settings/account", data={"confirm": ""})
        assert rows(pg_pool, "SELECT id FROM families WHERE id = %s", (family[0],))

    def test_and_says_what_to_type(self, parent):
        landed = parent.post("/settings/account", data={"confirm": "nope"},
                             follow_redirects=True)
        assert "Type the email address on this account" in landed.get_data(as_text=True)

    def test_case_and_spaces_are_forgiven(self, parent, pg_pool, family):
        """Somebody typing their own address on a phone is not the threat."""
        parent.post("/settings/account", data={"confirm": f"  {ADDRESS.upper()} "})
        assert rows(pg_pool, "SELECT id FROM families WHERE id = %s", (family[0],)) == []

    def test_it_needs_a_csrf_token_like_every_other_write(self, cloud, family):
        bare = cloud.test_client()
        with bare.session_transaction() as stored:
            stored["user_id"] = family[1]
            stored["family_id"] = str(family[0])
        assert bare.post("/settings/account",
                         data={"confirm": ADDRESS}).status_code == 400

    def test_a_signed_out_visitor_cannot_reach_it(self, cloud):
        landed = client_for(cloud).post("/settings/account", data={"confirm": ADDRESS})
        assert landed.status_code == 302


class TestOneFamilyCannotDeleteAnother:
    def test_the_session_decides_and_nothing_else_can(self, cloud, pg_pool, family):
        """There is no family id in the URL or the form to get wrong. The
        confirmation is the *session's* address, so holding one family's cookie
        and typing another family's address deletes neither."""
        from dinkydash import config as config_module

        with pg_pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO families (screen_token, config)
                               VALUES (%s, '{}'::jsonb) RETURNING id""",
                            (config_module.new_screen_token(),))
                other = cur.fetchone()[0]
                cur.execute("INSERT INTO users (family_id, email) VALUES (%s, %s)",
                            (other, "other@example.com"))

        mine = client_for(cloud)
        with mine.session_transaction() as stored:
            stored["user_id"] = family[1]
            stored["family_id"] = str(family[0])
        mine.post("/settings/account", data={"confirm": "other@example.com"})

        assert rows(pg_pool, "SELECT id FROM families WHERE id = %s", (other,))
        assert rows(pg_pool, "SELECT id FROM families WHERE id = %s", (family[0],))

        with pg_pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute("DELETE FROM families WHERE id = %s", (other,))


# -- and a self-hoster sees none of it --------------------------------------

class TestSingleModeHasNoAccount:
    @pytest.fixture
    def single(self, tmp_path):
        (tmp_path / "config.yaml").write_text(CONFIG)
        return create_app(FileStore(tmp_path / "config.yaml"))

    def test_there_is_no_account_page(self, single):
        assert single.test_client().get("/settings/account").status_code == 404

    def test_and_no_export(self, single):
        assert single.test_client().get("/settings/account/export").status_code == 404

    def test_the_settings_home_does_not_offer_one(self, single):
        page = single.test_client().get("/settings/").get_data(as_text=True)
        assert "Your data" not in page


class TestWhereItGoes:
    """The account page says who sees what, beside the buttons (DIN-44)."""

    @pytest.mark.parametrize("who", ["Anthropic", "SendGrid", "Sentry"])
    def test_it_names(self, parent, who):
        page = parent.get("/settings/account").get_data(as_text=True)
        assert who in page
