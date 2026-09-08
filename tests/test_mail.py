"""What `dinkydash.mail.send` must do, and what it must never do.

No test here touches the network. `send` takes a `transport` argument precisely
so the suite stays offline and free — it runs in under a second today, and a
live API call would make it slow, flaky and billable at once.

Two of these tests are about secrets rather than behaviour. This module is what
magic links go out through, and **a login link in a log is a login in a log**;
the recipient's address is personal data too. `tests/test_secrets_and_headers.py`
guards the same promise on the calendar side.
"""

import logging

import pytest
import requests

from dinkydash.mail import MailError, MailRefused, send


class FakeResponse:
    def __init__(self, status_code=202):
        self.status_code = status_code


class Recorder:
    """A stand-in for `requests.post` that remembers what it was called with."""

    def __init__(self, response=None, raises=None):
        self.response, self.raises = response or FakeResponse(), raises
        self.url = self.json = self.headers = self.timeout = None

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.url, self.json, self.headers, self.timeout = url, json, headers, timeout
        if self.raises:
            raise self.raises
        return self.response


def send_ok(**kwargs):
    """Send with a recorded transport and a key, returning the recorder."""
    post = Recorder(**{k: kwargs.pop(k) for k in ("response", "raises") if k in kwargs})
    kwargs.setdefault("to", "parent@example.test")
    kwargs.setdefault("subject", "Your DinkyDash link")
    kwargs.setdefault("text", "Tap to sign in.")
    send(transport=post, api_key="SG.test", **kwargs)
    return post


class TestTheRequest:
    def test_it_posts_to_sendgrid(self):
        assert send_ok().url == "https://api.sendgrid.com/v3/mail/send"

    def test_the_key_travels_as_a_bearer_token(self):
        assert send_ok().headers["Authorization"] == "Bearer SG.test"

    def test_the_recipient_is_in_the_personalisation(self):
        body = send_ok(to="parent@example.test").json
        assert body["personalizations"][0]["to"][0]["email"] == "parent@example.test"

    def test_the_sender_is_on_the_authenticated_domain(self):
        """DKIM only signs for the domain SendGrid validated."""
        assert send_ok().json["from"]["email"].endswith("@dinkydash.co")

    def test_the_sender_can_be_overridden_from_the_environment(self, monkeypatch):
        monkeypatch.setenv("DINKYDASH_MAIL_FROM", "login@dinkydash.co")
        assert send_ok().json["from"]["email"] == "login@dinkydash.co"

    def test_there_is_a_timeout(self):
        """A send that hangs forever would hang whatever asked for it."""
        assert send_ok().timeout > 0


class TestContent:
    def test_plain_text_alone_is_enough(self):
        content = send_ok(text="Tap to sign in.").json["content"]
        assert [c["type"] for c in content] == ["text/plain"]

    def test_plain_text_comes_before_html(self):
        """The order decides which part a client shows when it can render both."""
        content = send_ok(text="Tap to sign in.", html="<p>Tap</p>").json["content"]
        assert [c["type"] for c in content] == ["text/plain", "text/html"]

    @pytest.mark.parametrize("text", ["", "   ", None])
    def test_an_empty_body_is_refused_before_any_request(self, text):
        post = Recorder()
        with pytest.raises(MailRefused, match="plain-text"):
            send("parent@example.test", "Hello", text, transport=post, api_key="SG.test")
        assert post.url is None


class TestAddresses:
    @pytest.mark.parametrize("address", ["", "   ", None])
    def test_no_address_is_a_refusal(self, address):
        with pytest.raises(MailRefused, match="no email address"):
            send(address, "Hi", "Body", transport=Recorder(), api_key="SG.test")

    @pytest.mark.parametrize("address", ["notanemail", "two@@example.test",
                                         "@example.test", "parent@"])
    def test_an_obvious_non_address_is_a_refusal(self, address):
        """Bounces are shared across six domains on this account."""
        with pytest.raises(MailRefused, match="email address"):
            send(address, "Hi", "Body", transport=Recorder(), api_key="SG.test")

    @pytest.mark.parametrize("address", ["a@b.test\nbcc: x@y.test",
                                         "a@b.test\r\nSubject: nope"])
    def test_a_line_break_is_a_refusal(self, address):
        """Header injection, wherever the value ends up next."""
        with pytest.raises(MailRefused, match="line break"):
            send(address, "Hi", "Body", transport=Recorder(), api_key="SG.test")

    def test_surrounding_whitespace_is_trimmed(self):
        body = send_ok(to="  parent@example.test  ").json
        assert body["personalizations"][0]["to"][0]["email"] == "parent@example.test"


class TestFailures:
    def test_a_refused_send_is_a_mail_error_too(self):
        """One `except MailError` catches both; the subclass is for retry decisions."""
        assert issubclass(MailRefused, MailError)

    @pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
    def test_a_non_2xx_status_raises(self, status):
        with pytest.raises(MailError, match=str(status)):
            send_ok(response=FakeResponse(status))

    @pytest.mark.parametrize("status", [200, 202])
    def test_a_2xx_status_is_success(self, status):
        send_ok(response=FakeResponse(status))

    def test_a_timeout_says_so_in_words(self):
        with pytest.raises(MailError, match="did not answer in time"):
            send_ok(raises=requests.Timeout())

    def test_an_unreachable_server_says_so_in_words(self):
        with pytest.raises(MailError, match="could not reach"):
            send_ok(raises=requests.ConnectionError())

    def test_a_missing_key_is_a_refusal_not_a_crash(self, monkeypatch):
        monkeypatch.delenv("SENDGRID_API_KEY", raising=False)
        with pytest.raises(MailRefused, match="SENDGRID_API_KEY"):
            send("parent@example.test", "Hi", "Body", transport=Recorder())

    def test_the_key_is_read_from_the_environment_when_not_passed(self, monkeypatch):
        monkeypatch.setenv("SENDGRID_API_KEY", "SG.from-env")
        post = Recorder()
        send("parent@example.test", "Hi", "Body", transport=post)
        assert post.headers["Authorization"] == "Bearer SG.from-env"


class TestNothingSecretIsLogged:
    """The two things that must never reach a log line: the key, and the link."""

    def test_the_log_line_names_neither_recipient_nor_body_nor_key(self, caplog):
        link = "https://app.dinkydash.co/login/abc123secrettoken"
        with caplog.at_level(logging.DEBUG):
            send_ok(to="parent@example.test", subject="Your link",
                    text=f"Sign in: {link}")
        logged = " ".join(r.getMessage() for r in caplog.records)
        assert "abc123secrettoken" not in logged
        assert "parent@example.test" not in logged
        assert "SG.test" not in logged

    def test_a_failure_message_carries_no_key_and_no_link(self):
        link = "https://app.dinkydash.co/login/abc123secrettoken"
        with pytest.raises(MailError) as caught:
            send_ok(text=f"Sign in: {link}", raises=requests.ConnectionError(
                f"Failed to establish a connection to {link}"))
        assert "abc123secrettoken" not in str(caught.value)
        assert "SG.test" not in str(caught.value)
