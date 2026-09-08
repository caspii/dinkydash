"""One email in, one link out, one session. Cloud mode only.

    GET  /login          ask for an email address
    POST /login          send a link, and always say the same thing
    GET  /login/link     spend the token, start the session, go to the settings
    POST /logout         throw the session away

Registered only when `DINKYDASH_MODE=cloud`. Self-hosted has no accounts by
design — one family on their own network, and the same trust model as the
config file the settings UI writes — so in single mode these routes do not
exist rather than existing and refusing.

**Answer identically whether or not the address has an account.** "No account
with that address" is an enumeration oracle against a product whose users are
families, and it would be one whichever way it was worded. So there is one
message, and it is sent for an unknown address, a known one, a rate-limited one
and a failed send alike.

**A login link in a log is a login in a log**, and the app runs `gunicorn
--access-logfile -`, which writes every request line to the platform's log.
Three things keep the token out of it, and none of them is decoration:

* **the token rides in the query string, not the path.** Gunicorn's `%(U)s` is
  the path *without* one, so the access log format in `.do/app.yaml` is built
  from it. `tests/test_auth.py` fails if that line grows a `%(r)s` or a
  `%(q)s` back;
* **`NoTokens` below scrubs `?t=` out of both request logs anyway**, because
  the development server has no format to configure and `deploy_on_push` does
  not apply the committed spec;
* **`Referrer-Policy: no-referrer` on every response** (`web/__init__.py`),
  which stops a browser handing the whole URL to the next site.

What none of that reaches is DigitalOcean's own edge, whose logs we do not
format. So the token's last defence is the one it was always going to be: it
works once, and for fifteen minutes.

**Known and not closed: a mail scanner can burn a link.** A GET spends the
token, so a corporate mail filter that follows links before the person does
leaves them with a dead one. Single use is worth more than that is worth
avoiding — two clicks must not both sign in — and the family mail providers
this launches on do not do it. If it ever bites, the fix is a confirm button
that POSTs the token, at the cost of a click for everybody.
"""

import logging
import re

from flask import (Blueprint, current_app, redirect, render_template, request,
                   url_for)

from dinkydash import accounts, mail
from web import ratelimit, session as user_session

log = logging.getLogger(__name__)

bp = Blueprint("auth", __name__)

# A `?t=` in anything being logged, and what to put there instead.
A_TOKEN = re.compile(r"([?&]t=)[^&\s\"']+")
REDACTED = r"\1[redacted]"

# The one answer a login request ever gets.
SAME_ANSWER = ("If that address has an account, a link is on its way. "
               "It works once, and for fifteen minutes.")

# What a token that is expired, spent or invented all get.
DEAD_LINK = ("That link no longer works — it has either been used already or "
             "expired. Ask for a new one.")

# Per client IP, per hour, in this process. Generous enough that a family
# behind one address can all get in; small enough that a script cannot spend
# our SendGrid quota. The per-address half of the limit is in Postgres, in
# `accounts.issue_link`, where it holds across instances.
MOST_PER_IP = 20
PER_SECONDS = 3600

SUBJECT = "Your DinkyDash sign-in link"


# The two loggers that write a request line: Flask's development server, and
# gunicorn's access log. Both get the filter below.
REQUEST_LOGGERS = ("werkzeug", "gunicorn.access")


