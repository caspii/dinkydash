"""First-touch attribution, stored once at signup.

The cookie the marketing site sets and the query string on `/login` are both
read in `web/attribution.py`; what lands on the family is decided in
`dinkydash/accounts.set_first_touch`, which only ever writes the column while
it is still empty.
"""

import json
import re
from urllib.parse import quote

import pytest

from dinkydash import accounts, mail
from tests.conftest import client_for, open_the_link
from web import create_app

NEWCOMER = "first-touch-newcomer@example.com"
RETURNING = "first-touch-returning@example.com"


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
    return create_app(pool=pg_pool)


@pytest.fixture
def client(cloud):
    return client_for(cloud)


def link_in(message):
    found = re.search(r"https?://\S+/login/link\?t=[\w\-]+", message["text"])
    assert found, message["text"]
    return found.group(0)


def first_touch_for(pool, address):
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT f.first_touch FROM families f
               JOIN users u ON u.family_id = f.id
               WHERE lower(u.email) = %s""",
            (address,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def forget(pool, address):
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT family_id FROM users WHERE lower(email) = %s", (address,))
        row = cur.fetchone()
    if row is not None:
        accounts.delete_family(pool, row[0])
    with pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM login_tokens WHERE email = %s", (address,))


class TestCapturedAtSignup:
    def test_the_query_string_on_login_is_stored_on_the_new_family(
            self, client, sent, pg_pool):
        try:
            client.post("/login?utm_source=google&utm_campaign=launch&gclid=abc123",
                       data={"email": NEWCOMER})
            open_the_link(client, link_in(sent[-1]))
            assert first_touch_for(pg_pool, NEWCOMER) == {
                "utm_source": "google", "utm_campaign": "launch", "gclid": "abc123",
            }
        finally:
            forget(pg_pool, NEWCOMER)

    def test_the_cookie_wins_over_the_query_string(self, client, sent, pg_pool):
        cookie = quote(json.dumps({"utm_source": "cookie-value"}))
        try:
            client.post("/login?utm_source=query-value", data={"email": NEWCOMER},
                       headers={"Cookie": f"dd_ft={cookie}"})
            open_the_link(client, link_in(sent[-1]))
            assert first_touch_for(pg_pool, NEWCOMER) == {"utm_source": "cookie-value"}
        finally:
            forget(pg_pool, NEWCOMER)

    def test_nothing_on_the_request_stores_nothing(self, client, sent, pg_pool):
        try:
            client.post("/login", data={"email": NEWCOMER})
            open_the_link(client, link_in(sent[-1]))
            assert first_touch_for(pg_pool, NEWCOMER) is None
        finally:
            forget(pg_pool, NEWCOMER)

    def test_it_survives_to_the_link_click_with_no_params_on_that_request(
            self, client, sent, pg_pool):
        """The `/login` POST and the magic-link click are different requests."""
        try:
            client.post("/login?utm_source=google", data={"email": NEWCOMER})
            link = link_in(sent[-1])
            assert "utm_source" not in link
            open_the_link(client, link)
            assert first_touch_for(pg_pool, NEWCOMER) == {"utm_source": "google"}
        finally:
            forget(pg_pool, NEWCOMER)


class TestItIsNeverOverwritten:
    def test_a_later_sign_in_does_not_replace_it(self, client, sent, pg_pool):
        try:
            client.post("/login?utm_source=first-visit", data={"email": RETURNING})
            open_the_link(client, link_in(sent[-1]))
            assert first_touch_for(pg_pool, RETURNING) == {"utm_source": "first-visit"}

            client.post("/logout")
            sent.clear()
            client.post("/login?utm_source=second-visit", data={"email": RETURNING})
            open_the_link(client, link_in(sent[-1]))
            assert first_touch_for(pg_pool, RETURNING) == {"utm_source": "first-visit"}
        finally:
            forget(pg_pool, RETURNING)

    def test_calling_set_first_touch_again_directly_changes_nothing(self, pg_pool, pg_family):
        accounts.set_first_touch(pg_pool, pg_family, {"utm_source": "first"})
        accounts.set_first_touch(pg_pool, pg_family, {"utm_source": "second"})
        with pg_pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT first_touch FROM families WHERE id = %s", (pg_family,))
            assert cur.fetchone()[0] == {"utm_source": "first"}

    def test_an_empty_first_touch_writes_nothing(self, pg_pool, pg_family):
        accounts.set_first_touch(pg_pool, pg_family, {})
        accounts.set_first_touch(pg_pool, pg_family, None)
        with pg_pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT first_touch FROM families WHERE id = %s", (pg_family,))
            assert cur.fetchone()[0] is None
