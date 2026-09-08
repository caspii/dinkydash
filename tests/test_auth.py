"""Magic-link auth: one email, one link, one session.

Four claims, and each of them is invisible until it is not:

* **the link is the whole credential**, so it is hashed at rest, spent once,
  short-lived, and never written to a page, a log or a row in plaintext;
* **the answer is the same whether or not the address has an account**,
  because anything else is an enumeration oracle against a product whose
  users are families;
* **no form can be submitted from somebody else's page**, in either mode;
* **cloud mode's `/settings` is behind all of it**, and single mode's is not
  and must not be — a self-hoster has no account to sign in to.

The Postgres half skips unless `DINKYDASH_TEST_DATABASE_URL` is set, like the
rest of the suite. What can be tested without a database — the token shapes,
the cookie flags, CSRF, the rate limiter — is tested without one.
"""

import pathlib
import re

import pytest
import yaml

from dinkydash import accounts, mail
from dinkydash.store import FileStore
from tests.conftest import client_for
from web import create_app
from web.ratelimit import Limiter, client_ip

REPO = pathlib.Path(__file__).resolve().parent.parent

CONFIG = '''\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
people:
  - id: mia12345
    name: "Mia"
    date_of_birth: "2017-03-15"
'''

ADDRESS = "parent@example.com"


@pytest.fixture
def single(tmp_path):
    """A self-hosted app: no accounts, no login, no Secure cookie."""
    (tmp_path / "config.yaml").write_text(CONFIG)
    return create_app(FileStore(tmp_path / "config.yaml"))


@pytest.fixture
def pg_user(pg_pool, pg_family):
    """One parent on that family, and the id of their row."""
    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (family_id, email) VALUES (%s, %s) RETURNING id",
                (pg_family, ADDRESS),
            )
            return cur.fetchone()[0]


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
    """A cloud app over that family, with a store and therefore a pool."""
    from dinkydash.pgstore import PostgresStore

    store = PostgresStore(pg_pool, pg_family)
    store.save_config(yaml.safe_load(CONFIG))
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
    return create_app(pool=pg_pool)


@pytest.fixture
def client(cloud):
    return client_for(cloud)


def link_in(message):
    """The sign-in URL out of an email body."""
    found = re.search(r"https?://\S+/login/link\?t=[\w\-]+", message["text"])
    assert found, message["text"]
    return found.group(0)


def token_in(message):
    return link_in(message).split("t=")[1]


# -- the token itself, with no database in sight ----------------------------

class TestTheTokenShape:
    def test_a_token_is_32_bytes_of_entropy(self):
        # url-safe base64 of 32 bytes, with the padding stripped.
        assert len(accounts.new_token()) == 43

    def test_two_tokens_are_never_the_same(self):
        assert len({accounts.new_token() for _ in range(100)}) == 100

    def test_the_hash_is_not_the_token(self):
        token = accounts.new_token()
        assert accounts.hash_token(token) != token

    def test_the_same_token_always_hashes_the_same(self):
        token = accounts.new_token()
        assert accounts.hash_token(token) == accounts.hash_token(token)

    def test_the_hash_fits_the_column(self):
        # login_tokens.token_hash is TEXT with CHECK (length <= 128).
        assert len(accounts.hash_token(accounts.new_token())) <= 128

    @pytest.mark.parametrize("typed,stored", [
        ("Parent@Example.COM", "parent@example.com"),
        ("  parent@example.com  ", "parent@example.com"),
        (None, ""),
    ])
    def test_an_address_is_compared_lower_cased_and_trimmed(self, typed, stored):
        assert accounts.normalise(typed) == stored


# -- what the cookie says about itself --------------------------------------

