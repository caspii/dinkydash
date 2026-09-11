"""Sign-up: a family created by the product rather than by a SQL insert (DIN-41).

Four claims, and the first is the one the whole design turns on:

* **nothing is created until the link is clicked.** A `families` row starts a
  14-day trial and the worker calls Anthropic daily for it, so a POST that made
  one would let a script run up a bill with no card behind it. An unverified
  sign-up must cost exactly one `login_tokens` row and one email;
* **the family and the parent arrive together**, in one transaction, with a
  screen token and a config that renders a dashboard rather than an empty page;
* **the sign-up page and the sign-in page are the same page**, byte for byte,
  because a separate "create an account" route publishes which addresses have
  one;
* **clicking twice, or signing up twice, does not make two families.**

Skips without `DINKYDASH_TEST_DATABASE_URL`, like the rest of the Postgres
half — every assertion here needs rows.
"""

import re

import pytest
import yaml

from dinkydash import accounts, config as config_module, mail
from tests.conftest import client_for
from web import create_app

NEWCOMER = "newcomer@example.com"

CONFIG = '''\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
'''


@pytest.fixture
def sent(monkeypatch):
    """Every email the app tried to send, instead of sending it."""
    outbox = []

    def _send(to, subject, text, html=None, **kwargs):
        outbox.append({"to": to, "subject": subject, "text": text, "html": html})

    monkeypatch.setattr(mail, "send", _send)
    return outbox


@pytest.fixture
def cloud(pg_pool, pg_family, monkeypatch):
    """A cloud app with a pool.

    `pg_family` is here for its teardown and because the app needs a pool
    either way. The families this module makes are its own, created by the
    product under test, and `clean_up` below removes them.
    """
    from dinkydash.pgstore import PostgresStore

    PostgresStore(pg_pool, pg_family).save_config(yaml.safe_load(CONFIG))
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
    return create_app(pool=pg_pool)


@pytest.fixture
def client(cloud):
    return client_for(cloud)


@pytest.fixture(autouse=True)
def clean_up(pg_pool):
    """Delete whatever a test signed up, however it got created.

    Autouse and keyed on the address rather than on a returned id, because the
    point of most of these tests is that the row appears without anybody being
    handed its id.
    """
    yield
    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """DELETE FROM families WHERE id IN (
                       SELECT family_id FROM users WHERE email LIKE %s)""",
                ("%@example.com",),
            )
            cur.execute("DELETE FROM login_tokens WHERE email LIKE %s",
                        ("%@example.com",))


def link_in(message):
    found = re.search(r"https?://\S+/login/link\?t=[\w\-]+", message["text"])
    assert found, message["text"]
    return found.group(0)


def rows(pg_pool, sql, args=()):
    with pg_pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def family_of(pg_pool, address):
    """The family row behind an address, or None. As a dict, for readability."""
    found = rows(pg_pool, """SELECT f.id, f.screen_token, f.status, f.plan,
                                    f.trial_ends_at, f.config
                             FROM families f JOIN users u ON u.family_id = f.id
                             WHERE lower(u.email) = %s""", (address,))
    if not found:
        return None
    keys = ("id", "screen_token", "status", "plan", "trial_ends_at", "config")
    return dict(zip(keys, found[0]))


# -- nothing is created by asking -------------------------------------------

class TestSubmittingAnAddressCreatesNothing:
    """The abuse control, and the reason the schema changed.

    At roughly $0.13 per family per month, ten thousand scripted sign-ups that
    each started a trial would be a real and rising daily Anthropic bill with
    nothing to charge back. So the POST must be cheap.
    """

    def test_no_family_and_no_user_exist_after_a_post(self, client, sent, pg_pool):
        client.post("/login", data={"email": NEWCOMER})
        assert rows(pg_pool, "SELECT id FROM users WHERE email = %s",
                    (NEWCOMER,)) == []
        assert family_of(pg_pool, NEWCOMER) is None

    def test_what_it_does_cost_is_one_token_and_one_email(
            self, client, sent, pg_pool):
        client.post("/login", data={"email": NEWCOMER})
        assert len(rows(pg_pool,
                        "SELECT id FROM login_tokens WHERE email = %s",
                        (NEWCOMER,))) == 1
        assert len(sent) == 1

    def test_the_token_carries_the_address_and_no_user(self, client, sent, pg_pool):
        client.post("/login", data={"email": NEWCOMER})
        held = rows(pg_pool,
                    "SELECT user_id, email FROM login_tokens WHERE email = %s",
                    (NEWCOMER,))
        assert held == [(None, NEWCOMER)]

    def test_an_unclicked_signup_is_swept_like_any_other_dead_token(
            self, client, sent, pg_pool):
        """There is no second cleanup job to write, which is most of the point."""
        client.post("/login", data={"email": NEWCOMER})
        with pg_pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute("UPDATE login_tokens SET expires_at = now() - "
                            "interval '1 minute' WHERE email = %s", (NEWCOMER,))
        assert accounts.sweep(pg_pool) >= 1
        assert rows(pg_pool, "SELECT id FROM login_tokens WHERE email = %s",
                    (NEWCOMER,)) == []


