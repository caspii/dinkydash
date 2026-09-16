"""The bot check in front of the sign-in form.

Four claims, and the first is the one that keeps everybody else working:

* **it is off unless both keys are set**, so a self-hoster, a developer and
  this suite reach no network and need no Cloudflare account;
* **a refused challenge costs nothing** — no email leaves, and the address is
  never even looked up, so nothing about it can be inferred from the answer;
* **a refusal says the same thing whatever address was typed**, because the
  sign-in form is the sign-up form and anything address-shaped is an
  enumeration oracle;
* **a Cloudflare we cannot reach is not a Cloudflare that said no.** The first
  is allowed through, deliberately; the second never is.

No network is touched here: `requests.post` is replaced in every test that
would otherwise reach one, and the assertions are about what we sent it and
what we did with what came back.

The Postgres half skips without `DINKYDASH_TEST_DATABASE_URL`, like the rest of
the suite. Everything that can be checked without a database is.
"""

import pytest
import requests
import yaml

from dinkydash import mail
from tests.conftest import client_for
from web import create_app, turnstile

ANSWER = "an-answer-from-the-widget"

ADDRESS = "parent@example.com"

CONFIG = '''\
family_name: "The Wilsons"
timezone: "Europe/Berlin"
people:
  - id: mia12345
    name: "Mia"
    date_of_birth: "2017-03-15"
'''


@pytest.fixture
def sent(monkeypatch):
    """Every email the app tried to send, instead of sending it."""
    outbox = []
    monkeypatch.setattr(
        mail, "send",
        lambda to, subject, text, html=None, **kw: outbox.append(to))
    return outbox


@pytest.fixture
def client(pg_pool, pg_family, monkeypatch):
    from dinkydash.pgstore import PostgresStore

    PostgresStore(pg_pool, pg_family).save_config(yaml.safe_load(CONFIG))
    monkeypatch.setenv("DINKYDASH_MODE", "cloud")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "a-real-one")
    return client_for(create_app(pool=pg_pool))


@pytest.fixture
def pg_user(pg_pool, pg_family):
    """One parent with an account, so "known" and "unknown" can be compared."""
    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (family_id, email) VALUES (%s, %s) RETURNING id",
                (pg_family, ADDRESS),
            )
            return cur.fetchone()[0]


@pytest.fixture
def keys(monkeypatch):
    """Turnstile switched on, with keys that are obviously not real ones."""
    monkeypatch.setenv("TURNSTILE_SITE_KEY", "0xSITE")
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "0xSECRET")


@pytest.fixture
def cloudflare(monkeypatch):
    """Whatever Cloudflare would have said, and what we asked it."""
    asked = []

    class Reply:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def answer(payload=None, raises=None):
        def _post(url, data=None, timeout=None):
            asked.append({"url": url, "data": data, "timeout": timeout})
            if raises is not None:
                raise raises
            return Reply(payload)

        monkeypatch.setattr(requests, "post", _post)
        return asked

    answer.asked = asked
    return answer


# -- switched off is the default --------------------------------------------

class TestWhenThereAreNoKeys:
    def test_it_is_not_configured(self, monkeypatch):
        monkeypatch.delenv("TURNSTILE_SITE_KEY", raising=False)
        monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
        assert not turnstile.configured()

    def test_everything_passes(self, monkeypatch):
        monkeypatch.delenv("TURNSTILE_SITE_KEY", raising=False)
        monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
        assert turnstile.passed("") is True

    def test_nothing_is_asked_of_cloudflare(self, monkeypatch, cloudflare):
        monkeypatch.delenv("TURNSTILE_SITE_KEY", raising=False)
        monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
        asked = cloudflare({"success": True})
        turnstile.passed("")
        assert asked == []

    @pytest.mark.parametrize("site,secret", [("0xSITE", ""), ("", "0xSECRET")])
    def test_half_a_pair_is_not_configured(self, monkeypatch, site, secret):
        """A widget nobody verifies is worse than none: it looks like a control."""
        monkeypatch.setenv("TURNSTILE_SITE_KEY", site)
        monkeypatch.setenv("TURNSTILE_SECRET_KEY", secret)
        assert not turnstile.configured()


# -- what we send, and what we do with the answer ----------------------------