class TestTheSessionCookie:
    def test_cloud_mode_marks_it_secure(self, cloud):
        assert cloud.config["SESSION_COOKIE_SECURE"] is True

    def test_single_mode_does_not(self, single):
        # A Pi serves plain HTTP on a LAN. A Secure cookie there is a cookie
        # the browser never sends, which is every flash message lost.
        assert single.config["SESSION_COOKIE_SECURE"] is False

    @pytest.mark.parametrize("key,value", [
        ("SESSION_COOKIE_HTTPONLY", True),
        ("SESSION_COOKIE_SAMESITE", "Lax"),
    ])
    def test_the_other_two_are_the_same_in_both_modes(self, single, key, value):
        assert single.config[key] == value

    def test_cloud_agrees(self, cloud):
        assert cloud.config["SESSION_COOKIE_HTTPONLY"] is True
        assert cloud.config["SESSION_COOKIE_SAMESITE"] == "Lax"


# -- CSRF, in both modes ----------------------------------------------------

class TestCsrf:
    """On in single mode too. A page in another tab can POST to
    `http://raspberrypi.local:5123/settings/...` without it."""

    @pytest.fixture
    def plain(self, single):
        """A client that does *not* fill the token in for itself."""
        single.config["TESTING"] = True
        return single.test_client()

    def test_a_write_with_no_token_is_refused(self, plain):
        response = plain.post("/settings/system", data={"family_name": "The Bakers"})
        assert response.status_code == 400

    def test_a_write_with_the_wrong_token_is_refused(self, plain):
        plain.get("/settings/system")  # mints a real one into the session
        response = plain.post("/settings/system",
                              data={"family_name": "The Bakers",
                                    "csrf_token": "not-the-one"})
        assert response.status_code == 400

    def test_the_right_token_goes_through(self, single):
        client = client_for(single)
        assert client.post("/settings/system",
                           data={"family_name": "The Bakers",
                                 "timezone": "UTC"}).status_code == 302

    def test_a_token_full_of_emoji_is_a_400_not_a_500(self, plain):
        # `hmac.compare_digest` raises TypeError on a non-ASCII `str`.
        plain.get("/settings/system")
        assert plain.post("/settings/system",
                          data={"family_name": "The Bakers",
                                "csrf_token": "🎈🎈🎈"}).status_code == 400

    def test_a_read_needs_nothing(self, plain):
        assert plain.get("/settings/").status_code == 200

    def test_the_refusal_does_not_write_anything(self, plain, tmp_path):
        before = (tmp_path / "config.yaml").read_text()
        plain.post("/settings/system", data={"family_name": "The Bakers"})
        assert (tmp_path / "config.yaml").read_text() == before

    def test_every_form_that_writes_carries_the_field(self):
        """A form added without one is a form that stops working, silently."""
        missing, seen = [], 0
        for path in (REPO / "web" / "templates").rglob("*.html"):
            text = path.read_text()
            for form in re.findall(r"<form\b.*?</form>", text, re.S):
                if 'method="post"' not in form:
                    continue
                seen += 1
                if "csrf_token" not in form:
                    missing.append(str(path.relative_to(REPO)))
        assert missing == []
        # Or a regex that stopped matching would make this pass by finding none.
        assert seen >= 9


# -- the rate limiter -------------------------------------------------------

class TestTheLimiter:
    def test_it_allows_up_to_the_limit(self):
        limiter = Limiter(most=3, per=60)
        assert [limiter.allow("a", now=0) for _ in range(3)] == [True, True, True]

    def test_and_refuses_the_next(self):
        limiter = Limiter(most=3, per=60)
        for _ in range(3):
            limiter.allow("a", now=0)
        assert limiter.allow("a", now=0) is False

    def test_the_window_rolls(self):
        limiter = Limiter(most=1, per=60)
        assert limiter.allow("a", now=0) is True
        assert limiter.allow("a", now=59) is False
        assert limiter.allow("a", now=61) is True

    def test_one_key_does_not_limit_another(self):
        limiter = Limiter(most=1, per=60)
        assert limiter.allow("a", now=0) is True
        assert limiter.allow("b", now=0) is True

    def test_it_forgets_the_oldest_rather_than_growing_forever(self):
        limiter = Limiter(most=1, per=60, most_keys=2)
        for key in ("a", "b", "c"):
            limiter.allow(key, now=0)
        # "a" was the least recently seen, so it is the one that went.
        assert limiter.allow("a", now=0) is True
        assert limiter.allow("c", now=0) is False