# -- clicking is what creates it --------------------------------------------

class TestClickingTheLinkStartsTheFamily:
    def test_a_family_and_a_parent_appear(self, client, sent, pg_pool):
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        family = family_of(pg_pool, NEWCOMER)
        assert family is not None
        assert family["plan"] == "standard"

    def test_and_the_session_is_theirs(self, client, sent, pg_pool):
        client.post("/login", data={"email": NEWCOMER})
        landed = client.get(link_in(sent[0]))
        assert landed.status_code == 302
        assert landed.headers["Location"].endswith("/settings/")
        with client.session_transaction() as stored:
            assert stored["family_id"] == str(family_of(pg_pool, NEWCOMER)["id"])

    def test_the_screen_token_is_there_from_the_first_moment(
            self, client, sent, pg_pool):
        """Never null: the dashboard's URL is not something to add later."""
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        token = family_of(pg_pool, NEWCOMER)["screen_token"]
        assert 10 <= len(token) <= 32
        assert set(token) <= set(config_module.ID_ALPHABET)

    def test_the_trial_is_fourteen_days_and_the_family_is_trialing(
            self, client, sent, pg_pool):
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        family = family_of(pg_pool, NEWCOMER)
        assert family["status"] == "trialing"
        [(days,)] = rows(pg_pool,
                         "SELECT round(extract(epoch from (trial_ends_at - now()))"
                         " / 86400) FROM families WHERE id = %s", (family["id"],))
        assert days == 14

    def test_no_stripe_customer_is_created(self, client, sent, pg_pool):
        """The trial lives in the app; Stripe enters at conversion (phase 4)."""
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        [(customer,)] = rows(pg_pool,
                             "SELECT stripe_customer_id FROM families WHERE id = %s",
                             (family_of(pg_pool, NEWCOMER)["id"],))
        assert customer is None

    def test_a_dead_link_creates_nothing(self, client, sent, pg_pool):
        client.post("/login", data={"email": NEWCOMER})
        link = link_in(sent[0])
        with pg_pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute("UPDATE login_tokens SET expires_at = now() - "
                            "interval '1 minute' WHERE email = %s", (NEWCOMER,))
        client.get(link)
        assert family_of(pg_pool, NEWCOMER) is None


# -- what the new family sees -----------------------------------------------

class TestTheStartingConfig:
    def test_the_board_has_people_on_it_rather_than_nothing(
            self, client, sent, pg_pool):
        """An empty dashboard looks broken; the invented family is there to replace."""
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        config = family_of(pg_pool, NEWCOMER)["config"]
        assert [person["name"] for person in config["people"]] == ["Mia", "Theo"]
        assert config["recurring"] and config["special_dates"] and config["pets"]

    def test_and_never_a_calendar_url(self, client, sent, pg_pool):
        """An iCal address is a password in a URL. A working example would put
        somebody else's appointments on a stranger's wall."""
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        assert family_of(pg_pool, NEWCOMER)["config"]["calendars"] == []

    def test_every_item_can_be_addressed_before_anybody_opens_the_settings(self):
        """Ids are backfilled on first open in single mode. A hosted family
        should not need that round trip, so the starter carries them."""
        config = config_module.starter_config()
        for key in config_module.LIST_KEYS:
            for item in config[key]:
                assert item.get("id")

    def test_it_carries_no_file_paths(self):
        """`data_file` and `content_history_file` are FileStore's business, and
        a jsonb column is not a directory."""
        config = config_module.starter_config()
        assert "data_file" not in config
        assert "content_history_file" not in config

    def test_the_board_renders_for_a_family_that_has_typed_nothing(
            self, client, sent, pg_pool):
        """It shows the waiting screen, not the seeded people, and that is
        right: there is no payload until the worker's next tick writes one.

        **The seeded config is what the tick then has to work with**, which is
        the reason for seeding it — a family with no people would get a dashboard
        with nothing on it but a date. PLAN.md's "Generate now on signup" is
        what closes the gap between the click and the first dashboard, and it is a
        phase 2 worker item: a web request must not call Anthropic.

        Read at the screen URL, which sign-up gave the family a token for
        before anybody asked. That is the point of writing it at creation
        rather than later: a dashboard is reachable from the first second.
        """
        from tests.conftest import board_path

        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        page = client.get(board_path(pg_pool, family_of(pg_pool, NEWCOMER)["id"]))
        assert page.status_code == 200
        assert "Our family" in page.get_data(as_text=True)

    def test_but_the_settings_show_the_people_straight_away(self, client, sent):
        """Which is where a new parent is sent, and where they replace them."""
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        assert client.get("/settings/").status_code == 200
        listed = client.get("/settings/people").get_data(as_text=True)
        assert "Mia" in listed and "Theo" in listed


