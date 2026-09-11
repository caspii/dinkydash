"""What reaches Sentry, what must not (DIN-35), and the worker's check-in (DIN-54).

Real events, not a mocked SDK. `sentry_sdk` is initialised with exactly the
options the app uses, plus a transport that keeps every envelope in a list.
Then a request carrying every credential the app has is made to raise, and the
JSON of what *would* have been sent is searched for each one. That is the only
kind of test that means anything here: a scrubber asserted against a
hand-built dict would pass on the day the SDK started attaching something new.

The things it must not carry, and where each would ride:

* a **magic-link token** — the query string, and the Referer of the next page;
* a **screen token** — the URL's path;
* the **session cookie** and an **Authorization header**;
* the **request body** — a calendar URL somebody just pasted;
* the **caller's address**;
* a **calendar URL** inside an exception message, because `requests` puts the
  whole URL in every error it raises;
* a **family id** in a log line's arguments, because "Tick failed for family
  %s" is about our code and the `%s` is which family.

Skips when sentry-sdk is not installed, which is every self-hosted run.
"""

import json
import logging

import pytest

sentry_sdk = pytest.importorskip("sentry_sdk")
from sentry_sdk.transport import Transport  # noqa: E402

from dinkydash import sentry  # noqa: E402
from dinkydash.store import FileStore  # noqa: E402
from tests.conftest import client_for  # noqa: E402
from web import create_app  # noqa: E402

A_DSN = "https://public@example.invalid/1"
A_CALENDAR = "https://calendar.google.com/calendar/ical/x/private-3f9c1a7bDEADBEEF/basic.ics"
A_FAMILY = "b3f2c1a0-1234-4bcd-9ef0-123456789abc"


class Recorder(Transport):
    """A transport that keeps what it is given, so a test can read it."""

    def __init__(self):
        super().__init__()
        self.items = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            self.items.append((item.type, item.payload.json))

    def events(self):
        return [payload for kind, payload in self.items if kind == "event"]

    def check_ins(self):
        return [payload for kind, payload in self.items if kind == "check_in"]


@pytest.fixture
def recorder(monkeypatch):
    """The SDK, switched on the way the app switches it on, into a list."""
    monkeypatch.setenv("SENTRY_DSN", A_DSN)
    monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setattr(sentry, "_enabled", False)
    recorder = Recorder()
    assert sentry.init("test", transport=recorder) is True
    yield recorder
    sentry_sdk.flush()
    sentry_sdk.get_global_scope().set_client(None)


@pytest.fixture
def app(tmp_path):
    """A real app with two routes that raise, at the two URL shapes that carry
    a credential. Single mode: the scrubber does not know the mode, and this
    keeps the test off Postgres."""
    (tmp_path / "config.yaml").write_text(
        'family_name: "The Wilsons"\ntimezone: "Europe/Berlin"\n')
    app = create_app(FileStore(tmp_path / "config.yaml"))

    @app.route("/s/<token>", methods=["GET", "POST"])
    def a_screen(token):
        raise RuntimeError(f"could not fetch {A_CALENDAR}")

    @app.route("/login/link")
    def a_link():
        raise RuntimeError("no such token")

    return app


def sent(recorder):
    sentry_sdk.flush()
    (event,) = recorder.events()
    return event, json.dumps(event)