class TestWhichAddressItCounts:
    """`X-Forwarded-For` read from the right, stepping over private hops.

    The addresses here are real public ones on purpose. Python's `ipaddress`
    counts the documentation ranges — `203.0.113.0/24` and friends — as
    *private*, so a test written with those would pass through the fallback
    branch and prove nothing.
    """

    CLIENT = "93.184.216.34"      # what our proxy saw
    CLAIMED = "8.8.8.8"           # what the caller put in the header
    INTERNAL = "10.1.2.3"         # a hop inside the platform

    class _Request:
        def __init__(self, headers, remote_addr):
            self.headers = headers
            self.remote_addr = remote_addr

    def _asking_from(self, forwarded, remote_addr="10.0.0.1"):
        headers = {"X-Forwarded-For": forwarded} if forwarded else {}
        return self._Request(headers, remote_addr)

    def test_with_no_proxy_it_is_the_socket(self):
        assert client_ip(self._asking_from(None, self.CLIENT)) == self.CLIENT

    def test_the_last_public_hop_wins(self):
        assert client_ip(
            self._asking_from(f"{self.CLAIMED}, {self.CLIENT}")) == self.CLIENT

    def test_a_caller_cannot_pretend_to_be_someone_else(self):
        """Everything before the last hop is whatever the caller sent."""
        assert client_ip(
            self._asking_from(f"invented, {self.CLIENT}")) == self.CLIENT

    def test_an_internal_hop_is_stepped_over(self):
        """Otherwise a second proxy would put every family in one bucket."""
        assert client_ip(self._asking_from(
            f"{self.CLAIMED}, {self.CLIENT}, {self.INTERNAL}")) == self.CLIENT

    def test_all_private_falls_back_to_the_last_hop(self):
        assert client_ip(self._asking_from(self.INTERNAL)) == self.INTERNAL

    def test_nonsense_is_not_an_address(self):
        assert client_ip(self._asking_from("not-an-ip")) == "not-an-ip"


# -- what single mode must not grow -----------------------------------------

class TestSelfHostedHasNoLogin:
    def test_there_is_no_login_page(self, single):
        assert client_for(single).get("/login").status_code == 404

    def test_there_is_nothing_to_log_out_of(self, single):
        assert client_for(single).post("/logout").status_code == 404

    def test_the_settings_are_not_behind_anything(self, single):
        assert client_for(single).get("/settings/").status_code == 200

    def test_and_the_page_offers_no_sign_out(self, single):
        assert "Sign out" not in client_for(single).get("/settings/").get_data(as_text=True)


# -- asking for a link ------------------------------------------------------

class TestAskingForALink:
    def test_the_form_is_there(self, client):
        assert "Email me a link" in client.get("/login").get_data(as_text=True)

    def test_a_known_address_gets_an_email(self, client, sent, pg_user):
        client.post("/login", data={"email": ADDRESS})
        assert len(sent) == 1
        assert sent[0]["to"] == ADDRESS

    def test_an_unknown_address_gets_none(self, client, sent, pg_user):
        client.post("/login", data={"email": "stranger@example.com"})
        assert sent == []

    def test_but_the_two_pages_are_identical(self, client, sent, pg_user):
        known = client.post("/login", data={"email": ADDRESS})
        unknown = client.post("/login", data={"email": "stranger@example.com"})
        assert known.status_code == unknown.status_code
        assert known.get_data() == unknown.get_data()

    def test_the_address_is_matched_whatever_case_it_is_typed_in(
            self, client, sent, pg_user):
        client.post("/login", data={"email": "Parent@EXAMPLE.com"})
        assert len(sent) == 1

    def test_something_that_is_not_an_address_says_so(self, client, sent):
        page = client.post("/login", data={"email": "not-an-address"})
        # About what was typed, not about who exists — so it gives nothing away.
        assert "does not look like an email address" in page.get_data(as_text=True)
        assert sent == []

    def test_the_reply_never_names_the_address(self, client, sent, pg_user):
        page = client.post("/login", data={"email": ADDRESS}).get_data(as_text=True)
        assert ADDRESS not in page

    def test_the_link_is_never_on_the_page(self, client, sent, pg_user):
        page = client.post("/login", data={"email": ADDRESS}).get_data(as_text=True)
        assert token_in(sent[0]) not in page


