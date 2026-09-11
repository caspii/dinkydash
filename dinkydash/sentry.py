"""What leaves the machine when something breaks — and what never does.

Cloud mode only. `init` is called from `wsgi.py` for the web service and from
`worker.main` for the tick loop, and it reads `SENTRY_DSN`. With no DSN it
returns False and nothing is imported, initialised or sent — which is every
self-hosted dashboard and every test run. `sentry-sdk` lives in
`requirements-cloud.txt` for the same reason psycopg does: a Pi never installs it.

Two kinds of thing go out:

* **An error report**, for an unhandled exception in a web request, or a log
  record at ERROR anywhere — the worker's "Tick failed for family", the
  settings page's "Generation failed". WARNING-level feed failures stay in
  the log: they are one family's problem, not the platform's.
* **One check-in after every completed worker pass** (DIN-54). Sentry expects
  the next within `DINKYDASH_WORKER_INTERVAL`, plus twice that as grace, and
  a missed one is the alert. A check-in is a slug, a status and a duration —
  no family, no calendar, no text. `worker.run_pass` is the only caller,
  because it is the only place that knows a pass finished.

**What an error report may hold is decided here, once, in `scrub`**, and it is
narrow on purpose: the exception and where in *our* code it was raised, the
log line's template, the request's method, the release, the component. Not
the URL or the query string — a magic link rides in `?t=` and a screen token
in `/s/<token>` — not the Referer, which carries the same, not the headers,
the body or the cookies; not local variables (a config holds children's names
and a calendar URL is a password); not breadcrumbs (an outgoing-request
breadcrumb is the calendar URL again); and not the log line's *arguments*,
which is where a family id, a label or an address would ride. The SDK's own
PII switch is off as well, and it is not trusted alone: with it off, the SDK
was observed to keep the URL, the query string and the Referer.
`tests/test_sentry.py` captures real events through an in-process transport
and asserts each absence.
"""

import logging
import os
import re

log = logging.getLogger(__name__)

# The worker's cron monitor. One slug, one monitor: Sentry creates it from the
# `monitor_config` on the first check-in and updates it from every later one,
# so there is nothing to set up by hand and the schedule follows
# DINKYDASH_WORKER_INTERVAL.
MONITOR_SLUG = "worker-pass"

DEFAULT_ENVIRONMENT = "production"

REDACTED = "[redacted]"

# What an error report keeps at the top level. An allow-list rather than a
# deny-list, so that a key the SDK starts attaching in some later version is
# dropped until somebody decides it is safe. `request` is handled below.
KEEP = frozenset({
    "event_id", "timestamp", "platform", "level", "logger", "logentry",
    "exception", "message", "release", "environment", "server_name", "sdk",
    "contexts", "modules", "tags", "transaction", "transaction_info",
    "fingerprint", "type",
})

# Anything in free text that could name a family or open a door. Any URL
# scheme, because a calendar address is `https://` or `webcal://` and a
# connection string is `postgresql://`; a magic-link token; a screen token;
# an email address; a family id, which is a UUID.
_A_URL = re.compile(r"[a-z][a-z0-9+.-]*://\S+", re.IGNORECASE)
_A_TOKEN = re.compile(r"([?&]t=)[^&\s\"']+")
_A_SCREEN = re.compile(r"(/s/)[^/\s\"']+")
_AN_ADDRESS = re.compile(r"[^\s@\"'<>/]+@[^\s@\"'<>/]+")
_AN_ID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)

_enabled = False


def options(dsn, environment=None, release=None):
    """The SDK's settings, as one dict. Pure, so a test can read them.

    Everything that would carry data is off: PII, local variables, request
    bodies, breadcrumbs, tracing, sessions, the SDK's own logs and metrics —
    and its auto-enabled integrations, one of which instruments the Anthropic
    client and would see the prompt. Two integrations, named: Flask, for the
    unhandled exception in a request, and logging, for `log.exception`.
    """
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    return dict(
        dsn=dsn,
        environment=environment or DEFAULT_ENVIRONMENT,
        release=release or None,
        send_default_pii=False,
        include_local_variables=False,
        max_breadcrumbs=0,
        max_request_body_size="never",
        attach_stacktrace=False,
        auto_session_tracking=False,
        auto_enabling_integrations=False,
        integrations=[
            FlaskIntegration(),
            # `level=None`: no breadcrumbs from the log at all. ERROR and above
            # become a report; WARNING stays where it was written.
            LoggingIntegration(level=None, event_level=logging.ERROR),
        ],
        before_send=scrub,
        enable_logs=False,
        enable_metrics=False,
    )