class TestTheSettingsSayTheHouseholdIsInvented:
    """Seeding without saying so is somebody else's children on your page.

    A brand-new family lands on the set-up checklist rather than the daily
    controls: nothing to refresh, no dashboard to view and nothing worth writing
    yet. The first step names what is invented, and the buttons that would
    act on it are not there.
    """

    def test_a_brand_new_family_is_told(self, client, sent):
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        page = client.get("/settings/").get_data(as_text=True)
        assert "Set up your dashboard" in page
        assert "Mia, Theo and Biscuit are invented" in page

    def test_and_walked_through_the_steps_in_order(self, client, sent):
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        page = client.get("/settings/").get_data(as_text=True)
        assert page.index("Who lives here") < page.index("Time zone") \
            < page.index("A calendar") < page.index("Put it on the screen")

    def test_the_daily_controls_are_not_offered_yet(self, client, sent):
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        page = client.get("/settings/").get_data(as_text=True)
        assert "Refresh calendars" not in page
        assert "View dashboard" not in page
        assert "Rewrite daily message" not in page
        assert "Write first daily message" not in page  # not until the steps are done

    def test_the_screen_link_arrives_with_the_last_step(self, client, sent, pg_pool):
        from dinkydash.pgstore import PostgresStore

        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        family = family_of(pg_pool, NEWCOMER)
        store = PostgresStore(pg_pool, family["id"])
        config = store.load_config()
        for item in config["people"] + config["pets"]:
            item.pop(config_module.INVENTED)
        config["timezone"] = "Europe/Berlin"
        store.save_config(config)
        page = client.get("/settings/").get_data(as_text=True)
        assert f"/s/{family['screen_token']}" in page
        assert "Write first daily message" in page
        assert 'class="qr"' in page  # drawn locally, never fetched

    def test_the_worker_writes_nothing_for_them_yet(self, client, sent, pg_pool):
        """The seeded family is not a family to write about (`config.is_set_up`)."""
        from datetime import datetime, timezone as tz

        from dinkydash.schedule import due

        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        config = family_of(pg_pool, NEWCOMER)["config"]
        assert due(config, None, datetime.now(tz.utc))["brief"] is False

    def test_the_signal_needs_no_mode_check(self):
        """It is the config that says set up, so a freshly cloned Pi running the
        example file is told the same things — which is why there is no `cloud`
        branch in it."""
        assert not config_module.is_set_up(config_module.starter_config())
        assert config_module.is_set_up({"family_name": "The Bakers",
                                        "timezone": "Europe/London"})


# -- one family, however many links -----------------------------------------