class TestCheckingAnAnswer:
    def test_a_good_one_passes(self, keys, cloudflare):
        cloudflare({"success": True})
        assert turnstile.passed(ANSWER) is True

    def test_a_bad_one_does_not(self, keys, cloudflare):
        cloudflare({"success": False, "error-codes": ["invalid-input-response"]})
        assert turnstile.passed(ANSWER) is False

    def test_an_empty_one_is_refused_without_asking(self, keys, cloudflare):
        asked = cloudflare({"success": True})
        assert turnstile.passed("") is False
        assert asked == []

    def test_an_absurdly_long_one_is_refused_without_being_sent(self, keys, cloudflare):
        asked = cloudflare({"success": True})
        assert turnstile.passed("x" * 100_000) is False
        assert asked == []

    def test_the_secret_goes_to_cloudflare_and_the_answer_with_it(self, keys, cloudflare):
        asked = cloudflare({"success": True})
        turnstile.passed(ANSWER)
        assert asked[0]["url"] == turnstile.VERIFY_URL
        assert asked[0]["data"]["secret"] == "0xSECRET"
        assert asked[0]["data"]["response"] == ANSWER

    def test_the_callers_address_goes_too_when_there_is_one(self, keys, cloudflare):
        asked = cloudflare({"success": True})
        turnstile.passed(ANSWER, "93.184.216.34")
        assert asked[0]["data"]["remoteip"] == "93.184.216.34"

    def test_and_is_left_out_when_there_is_not(self, keys, cloudflare):
        """`client_ip` answers `""` when a caller cannot be told apart."""
        asked = cloudflare({"success": True})
        turnstile.passed(ANSWER, "")
        assert "remoteip" not in asked[0]["data"]

    def test_the_request_has_a_deadline(self, keys, cloudflare):
        asked = cloudflare({"success": True})
        turnstile.passed(ANSWER)
        assert asked[0]["timeout"] == turnstile.SECONDS


class TestWhenCloudflareCannotBeReached:
    """Allowed through on purpose — see the module docstring in web/turnstile.py.

    Both rate limits and the spend breaker are still behind this. A Cloudflare
    outage that lets some scripted sign-ups through is a smaller failure than
    one that stops every family signing in.
    """

    @pytest.mark.parametrize("failure", [
        requests.ConnectionError("no route"),
        requests.Timeout("too slow"),
        requests.HTTPError("500"),
        ValueError("that was not JSON"),
    ], ids=["connection", "timeout", "http-error", "not-json"])
    def test_the_answer_is_allowed_through(self, keys, cloudflare, failure):
        cloudflare(raises=failure)
        assert turnstile.passed(ANSWER) is True

    def test_but_it_says_so_in_the_log(self, keys, cloudflare, caplog):
        cloudflare(raises=requests.Timeout("too slow"))
        with caplog.at_level("WARNING", logger="web.turnstile"):
            turnstile.passed(ANSWER)
        assert "Could not put a sign-in challenge" in caplog.text

    def test_and_never_the_secret(self, keys, cloudflare, caplog):
        cloudflare(raises=requests.ConnectionError("connecting to 0xSECRET failed"))
        with caplog.at_level("WARNING", logger="web.turnstile"):
            turnstile.passed(ANSWER)
        assert "0xSECRET" not in caplog.text


# -- the form it guards ------------------------------------------------------

class TestTheSignInForm:
    """Needs the cloud app, so it needs a database."""

    def test_the_widget_is_absent_without_keys(self, client, monkeypatch):
        monkeypatch.delenv("TURNSTILE_SITE_KEY", raising=False)
        monkeypatch.delenv("TURNSTILE_SECRET_KEY", raising=False)
        page = client.get("/login").get_data(as_text=True)
        assert "challenges.cloudflare.com" not in page
        assert "cf-turnstile" not in page

    def test_and_present_with_them(self, client, keys):
        page = client.get("/login").get_data(as_text=True)
        assert "challenges.cloudflare.com/turnstile/v0/api.js" in page
        assert 'data-sitekey="0xSITE"' in page

    def test_the_secret_is_never_rendered(self, client, keys):
        assert "0xSECRET" not in client.get("/login").get_data(as_text=True)

    def test_a_refused_challenge_sends_no_email(self, client, keys, cloudflare, sent):
        cloudflare({"success": False, "error-codes": ["invalid-input-response"]})
        client.post("/login", data={"email": "parent@example.com",
                                    turnstile.FIELD: ANSWER})
        assert sent == []

    def test_a_refused_challenge_says_the_same_thing_for_every_address(
            self, client, keys, cloudflare, pg_user, sent):
        """`pg_user` has an account and the other address does not.

        The form echoes back what was typed into it, which is the one thing the
        two pages are allowed to differ by — it came from the sender. With each
        address taken out, what is left has to be the same page, or the refusal
        says which addresses already have an account.
        """
        cloudflare({"success": False, "error-codes": ["invalid-input-response"]})

        def refusal_for(address):
            page = client.post("/login", data={"email": address,
                                               turnstile.FIELD: ANSWER})
            return page.get_data(as_text=True).replace(address, "AN-ADDRESS")

        assert refusal_for(ADDRESS) == refusal_for("nobody@example.com")

    def test_a_passed_challenge_sends_one(self, client, keys, cloudflare, sent, pg_user):
        cloudflare({"success": True})
        client.post("/login", data={"email": "parent@example.com",
                                    turnstile.FIELD: ANSWER})
        assert len(sent) == 1
