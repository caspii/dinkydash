"""Cloud signup, login and logout routes.

Login requests return the same page for known, new, limited and failed sends.
The access-log filter removes credentials from request messages; the full
logging and authentication requirements are in the root CLAUDE.md.

GET /login/link consumes the token, so mail scanners that follow links can
invalidate them before the recipient clicks.
"""

import logging
import re

from flask import (Blueprint, current_app, redirect, render_template, request,
                   url_for)

from dinkydash import accounts, mail
from web import ratelimit, session as user_session
from web.urls import absolute_url

log = logging.getLogger(__name__)

bp = Blueprint("auth", __name__)

A_TOKEN = re.compile(r"([?&]t=)[^&\s\"']+")
REDACTED = r"\1[redacted]"

# Validation belongs to the route. A typo still reveals a recoverable credential;
# encoded separators/letters can also reach these paths through a server's decoder.
SCREEN_PREFIX = r"((?:/|%2f)(?:s|%73|%53)(?:/|%2f))"
A_SCREEN = re.compile(SCREEN_PREFIX + r"\S*", re.IGNORECASE)
A_SCREEN_TARGET = re.compile(SCREEN_PREFIX + r".*", re.IGNORECASE | re.DOTALL)
SCREEN_REDACTED = r"\1[redacted]"

SAME_ANSWER = ("A link is on its way. It works once, and for fifteen minutes. "
               "If you have not got a board yet, the link starts one.")

DEAD_LINK = ("That link no longer works — it has either been used already or "
             "expired. Ask for a new one.")

MOST_PER_IP = 20
PER_SECONDS = 3600

SUBJECT = "Your DinkyDash sign-in link"
WELCOME_SUBJECT = "Start your DinkyDash board"

_warned_about_anonymous = False


REQUEST_LOGGERS = ("werkzeug", "gunicorn.access")


class NoTokens(logging.Filter):
    """Redact magic-link and screen tokens from both server request loggers."""

    def filter(self, record):
        # Redact while the server still gives us the target separately: decoded
        # spaces and quotes inside a credential are not log-field separators.
        if record.name == "gunicorn.access" and isinstance(record.args, dict):
            path = record.args.get("U")
            if isinstance(path, str):
                record.args["U"] = A_SCREEN_TARGET.sub(SCREEN_REDACTED, path)
        elif (record.name == "werkzeug" and isinstance(record.args, tuple)
              and record.args and isinstance(record.args[0], str)):
            request_line = record.args[0]
            target, separator, protocol = request_line.rpartition(" HTTP/")
            if not separator:
                target, protocol = request_line, ""
            redacted = A_SCREEN_TARGET.sub(SCREEN_REDACTED, target)
            record.args = (redacted + separator + protocol, *record.args[1:])

        message = record.getMessage()
        redacted = A_SCREEN.sub(SCREEN_REDACTED, A_TOKEN.sub(REDACTED, message))
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def quieten_the_request_log():
    """Attach the filter above to both request loggers, once each."""
    for name in REQUEST_LOGGERS:
        logger = logging.getLogger(name)
        if not any(isinstance(f, NoTokens) for f in logger.filters):
            logger.addFilter(NoTokens())


@bp.record_once
def _quieten(state):
    quieten_the_request_log()


@bp.record_once
def _build_the_limiter(state):
    """Give each app its own per-caller limiter."""
    state.app.config.setdefault(
        "LOGIN_LIMITER", ratelimit.Limiter(MOST_PER_IP, PER_SECONDS))


def _pool():
    pool = current_app.config.get("POOL")
    if pool is None:
        raise RuntimeError("Cloud mode needs a database to sign anybody in.")
    return pool


@bp.route("/login", methods=["GET", "POST"])
def login():
    if user_session.signed_in():
        return redirect(url_for("settings.home"))
    if request.method == "GET":
        return render_template("auth/login.html")

    address = request.form.get("email", "")
    if "@" not in address or len(address.strip()) > accounts.LONGEST_EMAIL:
        return render_template("auth/login.html", email=address,
                               problem="That does not look like an email address.")

    _send_a_link(address)
    return render_template("auth/sent.html", message=SAME_ANSWER)


