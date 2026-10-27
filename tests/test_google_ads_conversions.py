"""The `account_created` conversion, fired once on the welcome page.

Mirrors `tests/test_fathom.py`'s `TestTheSignupEvent`: the same session flag
now guards both trackers, and an unset `GOOGLE_ADS_ID` has to behave exactly
like an unset `FATHOM_SITE_ID` -- nothing rendered, nothing fired.
"""

import re

import pytest

from dinkydash import mail
from tests.conftest import client_for, open_the_link
from web import create_app

NEWCOMER = "google-ads-newcomer@example.com"
RETURNING = "google-ads-returning@example.com"
ADS_ID = "AW-123456789"
LABEL = "signupLabel"


@pytest.fixture
def sent(monkeypatch):
    outbox = []

    def _send(to, subject, text, html=None, **kwargs):
        outbox.append({"to": to, "subject": subject, "text": text, "html": html})

    monkeypatch.setattr(mail, "send", _send)
    return outbox


@pytest.fixture
def cloud(pg_pool, monkeypatch):
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
    monkeypatch.setenv("GOOGLE_ADS_ID", ADS_ID)
    monkeypatch.setenv("GOOGLE_ADS_SIGNUP_LABEL", LABEL)
    return create_app(pool=pg_pool)


@pytest.fixture
def client(cloud):
    return client_for(cloud)


def link_in(message):
    found = re.search(r"https?://\S+/login/link\?t=[\w\-]+", message["text"])
    assert found, message["text"]
    return found.group(0)


def forget(pool, address):
    from dinkydash import accounts

    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT family_id FROM users WHERE lower(email) = %s", (address,))
        row = cur.fetchone()
    if row is not None:
        accounts.delete_family(pool, row[0])
    with pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM login_tokens WHERE email = %s", (address,))


class TestTheSignupConversion:
    def test_a_new_account_renders_it_once(self, client, sent, pg_pool):
        try:
            client.post("/login", data={"email": NEWCOMER})
            landed = open_the_link(client, link_in(sent[-1]))
            assert landed.status_code == 302
            assert landed.headers["Location"].endswith("/login/welcome")

            page = client.get("/login/welcome")
            body = page.get_data(as_text=True)
            assert page.status_code == 200
            assert "no-store" in page.headers["Cache-Control"]
            assert f"gtag('config', \"{ADS_ID}\")" in body
            assert f'"send_to": "{ADS_ID}/{LABEL}"' in body
            assert NEWCOMER not in body

            again = client.get("/login/welcome")
            assert again.status_code == 302
            assert again.headers["Location"].endswith("/settings/")
            home = client.get("/settings/").get_data(as_text=True)
            assert "googletagmanager" not in home
        finally:
            forget(pg_pool, NEWCOMER)

    def test_a_returning_sign_in_does_not_render_it(self, client, sent, pg_pool):
        try:
            client.post("/login", data={"email": RETURNING})
            open_the_link(client, link_in(sent[-1]))
            client.post("/logout")
            sent.clear()

            client.post("/login", data={"email": RETURNING})
            landed = open_the_link(client, link_in(sent[-1]))
            assert landed.headers["Location"].endswith("/settings/")
            welcome = client.get("/login/welcome")
            assert welcome.status_code == 302
            assert "googletagmanager" not in welcome.get_data(as_text=True)
        finally:
            forget(pg_pool, RETURNING)

    def test_with_fathom_too_settings_waits_for_both(
            self, client, sent, pg_pool, monkeypatch):
        """Only the page's gate navigates, and only once both have reported.

        A tracker that opened settings itself would cancel whatever the other
        one still had to send.
        """
        monkeypatch.setenv("FATHOM_SITE_ID", "ABCDEFGH")
        try:
            client.post("/login", data={"email": NEWCOMER})
            open_the_link(client, link_in(sent[-1]))
            body = client.get("/login/welcome").get_data(as_text=True)
            assert "var waiting = 2;" in body
            assert body.count("location.replace(") == 1
            assert body.count("trackerDone();") == 3
            assert 'fathom.trackEvent("signup")' in body
            assert f'"send_to": "{ADS_ID}/{LABEL}"' in body
        finally:
            forget(pg_pool, NEWCOMER)


class TestWhenItIsOff:
    @pytest.fixture
    def quiet(self, cloud, monkeypatch):
        monkeypatch.delenv("GOOGLE_ADS_ID", raising=False)
        monkeypatch.delenv("GOOGLE_ADS_SIGNUP_LABEL", raising=False)
        return client_for(cloud)

    def test_the_public_pages_carry_nothing(self, quiet):
        login = quiet.get("/login").get_data(as_text=True)
        assert "googletagmanager" not in login
        assert "gtag(" not in login

    def test_a_new_account_goes_straight_to_settings(self, quiet, sent, pg_pool):
        try:
            quiet.post("/login", data={"email": NEWCOMER})
            landed = open_the_link(quiet, link_in(sent[-1]))
            assert landed.status_code == 302
            assert landed.headers["Location"].endswith("/settings/")
        finally:
            forget(pg_pool, NEWCOMER)