def init(component, **overrides):
    """Start reporting if `SENTRY_DSN` is set. Returns whether it did.

    `component` — "web" or "worker" — is a tag on every report, because the
    same exception means different things in a request and in a pass.
    `overrides` are for the tests, which pass a transport that keeps the
    envelopes in a list instead of sending them.
    """
    global _enabled
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        log.info("SENTRY_DSN is not set; errors stay in the log.")
        return False

    import sentry_sdk

    settings = options(dsn, environment=os.environ.get("SENTRY_ENVIRONMENT"),
                       release=os.environ.get("GIT_SHA"))
    sentry_sdk.init(**{**settings, **overrides})
    sentry_sdk.get_global_scope().set_tag("component", component)
    _enabled = True
    log.info("Reporting errors to Sentry as %s.", component)
    return True


def check_in(interval_seconds, duration_seconds):
    """Tell Sentry a worker pass finished, and how long it took.

    A no-op without a DSN. The monitor's schedule and grace ride along on
    every check-in, so the monitor exists after the first one and follows a
    changed interval after the next. Returns the check-in id, or None.
    """
    if not _enabled:
        return None

    from sentry_sdk.crons import capture_checkin

    return capture_checkin(monitor_slug=MONITOR_SLUG, status="ok",
                           duration=float(duration_seconds),
                           monitor_config=monitor_config(interval_seconds))


def monitor_config(interval_seconds):
    """The monitor, derived from the worker's interval and nothing else.

    Sentry counts in whole minutes. A five-minute interval is expected every
    five minutes with ten minutes' grace, so the issue opens when the third
    pass in a row has failed to check in — the allowance the in-house design
    had. The grace also has to cover a pass that runs long: the check-in is
    sent when a pass *ends*, so a pass longer than two intervals reads as
    missed, which by then it fairly is.
    """
    minutes = max(1, round(interval_seconds / 60))
    return {
        "schedule": {"type": "interval", "value": minutes, "unit": "minute"},
        "checkin_margin": 2 * minutes,
        "failure_issue_threshold": 1,
        "recovery_threshold": 1,
        "timezone": "UTC",
    }


def scrub(event, hint=None):
    """`before_send`: the whole report, reduced to what may leave.

    A check-in passes through untouched — it is a slug, a status and a
    duration, and the allow-list below would strip the slug.
    """
    if event.get("type") == "check_in":
        return event

    kept = {key: value for key, value in event.items() if key in KEEP}

    # The method and nothing else. The URL holds a screen token, the query
    # string a login token, the Referer either, the headers the host, and the
    # body whatever somebody just typed into the settings.
    method = (event.get("request") or {}).get("method")
    if method:
        kept["request"] = {"method": method}

    # The template, never the arguments: "Tick failed for family %s" is about
    # our code, and the %s is which family.
    if "logentry" in kept:
        entry = kept["logentry"] or {}
        kept["logentry"] = {"message": scrub_text(entry.get("message")
                                                  or entry.get("formatted") or "")}
    if "message" in kept:
        if isinstance(kept["message"], str):
            kept["message"] = scrub_text(kept["message"])
        else:
            del kept["message"]

    # Exception text is written by whoever raised, including libraries that
    # quote the URL they failed on. The frames are our own source, which is
    # public; their local variables are not, and are off at the SDK too.
    for value in (kept.get("exception") or {}).get("values") or []:
        if "value" in value:
            value["value"] = scrub_text(value["value"])
        for frame in (value.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)

    return kept


def scrub_text(text):
    """Free text with every URL, token, address and family id taken out."""
    if not isinstance(text, str):
        return text
    text = _A_URL.sub(REDACTED, text)
    text = _A_TOKEN.sub(r"\g<1>" + REDACTED, text)
    text = _A_SCREEN.sub(r"\g<1>" + REDACTED, text)
    text = _AN_ADDRESS.sub(REDACTED, text)
    return _AN_ID.sub(REDACTED, text)