class NoTokens(logging.Filter):
    """Take the token out of anything a server writes about a request.

    Belt to the access log format's braces, and it exists because both halves
    of that format can be missing:

    * **Flask's own development server logs the whole request line**, and no
      `--access-logformat` reaches it. A developer running cloud mode locally
      watches sign-in links scroll past their terminal. Observed, not imagined,
      which is how this came to be written.
    * **`deploy_on_push` does not apply the committed app spec** — it rebuilds
      the components that already exist (doc/operations.md). So a commit that
      changes the format in `.do/app.yaml` and is merged without somebody
      running `doctl apps update` leaves production on gunicorn's default
      `%(r)s`, which is the full request line. This filter is what makes that
      window safe rather than silent.

    A filter rather than a formatter, because it has to reach the message
    whatever handler eventually prints it, and gunicorn's message is only
    assembled when the record is formatted.
    """

    def filter(self, record):
        message = record.getMessage()
        if "t=" in message:
            record.msg = A_TOKEN.sub(REDACTED, message)
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
    """One limiter per app, rather than one per process.

    A module-level counter would be shared by every app built in a process,
    which is fine in production and wrong in a test suite that builds several.
    """
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
    if "@" not in address:
        # The one thing worth saying back, and it says nothing about accounts:
        # this is about what was typed, not about who exists.
        return render_template("auth/login.html", email=address,
                               problem="That does not look like an email address.")

    _send_a_link(address)
    return render_template("auth/sent.html", message=SAME_ANSWER)


def _send_a_link(address):
    """Do whatever there is to do, and tell the caller nothing about it.

    Every branch below returns the same None, and the page above is the same
    page, because each of them is something an attacker would otherwise learn:
    whether the address exists, whether it has asked recently, and whether our
    mail provider is up.

    **Known and not closed: this takes longer when the address exists**, by
    roughly the time SendGrid takes to answer. Somebody timing the two could
    tell them apart. Closing it means sending off the request thread, which is
    a background worker's job rather than a login route's, and the enumeration
    it would buy is a list of addresses somebody already had.
    """
    limiter = current_app.config["LOGIN_LIMITER"]
    if not limiter.allow(ratelimit.client_ip(request)):
        # The caller's address, never the one they typed. Which addresses were
        # asked about is the thing this endpoint exists not to say.
        log.warning("A sign-in request was rate-limited by caller address.")
        return

    pool = _pool()
    user = accounts.user_for(pool, address)
    if user is None:
        return

    token = accounts.issue_link(pool, user[0])
    if token is None:
        return

    link = _link_for(token)
    try:
        mail.send(accounts.normalise(address), SUBJECT,
                  _text(link), html=_html(link))
    except mail.MailError as exc:
        # `mail` messages carry no address, no key and no body, and this one
        # must not add the link back. A failed send is a failed login, and the
        # person will ask again.
        log.warning("A sign-in link did not go out: %s", exc)


def _link_for(token):
    """The sign-in URL, built from configuration rather than from the request.

    Two things here are deliberate and neither is cosmetic.

    **The host is `APP_HOST`, not `request.host`.** `request.host` is the
    `Host` header, which the caller writes. Building the link from it would let
    somebody POST this form with a victim's address and a `Host` of their own,
    and have a working token mailed to the victim pointing at their server.
    `wsgi.py` already refuses to route an unknown host to this app, so the
    attack does not land today — but a bearer credential should not rely on a
    rule in a different file, and this app is also runnable on its own.

    **The scheme is always https.** App Platform terminates TLS, so the request
    that reaches Flask is plain HTTP and a link built from it would put the
    credential on the wire in clear.

    Falls back to `request.host` when `APP_HOST` is unset, which is local
    development and the tests. Cloud mode sets it in `.do/app.yaml`.
    """
    host = current_app.config.get("APP_HOST") or request.host
    return f"https://{host}{url_for('auth.landing', t=token)}"


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


def _text(link):
    return f"""\
Here is your link to sign in to DinkyDash:

{link}

It works once, and for fifteen minutes.

If you did not ask for this, you can ignore it. Nobody can sign in without
the link, and it stops working on its own.

- DinkyDash
https://dinkydash.co
"""


def _html(link):
    """Deliberately plain. No images, no tracking pixel, no third-party CSS.

    A login email that loads anything from anywhere else hands the fact of the
    login, and often the URL, to whoever serves it.
    """
    return f"""\
<p>Here is your link to sign in to DinkyDash:</p>
<p><a href="{link}">Sign in to DinkyDash</a></p>
<p>It works once, and for fifteen minutes.</p>
<p>If you did not ask for this, you can ignore it. Nobody can sign in without
the link, and it stops working on its own.</p>
<p>— DinkyDash</p>
"""