class TestOnlyEverOneFamilyPerAddress:
    def test_clicking_the_same_link_twice_signs_in_once_and_creates_once(
            self, client, sent, pg_pool):
        client.post("/login", data={"email": NEWCOMER})
        link = link_in(sent[0])
        client.get(link)
        client.get(link)  # single use: the second is a dead link
        assert len(rows(pg_pool, "SELECT id FROM users WHERE email = %s",
                        (NEWCOMER,))) == 1

    def test_two_signups_then_both_links_still_make_one_family(
            self, client, sent, pg_pool):
        """Two POSTs before either click mint two live tokens, and both work."""
        client.post("/login", data={"email": NEWCOMER})
        client.post("/login", data={"email": NEWCOMER})
        assert len(sent) == 2
        first = family_after(client, sent[0], pg_pool)
        second = family_after(client, sent[1], pg_pool)
        assert first == second
        assert len(rows(pg_pool, "SELECT id FROM families WHERE id = %s",
                        (first,))) == 1

    def test_and_the_second_click_leaves_no_orphan_family(
            self, client, sent, pg_pool):
        """Losing the race means undoing the family just made, not keeping it."""
        client.post("/login", data={"email": NEWCOMER})
        client.post("/login", data={"email": NEWCOMER})
        before = rows(pg_pool, "SELECT count(*) FROM families")[0][0]
        client.get(link_in(sent[0]))
        client.get(link_in(sent[1]))
        after = rows(pg_pool, "SELECT count(*) FROM families")[0][0]
        assert after == before + 1

    def test_signing_up_with_an_address_that_already_has_an_account(
            self, client, sent, pg_pool):
        """A token minted for an address that gained an account meanwhile signs
        them in rather than giving them a second dashboard."""
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        family = family_of(pg_pool, NEWCOMER)["id"]

        # Signed in, and `/login` redirects somebody who already is — so this
        # is what asking for a second link actually looks like.
        client.post("/logout")
        client.post("/login", data={"email": NEWCOMER})   # now a sign-in link
        client.get(link_in(sent[1]))
        assert family_of(pg_pool, NEWCOMER)["id"] == family

    def test_an_absurdly_long_address_is_refused_before_it_reaches_a_row(
            self, client, sent, pg_pool):
        """`users.email` is 320 characters, and a CHECK violation would be a 500
        on a route anybody can post to. Refused as bad input, and — the reason
        it is checked in the route — never logged as a rate limit it did not
        hit."""
        page = client.post("/login", data={"email": "a" * 400 + "@example.com"})
        assert b"does not look like an email address" in page.get_data()
        assert sent == []
        assert rows(pg_pool, "SELECT id FROM login_tokens WHERE email IS NOT NULL") == []

    def test_the_per_address_limit_counts_signup_links_too(
            self, client, sent, pg_pool):
        """Three live links per address, whichever kind. It is the control that
        caps the SendGrid bill, and sign-up must not be a way round it."""
        for _ in range(5):
            client.post("/login", data={"email": NEWCOMER})
        assert len(sent) == accounts.MOST_LIVE_LINKS


def family_after(client, message, pg_pool):
    client.get(link_in(message))
    return family_of(pg_pool, NEWCOMER)["id"]


# -- and it still says nothing about who exists ------------------------------

class TestTheAnswerIsStillTheSame:
    def test_a_new_address_and_a_returning_one_get_identical_pages(
            self, client, sent, pg_pool):
        """The assertion that actually prevents enumeration. It mattered before
        DIN-41 and it matters more now that one of the two creates something."""
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))          # NEWCOMER now has an account

        returning = client.post("/login", data={"email": NEWCOMER})
        stranger = client.post("/login", data={"email": "nobody@example.com"})
        assert returning.status_code == stranger.status_code
        assert returning.get_data() == stranger.get_data()

    def test_the_page_promises_a_link_without_a_condition_on_it(self, client):
        """It used to say "if that address has an account". Now every address
        that asks really does get one, so the hedge would be a lie."""
        page = client.post("/login", data={"email": NEWCOMER})
        body = page.get_data(as_text=True)
        assert "A link is on its way" in body
        assert "if that address has an account" not in body.lower()

    def test_the_form_is_one_form_with_one_button(self, client):
        """Two buttons is two ways to learn whether an address is registered."""
        page = client.get("/login").get_data(as_text=True)
        assert page.count("<form") == 1
        assert page.count('type="submit"') == 1

    def test_the_two_emails_differ_only_in_the_mailbox(self, client, sent):
        """Safe, because whoever opens that mailbox already knows which they are.
        Telling a new parent the link starts a dashboard is what gets it finished."""
        client.post("/login", data={"email": NEWCOMER})
        client.get(link_in(sent[0]))
        client.post("/logout")
        client.post("/login", data={"email": NEWCOMER})
        assert "Start your DinkyDash dashboard" in sent[0]["subject"]
        assert "sign-in link" in sent[1]["subject"]

    def test_neither_email_carries_anything_but_the_link(self, client, sent):
        """No image, no pixel, no third-party CSS: a login email that loads
        anything hands the fact of the login to whoever serves it."""
        client.post("/login", data={"email": NEWCOMER})
        html = sent[0]["html"]
        assert "<img" not in html and "http://" not in html
        assert len(re.findall(r"https://", html)) == 1
