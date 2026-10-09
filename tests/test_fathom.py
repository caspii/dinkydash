"""Fathom on the public sign-in pages, and nowhere past them.

The counter is off unless `FATHOM_SITE_ID` is a site id. On, it is the three
pages somebody sees before they have an account, plus one page that counts a
new account and then leaves. The dashboard, the settings, billing and the
operator's page do not load it. A returning sign-in is not a sign-up.
"""

import re

import pytest
import yaml

from dinkydash import accounts, mail
from dinkydash.store import FileStore
from tests.conftest import board_path, client_for, open_the_link
from web import create_app, fathom
from website.site import create_site_app

SITE = "HLVHPKAZ"
SCRIPT = "https://cdn.usefathom.com/script.js"
ADDRESS = "parent@example.com"
QUIET_NEWCOMER = "fathom-quiet@example.com"
COUNTED_NEWCOMER = "fathom-counted@example.com"

CONFIG = '''\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
'''


def _scripts(html):
    return re.findall(r"<script\b[^>]*>.*?</script>", html, flags=re.I | re.S)


@pytest.fixture
def sent(monkeypatch):
    outbox = []

    def _send(to, subject, text, html=None, **kwargs):
        outbox.append({"to": to, "subject": subject, "text": text, "html": html})

    monkeypatch.setattr(mail, "send", _send)
    return outbox


@pytest.fixture
def pg_user(pg_pool, pg_family):
    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (family_id, email) VALUES (%s, %s) RETURNING id",
                (pg_family, ADDRESS),
            )
            return cur.fetchone()[0]


@pytest.fixture
def cloud(pg_pool, pg_family, monkeypatch):
    from dinkydash.pgstore import PostgresStore

    store = PostgresStore(pg_pool, pg_family)
    store.save_config(yaml.safe_load(CONFIG))
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
    monkeypatch.setenv("FATHOM_SITE_ID", SITE)
    return create_app(pool=pg_pool)


@pytest.fixture
def client(cloud):
    return client_for(cloud)


def link_in(message):
    found = re.search(r"https?://\S+/login/link\?t=[\w\-]+", message["text"])
    assert found, message["text"]
    return found.group(0)