class TestARequestThatRaises:
    SECRETS = {
        "the screen token": "abcdEfghjkmn",
        "the login token in the query string": "QUERYSECRET",
        "the login token in the Referer": "REFSECRET",
        "the session cookie": "COOKIESECRET",
        "the Authorization header": "AUTHSECRET",
        "the calendar URL in the exception": "DEADBEEF",
        "the caller's address": "203.0.113.9",
        "the hostname": "app.example.test",
    }

    @pytest.fixture
    def event(self, app, recorder):
        """A GET, so the fake session cookie is not a CSRF failure first."""
        client = client_for(app)
        with pytest.raises(RuntimeError):
            client.get(
                "/s/abcdEfghjkmn?t=QUERYSECRET",
                headers={"Referer": "https://app.example.test/login/link?t=REFSECRET",
                         "Cookie": "session=COOKIESECRET",
                         "Authorization": "Bearer AUTHSECRET",
                         "X-Forwarded-For": "203.0.113.9",
                         "DO-Connecting-IP": "203.0.113.9"},
                base_url="https://app.example.test")
        return sent(recorder)

    @pytest.mark.parametrize("what", sorted(SECRETS))
    def test_nothing_that_identifies_the_request_leaves(self, event, what):
        _, body = event
        assert self.SECRETS[what] not in body, what

    def test_the_request_is_reduced_to_its_method(self, event):
        payload, _ = event
        assert payload["request"] == {"method": "GET"}

    def test_a_form_that_raises_leaves_its_body_and_its_csrf_token_behind(self, app, recorder):
        """A real signed session, the way a browser posts a settings form: the
        pasted calendar URL and the CSRF token are both in the request, and
        neither is in the report."""
        client = client_for(app)
        with pytest.raises(RuntimeError):
            client.post("/s/abcdEfghjkmn",
                        data={"calendar_url": A_CALENDAR.replace("DEADBEEF", "BODYSECRET")})
        with client.session_transaction() as stored:
            csrf = stored["csrf"]
        payload, body = sent(recorder)
        assert payload["request"] == {"method": "POST"}
        assert "BODYSECRET" not in body
        assert csrf not in body

    def test_the_exception_and_where_it_was_raised_do_leave(self, event):
        """The report still has to be worth reading."""
        payload, _ = event
        (exc,) = payload["exception"]["values"]
        assert exc["type"] == "RuntimeError"
        assert exc["value"] == "could not fetch [redacted]"
        assert exc["stacktrace"]["frames"][-1]["function"] == "a_screen"
        assert payload["transaction"] == "a_screen"
        assert payload["tags"]["component"] == "test"
        assert payload["environment"] == "production"

    def test_no_frame_carries_local_variables(self, event):
        """A config dict in a local is children's names; a URL in one is a password."""
        payload, _ = event
        for value in payload["exception"]["values"]:
            for frame in value["stacktrace"]["frames"]:
                assert "vars" not in frame

    def test_the_blocks_that_only_ever_hold_data_are_gone(self, event):
        payload, _ = event
        for block in ("user", "breadcrumbs", "extra"):
            assert block not in payload


class TestALogRecord:
    def test_error_reports_the_template_and_never_the_arguments(self, recorder):
        try:
            raise RuntimeError(f"their feed: {A_CALENDAR}")
        except RuntimeError:
            logging.getLogger("dinkydash.worker").exception(
                "Tick failed for family %s; leaving it for the next pass.", A_FAMILY)
        payload, body = sent(recorder)
        assert payload["logentry"] == {
            "message": "Tick failed for family %s; leaving it for the next pass."}
        assert payload["logger"] == "dinkydash.worker"
        assert payload["level"] == "error"
        assert A_FAMILY not in body
        assert "DEADBEEF" not in body

    def test_an_error_without_an_exception_is_still_a_report(self, recorder):
        logging.getLogger("dinkydash.mail").error("SendGrid said %s", "ARGUMENTSECRET")
        payload, body = sent(recorder)
        assert payload["logentry"] == {"message": "SendGrid said %s"}
        assert "ARGUMENTSECRET" not in body

    def test_a_warning_stays_in_the_log(self, recorder):
        """A failed feed is one family's problem, not the platform's."""
        logging.getLogger("dinkydash.calendars").warning("Feed %s failed: 404", "Dad's")
        sentry_sdk.flush()
        assert recorder.events() == []


class TestTheTextScrubber:
    @pytest.mark.parametrize("text, expected", [
        (f"404 for url: {A_CALENDAR}", "404 for url: [redacted]"),
        ("webcal://p12-caldav.icloud.com/published/2/abc", "[redacted]"),
        ("postgresql://user:hunter2@db.example/dinkydash", "[redacted]"),
        ("GET /login/link?t=abc123&x=1", "GET /login/link?t=[redacted]&x=1"),
        ("GET /s/abcdEfghjkmn/manifest.webmanifest", "GET /s/[redacted]/manifest.webmanifest"),
        ("sent to parent@example.com today", "sent to [redacted] today"),
        (f"family {A_FAMILY} is gone", "family [redacted] is gone"),
        ("Could not mark expired trials", "Could not mark expired trials"),
    ])
    def test_it_takes_out_what_names_a_family_or_opens_a_door(self, text, expected):
        assert sentry.scrub_text(text) == expected

    def test_it_leaves_anything_that_is_not_text_alone(self):
        assert sentry.scrub_text(None) is None
        assert sentry.scrub_text(42) == 42