class TestOnlyTheHashIsStored:
    def test_the_plaintext_token_is_nowhere_in_the_table(
            self, client, sent, pg_user, pg_pool):
        client.post("/login", data={"email": ADDRESS})
        token = token_in(sent[0])
        with pg_pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT token_hash FROM login_tokens WHERE user_id = %s",
                        (pg_user,))
            stored = [row[0] for row in cur.fetchall()]
        assert stored == [accounts.hash_token(token)]
        assert token not in stored


class TestTheEmailItself:
    def test_it_carries_a_link_to_the_landing_route(self, client, sent, pg_user):
        client.post("/login", data={"email": ADDRESS})
        assert "/login/link?t=" in link_in(sent[0])

    def test_the_link_is_https_whatever_the_request_was(self, client, sent, pg_user):
        # App Platform terminates TLS, so the request that reaches Flask is
        # plain HTTP. A link built from it would put the credential on the wire.
        client.post("/login", data={"email": ADDRESS})
        assert link_in(sent[0]).startswith("https://")

    def test_it_says_what_the_link_does(self, client, sent, pg_user):
        client.post("/login", data={"email": ADDRESS})
        assert "once" in sent[0]["text"]
        assert "fifteen minutes" in sent[0]["text"]

    def test_it_asks_nothing_of_a_third_party(self, client, sent, pg_user):
        """No tracking pixel, no remote CSS. Either would publish the login."""
        client.post("/login", data={"email": ADDRESS})
        body = sent[0]["html"]
        assert "<img" not in body
        for host in ("googleapis", "gstatic", "sendgrid.net", "cdn."):
            assert host not in body


class TestWhereTheLinkPoints:
    """The host comes from configuration, never from the `Host` header.

    Otherwise somebody could POST this form with a victim's address and a
    `Host` of their own, and have a working token mailed to the victim
    pointing at their server.
    """

    @pytest.fixture
    def hosted(self, pg_pool, pg_family, monkeypatch):
        from dinkydash.pgstore import PostgresStore

        store = PostgresStore(pg_pool, pg_family)
        store.save_config(yaml.safe_load(CONFIG))
        monkeypatch.setenv("DINKYDASH_MODE", "cloud")
        monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
        monkeypatch.setenv("DINKYDASH_APP_HOST", "app.dinkydash.co")
        return client_for(create_app(pool=pg_pool))

    def test_it_uses_the_configured_host(self, hosted, sent, pg_user):
        hosted.post("/login", data={"email": ADDRESS})
        assert link_in(sent[0]).startswith("https://app.dinkydash.co/login/link?t=")

    def test_a_forged_host_header_changes_nothing(self, hosted):
        from web.routes.auth import _link_for

        with hosted.application.test_request_context(
                "/login", headers={"Host": "evil.example"}):
            assert _link_for("TOKEN") == "https://app.dinkydash.co/login/link?t=TOKEN"

    def test_and_the_setting_is_doing_the_work(self, client):
        """The same request with no `APP_HOST` *does* follow the header.

        Which is what makes the assertion above mean something rather than
        being true for some other reason.
        """
        from web.routes.auth import _link_for

        with client.application.test_request_context(
                "/login", headers={"Host": "evil.example"}):
            assert _link_for("TOKEN") == "https://evil.example/login/link?t=TOKEN"

    def test_without_one_it_falls_back_to_the_request(self, client, sent, pg_user):
        # Local development and the tests, where there is no hostname to set.
        client.post("/login", data={"email": ADDRESS})
        assert link_in(sent[0]).startswith("https://localhost/login/link?t=")