def forget(pool, address):
    """Drop a family this module created, and the sign-up token that has no user id."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT family_id FROM users WHERE lower(email) = %s", (address,))
        row = cur.fetchone()
    if row is not None:
        accounts.delete_family(pool, row[0])
    with pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM login_tokens WHERE email = %s", (address,))


class TestTheSiteId:
    def test_unset_is_off(self, monkeypatch):
        monkeypatch.delenv("FATHOM_SITE_ID", raising=False)
        assert fathom.site_id() == ""

    def test_blank_is_off(self, monkeypatch):
        monkeypatch.setenv("FATHOM_SITE_ID", "   ")
        assert fathom.site_id() == ""

    def test_markup_is_off(self, monkeypatch):
        monkeypatch.setenv("FATHOM_SITE_ID", '"><script>')
        assert fathom.site_id() == ""

    def test_a_real_one_is_stripped_and_kept(self, monkeypatch):
        monkeypatch.setenv("FATHOM_SITE_ID", f"  {SITE}  ")
        assert fathom.site_id() == SITE


class TestWhenItIsOff:
    """No site id, no script, and a new account still lands on settings."""

    @pytest.fixture
    def quiet(self, cloud, monkeypatch):
        monkeypatch.delenv("FATHOM_SITE_ID", raising=False)
        return client_for(cloud)

    def test_the_public_pages_carry_nothing(self, quiet, sent, pg_user):
        login = quiet.get("/login").get_data(as_text=True)
        sent_page = quiet.post("/login", data={"email": ADDRESS}).get_data(as_text=True)
        landing = quiet.get(link_in(sent[0]).replace("https://localhost", ""))
        landing_page = landing.get_data(as_text=True)
        for page in (login, sent_page, landing_page):
            assert "usefathom" not in page
            assert "trackEvent" not in page
        assert "<script" not in landing_page

    def test_a_new_account_goes_straight_to_settings(self, quiet, sent, pg_pool):
        try:
            quiet.post("/login", data={"email": QUIET_NEWCOMER})
            landed = open_the_link(quiet, link_in(sent[-1]))
            assert landed.status_code == 302
            assert landed.headers["Location"].endswith("/settings/")
            assert "usefathom" not in quiet.get("/settings/").get_data(as_text=True)
        finally:
            forget(pg_pool, QUIET_NEWCOMER)


class TestThePublicPages:
    def test_the_sign_in_page_loads_it(self, client):
        page = client.get("/login")
        body = page.get_data(as_text=True)
        assert page.headers["Referrer-Policy"] == "no-referrer"
        assert body.count(SCRIPT) == 1
        assert f'data-site="{SITE}"' in body
        assert 'data-auto="false"' in body
        assert "fathom.trackPageview" in body
        assert "trackEvent" not in body
        assert "location.href" not in body

    def test_check_your_email_loads_it_and_does_not_count_a_signup(self, client, sent):
        body = client.post("/login", data={"email": ADDRESS}).get_data(as_text=True)
        assert body.count(SCRIPT) == 1
        assert "trackEvent" not in body
        assert "Check your email" in body

    def test_the_confirmation_page_loads_it_and_does_not_press_the_button(
            self, client, sent, pg_user):
        client.post("/login", data={"email": ADDRESS})
        url = link_in(sent[0]).replace("https://localhost", "")
        token = url.split("t=", 1)[1]
        page = client.get(url)
        body = page.get_data(as_text=True)
        assert page.headers["Referrer-Policy"] == "no-referrer"
        assert "http-equiv" not in body.lower()
        assert body.count(SCRIPT) == 1
        assert "trackEvent" not in body
        joined = "\n".join(_scripts(body))
        assert token not in joined
        for needle in ("submit", ".click(", "requestSubmit"):
            assert needle not in joined
        assert f'name="t" value="{token}"' in body

    def test_a_bad_site_id_loads_nothing(self, cloud, monkeypatch):
        monkeypatch.setenv("FATHOM_SITE_ID", '"><img')
        body = client_for(cloud).get("/login").get_data(as_text=True)
        assert "usefathom" not in body
        assert "<img" not in body


class TestSignedInPagesDoNotLoadIt:
    def test_settings_billing_and_the_screen(
            self, client, sent, pg_user, pg_pool, pg_family, monkeypatch):
        client.post("/login", data={"email": ADDRESS})
        landed = open_the_link(client, link_in(sent[0]))
        assert landed.headers["Location"].endswith("/settings/")
        home = client.get("/settings/").get_data(as_text=True)
        billing = client.get("/settings/billing").get_data(as_text=True)
        billing_return = client.get("/settings/billing?checkout=returned").get_data(as_text=True)
        account = client.get("/settings/account").get_data(as_text=True)
        screen = client.get(board_path(pg_pool, pg_family)).get_data(as_text=True)
        monkeypatch.setenv("DINKYDASH_ADMIN_EMAILS", ADDRESS)
        admin = client.get("/admin").get_data(as_text=True)
        for body in (home, billing, billing_return, account, screen, admin):
            assert "usefathom" not in body
            assert "trackEvent" not in body


class TestTheSignupEvent:
    def test_a_new_account_renders_it_once(self, client, sent, pg_pool):
        try:
            client.post("/login", data={"email": COUNTED_NEWCOMER})
            landed = open_the_link(client, link_in(sent[-1]))
            assert landed.status_code == 302
            assert landed.headers["Location"].endswith("/login/welcome")
            page = client.get("/login/welcome")
            body = page.get_data(as_text=True)
            assert page.status_code == 200
            assert "no-store" in page.headers["Cache-Control"]
            assert body.count('fathom.trackEvent("signup")') == 1
            assert body.count(SCRIPT) == 1
            assert "fathom.trackPageview" not in body
            assert COUNTED_NEWCOMER not in body
            assert 'href="/settings/"' in body
            again = client.get("/login/welcome")
            assert again.status_code == 302
            assert again.headers["Location"].endswith("/settings/")
            home = client.get("/settings/").get_data(as_text=True)
            assert "usefathom" not in home
            assert "trackEvent" not in home
        finally:
            forget(pg_pool, COUNTED_NEWCOMER)

    def test_a_returning_sign_in_does_not_render_it(self, client, sent, pg_user):
        client.post("/login", data={"email": ADDRESS})
        landed = open_the_link(client, link_in(sent[0]))
        assert landed.headers["Location"].endswith("/settings/")
        welcome = client.get("/login/welcome")
        assert welcome.status_code == 302
        assert welcome.headers["Location"].endswith("/settings/")
        assert "trackEvent" not in welcome.get_data(as_text=True)

    def test_signed_out_the_welcome_page_is_the_sign_in_page(self, client):
        landed = client.get("/login/welcome")
        assert landed.status_code == 302
        assert landed.headers["Location"].endswith("/login")


class TestASelfHostedDashboard:
    def test_nothing_loads_even_when_the_variable_is_set(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DINKYDASH_MODE", raising=False)
        monkeypatch.setenv("FATHOM_SITE_ID", SITE)
        (tmp_path / "config.yaml").write_text(CONFIG)
        app = client_for(create_app(FileStore(tmp_path / "config.yaml")))
        for path in ("/", "/settings/"):
            body = app.get(path).get_data(as_text=True)
            assert "usefathom" not in body
            assert "trackEvent" not in body


class TestTheMarketingSiteCarriesTheSource:
    def test_the_login_links_stay_put_and_the_script_passes_the_source(self):
        client = create_site_app(site_url="https://dinkydash.co").test_client()
        body = client.get("/").get_data(as_text=True)
        assert 'href="https://app.dinkydash.co/login"' in body
        assert "document.cookie" not in body
        assert "localStorage" not in body
        assert "from.origin" in body
        assert 'referrerPolicy = "origin"' in body
        assert "utm_source" in body
        assert "utm_campaign" in body
        # The path and query of the referring page are not what is copied.
        assert 'searchParams.set("ref", document.referrer)' not in body
        assert client.get("/").headers["Referrer-Policy"] == "no-referrer"