def _send_a_link(address):
    """Send a login or signup link if allowed; return the same result in every case.

    Logs may contain the caller's IP and recipient's domain, but never the full
    recipient address or a credential.
    """
    caller = ratelimit.client_ip(request)
    _warn_once_if_anonymous(caller)

    limiter = current_app.config["LOGIN_LIMITER"]
    if not limiter.allow(caller):
        log.warning("Sign-in requests from %s are over the limit "
                    "(%s per %s minutes, in this process).",
                    caller or "an unknown caller",
                    limiter.most, round(limiter.per / 60))
        return

    pool = _pool()
    user = accounts.user_for(pool, address)
    if user is None:
        kind, token = "sign-up", accounts.issue_signup_link(pool, address)
    else:
        kind, token = "sign-in", accounts.issue_link(pool, user[0])

    if token is None:
        log.warning("No %s link minted for a %s address from %s: "
                    "%s live links already.", kind, _domain(address),
                    caller or "an unknown caller", accounts.MOST_LIVE_LINKS)
        return

    link = _link_for(token)
    new_family = kind == "sign-up"
    try:
        mail.send(accounts.normalise(address),
                  WELCOME_SUBJECT if new_family else SUBJECT,
                  _text(link, new_family), html=_html(link, new_family))
    except mail.MailError as exc:
        log.warning("A %s link did not go out: %s", kind, exc)
    else:
        log.info("Sent a %s link to a %s address.", kind, _domain(address))


def _domain(address):
    """The part of an address that is not a person. `@example.com`, or `@?`."""
    _, _, domain = accounts.normalise(address).partition("@")
    return f"@{domain}" if domain else "@?"


def _warn_once_if_anonymous(caller):
    """Warn once per process if requests lack a usable rate-limit address."""
    global _warned_about_anonymous
    if caller or _warned_about_anonymous:
        return
    _warned_about_anonymous = True
    log.warning(
        "No caller address on this request: none of %s was set and the socket "
        "address is not public. The per-caller sign-in limit is not firing; "
        "the per-address one in Postgres still is.",
        ", ".join(ratelimit.CALLER_HEADERS))


def _link_for(token):
    """Build a credential URL using the shared app-origin policy."""
    return absolute_url(url_for("auth.landing", t=token))


@bp.route("/login/link")
def landing():
    """Spend the token and start the session.

    Nothing here distinguishes expired from spent from never-issued, because
    `consume_link` does not either — one answer, one page.
    """
    user = accounts.consume_link(_pool(), request.args.get("t"))
    if user is None:
        return render_template("auth/login.html", problem=DEAD_LINK)
    user_session.sign_in(user[0], user[1])
    return redirect(url_for("settings.home"))


@bp.route("/logout", methods=["POST"])
def logout():
    user_session.sign_out()
    return redirect(url_for("auth.login"))


def _text(link, new_family=False):
    """The email. Two openings, because one of them is somebody's first.

    **The difference is safe.** What the page says back is identical either
    way; this only differs in a mailbox, and whoever opens that mailbox knows
    whether they already had a board. Telling a new parent that the link starts
    one is the difference between finishing the sign-up and abandoning it.
    """
    if new_family:
        return f"""\
Welcome to DinkyDash.

Open this link and your board is ready — people, chores and countdowns are
already filled in with an invented family for you to replace:

{link}

The link works once, and for fifteen minutes.

If you did not ask for this, you can ignore it. Nothing has been created, and
the link stops working on its own.

- DinkyDash
https://dinkydash.co
"""
    return f"""\
Here is your link to sign in to DinkyDash:

{link}

The link works once, and for fifteen minutes.

If you did not ask for this, you can ignore it. Nobody can sign in without
the link, and it stops working on its own.

- DinkyDash
https://dinkydash.co
"""


def _html(link, new_family=False):
    """Render an email without remote images, tracking pixels or third-party CSS."""
    if new_family:
        return f"""\
<p>Welcome to DinkyDash.</p>
<p>Open this link and your board is ready — people, chores and countdowns are
already filled in with an invented family for you to replace:</p>
<p><a href="{link}">Start my board</a></p>
<p>The link works once, and for fifteen minutes.</p>
<p>If you did not ask for this, you can ignore it. Nothing has been created,
and the link stops working on its own.</p>
<p>— DinkyDash</p>
"""
    return f"""\
<p>Here is your link to sign in to DinkyDash:</p>
<p><a href="{link}">Sign in to DinkyDash</a></p>
<p>The link works once, and for fifteen minutes.</p>
<p>If you did not ask for this, you can ignore it. Nobody can sign in without
the link, and it stops working on its own.</p>
<p>— DinkyDash</p>
"""