# -- spending it ------------------------------------------------------------

class TestSigningIn:
    def _link(self, client, sent):
        client.post("/login", data={"email": ADDRESS})
        return link_in(sent[0]).replace("https://localhost", "")

    def test_the_link_signs_you_in(self, client, sent, pg_user):
        response = client.get(self._link(client, sent))
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/settings/")

    def test_and_the_session_carries_the_family(self, client, sent, pg_user, pg_family):
        client.get(self._link(client, sent))
        with client.session_transaction() as stored:
            assert stored["user_id"] == pg_user
            assert stored["family_id"] == str(pg_family)

    def test_the_session_never_carries_the_address(self, client, sent, pg_user):
        """Flask signs the cookie, it does not encrypt it."""
        client.get(self._link(client, sent))
        with client.session_transaction() as stored:
            assert ADDRESS not in str(dict(stored))

    def test_it_records_when(self, client, sent, pg_user, pg_pool):
        client.get(self._link(client, sent))
        with pg_pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT last_login_at FROM users WHERE id = %s", (pg_user,))
            assert cur.fetchone()[0] is not None

    def test_a_second_click_does_not_sign_anybody_in(self, client, sent, pg_user):
        link = self._link(client, sent)
        assert client.get(link).status_code == 302
        second = client.get(link)
        assert second.status_code == 200
        assert "no longer works" in second.get_data(as_text=True)

    def test_single_use_is_decided_in_the_database(self, client, sent, pg_user, pg_pool):
        """Two callers, no request in between: only one may come back a user."""
        client.post("/login", data={"email": ADDRESS})
        token = token_in(sent[0])
        first = accounts.consume_link(pg_pool, token)
        second = accounts.consume_link(pg_pool, token)
        assert first is not None
        assert second is None


class TestALinkThatDoesNotWork:
    """Expired, spent and invented are one answer, and one page."""

    def _dead(self, pg_pool, pg_user, ago="1 hour"):
        token = accounts.new_token()
        with pg_pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO login_tokens (user_id, token_hash, expires_at) "
                    f"VALUES (%s, %s, now() - INTERVAL '{ago}')",
                    (pg_user, accounts.hash_token(token)),
                )
        return token

    def test_an_expired_one_is_refused(self, client, pg_pool, pg_user):
        page = client.get(f"/login/link?t={self._dead(pg_pool, pg_user)}")
        assert "no longer works" in page.get_data(as_text=True)

    def test_an_invented_one_gets_the_same_page(self, client, pg_pool, pg_user):
        expired = client.get(f"/login/link?t={self._dead(pg_pool, pg_user)}")
        invented = client.get("/login/link?t=" + accounts.new_token())
        assert expired.get_data() == invented.get_data()

    def test_no_token_at_all_gets_it_too(self, client, pg_pool, pg_user):
        expired = client.get(f"/login/link?t={self._dead(pg_pool, pg_user)}")
        assert client.get("/login/link").get_data() == expired.get_data()

    def test_an_absurdly_long_one_is_refused_without_being_hashed(self, pg_pool):
        assert accounts.consume_link(pg_pool, "x" * 100_000) is None

    def test_none_of_them_leaves_a_session(self, client, pg_pool, pg_user):
        client.get(f"/login/link?t={self._dead(pg_pool, pg_user)}")
        with client.session_transaction() as stored:
            assert "user_id" not in stored


# -- the two rate limits ----------------------------------------------------