class TestTheCheckIn:
    """The worker's pulse: a slug, a status and a duration (DIN-54)."""

    def test_it_is_a_slug_a_status_a_duration_and_the_schedule(self, recorder):
        sentry.check_in(300, 12.5)
        sentry_sdk.flush()
        (item,) = recorder.check_ins()
        assert item["monitor_slug"] == "worker-pass"
        assert item["status"] == "ok"
        assert item["duration"] == 12.5
        assert item["environment"] == "production"
        assert item["monitor_config"] == {
            "schedule": {"type": "interval", "value": 5, "unit": "minute"},
            "checkin_margin": 10,
            "failure_issue_threshold": 1,
            "recovery_threshold": 1,
            "timezone": "UTC",
        }

    def test_it_carries_nothing_about_anybody(self, recorder):
        sentry.check_in(300, 1.0)
        sentry_sdk.flush()
        (item,) = recorder.check_ins()
        assert set(item) <= {
            "type", "monitor_slug", "check_in_id", "status", "duration",
            "environment", "release", "monitor_config", "event_id", "timestamp",
            "contexts", "server_name", "sdk", "platform",
        }

    def test_the_scrubber_lets_it_through_whole(self, recorder):
        """`before_send` sees check-ins too, and the allow-list would strip the slug."""
        sentry.check_in(300, 1.0)
        sentry_sdk.flush()
        assert recorder.check_ins()[0]["monitor_slug"] == "worker-pass"

    def test_it_is_labelled_with_the_environment_and_release(self, recorder, monkeypatch):
        monkeypatch.setenv("SENTRY_ENVIRONMENT", "drill")
        monkeypatch.setenv("GIT_SHA", "abc1234")
        monkeypatch.setattr(sentry, "_enabled", False)
        sentry_sdk.get_global_scope().set_client(None)
        recorder = Recorder()
        sentry.init("worker", transport=recorder)
        sentry.check_in(300, 1.0)
        sentry_sdk.flush()
        (item,) = recorder.check_ins()
        assert item["environment"] == "drill"
        assert item["release"] == "abc1234"

    @pytest.mark.parametrize("seconds, minutes, margin", [
        (300, 5, 10),   # the default: missed after the third silent pass
        (900, 15, 30),
        (60, 1, 2),
        (5, 1, 2),      # a local drill; Sentry counts in whole minutes
    ])
    def test_the_monitor_follows_the_workers_interval(self, seconds, minutes, margin):
        config = sentry.monitor_config(seconds)
        assert config["schedule"] == {"type": "interval", "value": minutes, "unit": "minute"}
        assert config["checkin_margin"] == margin


class TestWithoutADsn:
    """Every self-hosted board, and every test that is not this file."""

    @pytest.fixture(autouse=True)
    def no_dsn(self, monkeypatch):
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        monkeypatch.setattr(sentry, "_enabled", False)

    def test_init_does_nothing_and_says_so(self):
        assert sentry.init("web") is False
        assert not sentry_sdk.is_initialized()

    def test_an_empty_dsn_is_no_dsn(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", "  ")
        assert sentry.init("web") is False

    def test_a_check_in_is_a_no_op(self):
        assert sentry.check_in(300, 1.0) is None


class TestTheOptions:
    def test_everything_that_would_carry_data_is_off(self):
        options = sentry.options(A_DSN)
        assert options["send_default_pii"] is False
        assert options["include_local_variables"] is False
        assert options["max_request_body_size"] == "never"
        assert options["max_breadcrumbs"] == 0
        assert options["attach_stacktrace"] is False
        assert options["auto_session_tracking"] is False
        assert options["enable_logs"] is False
        assert options["enable_metrics"] is False
        assert options.get("traces_sample_rate") is None
        assert options["before_send"] is sentry.scrub

    def test_only_the_two_named_integrations_are_on(self):
        """The auto-enabled set includes one that instruments the Anthropic
        client, which would see the prompt — the whole of a family's day."""
        options = sentry.options(A_DSN)
        assert options["auto_enabling_integrations"] is False
        assert {type(i).__name__ for i in options["integrations"]} == {
            "FlaskIntegration", "LoggingIntegration"}

    def test_the_environment_defaults_to_production(self):
        assert sentry.options(A_DSN)["environment"] == "production"
        assert sentry.options(A_DSN, environment="drill")["environment"] == "drill"