class TestTheLimitPerAddress:
    def test_three_live_links_is_the_most(self, client, sent, pg_user):
        for _ in range(5):
            client.post("/login", data={"email": ADDRESS})
        assert len(sent) == accounts.MOST_LIVE_LINKS

    def test_and_the_page_never_says_so(self, client, sent, pg_user):
        pages = [client.post("/login", data={"email": ADDRESS}).get_data()
                 for _ in range(5)]
        # If being limited looked different, it would say the address exists.
        assert len(set(pages)) == 1

    def test_the_links_already_sent_still_work(self, client, sent, pg_user):
        for _ in range(5):
            client.post("/login", data={"email": ADDRESS})
        first = link_in(sent[0]).replace("https://localhost", "")
        assert client.get(first).status_code == 302


class TestTheLimitPerAddressOfTheCaller:
    def test_a_flooding_caller_sends_no_more_email(self, cloud, sent, pg_user):
        cloud.config["LOGIN_LIMITER"] = Limiter(most=1, per=3600)
        client = client_for(cloud)
        client.post("/login", data={"email": ADDRESS})
        client.post("/login", data={"email": ADDRESS})
        assert len(sent) == 1

    def test_and_that_page_is_the_same_page_too(self, cloud, sent, pg_user):
        cloud.config["LOGIN_LIMITER"] = Limiter(most=1, per=3600)
        client = client_for(cloud)
        first = client.post("/login", data={"email": ADDRESS})
        second = client.post("/login", data={"email": ADDRESS})
        assert first.get_data() == second.get_data()


# -- the gate ---------------------------------------------------------------

class TestTheSettingsAreBehindIt:
    @pytest.mark.parametrize("path", ["/settings/", "/settings/people",
                                      "/settings/system", "/settings/refresh"])
    def test_a_stranger_is_sent_to_the_login(self, client, path):
        response = client.get(path)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_a_write_is_refused_as_well(self, client):
        response = client.post("/settings/system", data={"family_name": "The Bakers"})
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_signing_in_opens_it(self, client, sent, pg_user):
        client.post("/login", data={"email": ADDRESS})
        client.get(link_in(sent[0]).replace("https://localhost", ""))
        assert client.get("/settings/").status_code == 200

    def test_the_login_page_itself_is_open(self, client):
        assert client.get("/login").status_code == 200

    def test_somebody_signed_in_is_not_asked_again(self, client, sent, pg_user):
        client.post("/login", data={"email": ADDRESS})
        client.get(link_in(sent[0]).replace("https://localhost", ""))
        response = client.get("/login")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/settings/")


class TestSigningOut:
    def test_it_empties_the_session(self, client, sent, pg_user):
        client.post("/login", data={"email": ADDRESS})
        client.get(link_in(sent[0]).replace("https://localhost", ""))
        client.post("/logout")
        with client.session_transaction() as stored:
            assert "user_id" not in stored

    def test_and_the_settings_are_shut_again(self, client, sent, pg_user):
        client.post("/login", data={"email": ADDRESS})
        client.get(link_in(sent[0]).replace("https://localhost", ""))
        client.post("/logout")
        assert client.get("/settings/").status_code == 302

    def test_it_cannot_be_done_from_somebody_elses_page(self, cloud):
        cloud.config["TESTING"] = True
        plain = cloud.test_client()
        assert plain.post("/logout").status_code == 400


# -- the sweep --------------------------------------------------------------

class TestTheSweep:
    def test_it_deletes_what_has_expired(self, pg_pool, pg_user):
        with pg_pool.connection() as conn, conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO login_tokens (user_id, token_hash, expires_at) "
                    "VALUES (%s, %s, now() - INTERVAL '1 hour')",
                    (pg_user, accounts.hash_token(accounts.new_token())),
                )
        assert accounts.sweep(pg_pool) == 1

    def test_it_leaves_a_live_one_alone(self, pg_pool, pg_user):
        accounts.issue_link(pg_pool, pg_user)
        assert accounts.sweep(pg_pool) == 0

    def test_the_worker_calls_it_and_never_raises(self, pg_pool, pg_user):
        from worker import sweep_logins
        assert sweep_logins(pg_pool) == 0

    def test_a_broken_sweep_does_not_stop_a_pass(self):
        from worker import sweep_logins

        class Broken:
            def connection(self):
                raise RuntimeError("no database today")

        assert sweep_logins(Broken()) == 0


class TestBothRequestLogsAreScrubbedAnyway:
    """Neither server may write the token, whatever its format string says.

    Flask's development server has no format to configure, and `deploy_on_push`
    does not apply the committed app spec — so production can be running
    gunicorn's default `%(r)s` between a merge and a `doctl apps update`. The
    filter is what makes both of those safe.
    """

    @pytest.fixture
    def record(self):
        import logging
        return logging.LogRecord(
            "werkzeug", logging.INFO, __file__, 0,
            '"%s" %s %s', ("GET /login/link?t=SECRETTOKEN HTTP/1.1", 302, "-"), None)

    def test_the_token_is_taken_out(self, cloud, record):
        from web.routes.auth import NoTokens
        NoTokens().filter(record)
        assert "SECRETTOKEN" not in record.getMessage()
        assert "[redacted]" in record.getMessage()

    def test_the_rest_of_the_line_survives(self, cloud, record):
        from web.routes.auth import NoTokens
        NoTokens().filter(record)
        assert "GET /login/link" in record.getMessage()
        assert "302" in record.getMessage()

    def test_an_ordinary_line_is_left_alone(self, cloud):
        import logging

        from web.routes.auth import NoTokens
        record = logging.LogRecord("werkzeug", logging.INFO, __file__, 0,
                                   '"%s" %s', ("GET /settings/ HTTP/1.1", 200), None)
        NoTokens().filter(record)
        assert record.getMessage() == '"GET /settings/ HTTP/1.1" 200'

    @pytest.mark.parametrize("name", ["werkzeug", "gunicorn.access"])
    def test_building_a_cloud_app_attaches_it(self, cloud, name):
        import logging

        from web.routes.auth import NoTokens
        assert any(isinstance(f, NoTokens)
                   for f in logging.getLogger(name).filters)

    def test_it_reaches_a_gunicorn_access_record(self, cloud):
        """gunicorn logs a format string plus a mapping, not a finished line.

        `%(r)s` is the request line, query string and all, and it is what the
        default format uses — so the filter has to work on a record whose
        message does not exist until it is formatted.
        """
        import logging

        from web.routes.auth import NoTokens
        record = logging.LogRecord(
            "gunicorn.access", logging.INFO, __file__, 0,
            '%(h)s "%(r)s" %(s)s',
            {"h": "203.0.113.9",
             "r": "GET /login/link?t=SECRETTOKEN HTTP/1.1",
             "s": "302"},
            None)
        NoTokens().filter(record)
        assert "SECRETTOKEN" not in record.getMessage()
        assert "203.0.113.9" in record.getMessage()


# -- the log the platform keeps ---------------------------------------------

class TestTheLinkIsNotInTheAccessLog:
    """A login link in a log is a login in a log.

    The token rides in the query string precisely because gunicorn's `%(U)s`
    is the path without one. If this format ever goes back to the default
    `%(r)s`, every sign-in link is written to the platform's log.
    """

    @pytest.fixture
    def run_command(self):
        spec = yaml.safe_load((REPO / ".do" / "app.yaml").read_text())
        return spec["services"][0]["run_command"]

    def test_the_format_is_set_at_all(self, run_command):
        assert "--access-logformat" in run_command

    def test_it_logs_the_path_without_the_query_string(self, run_command):
        assert "%(U)s" in run_command

    @pytest.mark.parametrize("atom", ["%(r)s", "%(q)s"])
    def test_and_never_the_query_string(self, run_command, atom):
        assert atom not in run_command
