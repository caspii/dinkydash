"""What the session cookie carries, and what it has to prove.

Two things live in that cookie and both are authentication:

    who is signed in     `user_id` and `family_id`, set by a magic link
    a CSRF token         proof that a form that writes came from a page we sent

Flask signs the cookie, it does not encrypt it. So what goes in is what we are
happy for the holder to read: two ids, and no email address. In cloud mode the
signature *is* the login, which is why `create_app` refuses to start on the
self-hosted fallback key.

**The cookie flags are stated, not left to their defaults.** `HttpOnly` is
Flask's default and `SameSite` is not; a flag nobody writes down is a flag
nobody notices when a default moves under it.

**`Secure` is the one thing here that mode gates.** A Raspberry Pi serves plain
HTTP on a home network, and a `Secure` cookie is never sent over it — the
settings UI would lose every flash message, and every CSRF token with them.
Cloud mode is HTTPS only and sets it.

**CSRF is on in both modes**, and that is deliberate. Self-hosted has no
accounts, but it does sit on a home network with a guessable address: a page
in another tab can POST to `http://raspberrypi.local:5123/settings/...` and
edit somebody's board. It costs a hidden field, and running the same code in
both modes is what stops it being a check nobody exercises.
"""

import hmac
import secrets
from datetime import timedelta

from flask import abort, current_app, redirect, request, session, url_for

# What the session holds when somebody is signed in.
USER_ID = "user_id"
FAMILY_ID = "family_id"

# The CSRF token: where it is kept, and what the form calls it.
CSRF_KEY = "csrf"
CSRF_FIELD = "csrf_token"

# Everything that must not change anything. RFC 9110's safe methods.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# How long a sign-in lasts. A board on a wall is furniture and its owner should
# not be signed out of the settings for it every fortnight.
SESSION_LIFETIME = timedelta(days=30)


def configure(app):
    """Cookie flags, the CSRF check, and `csrf_token()` for the templates."""
    from . import CLOUD

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=app.config["MODE"] == CLOUD,
        PERMANENT_SESSION_LIFETIME=SESSION_LIFETIME,
    )
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.before_request(check_csrf)


# -- who is signed in -------------------------------------------------------

def sign_in(user_id, family_id):
    """Start a session for that user, throwing away whatever was there.

    `session.clear()` first is the session-fixation defence: an attacker who
    got a victim to carry their cookie must not still be holding it after the
    victim signs in.
    """
    session.clear()
    session.permanent = True
    session[USER_ID] = user_id
    session[FAMILY_ID] = str(family_id)


def sign_out():
    session.clear()


def signed_in():
    return bool(session.get(USER_ID))


def current_user_id():
    """Who is signed in, or None. The person, as opposed to the family.

    Almost everything is scoped to the family and reads `web/family.py`
    instead. This is for the two things that are about the *person*: showing
    somebody their own address, and confirming that they typed it back before
    deleting the account.
    """
    return session.get(USER_ID)


def guard():
    """Cloud mode: no session, no family. Returns a redirect, or None.

    Authentication and authorisation are the same act here, because the session
    is not merely permission to see a board — it *is* which board. The family
    on it is the only thing `web/family.py` will build a store from (DIN-39).

    No `next` parameter. A redirect target taken from a URL is an open redirect
    waiting to be written wrongly, and everything behind this gate is one page
    away from `/settings/` anyway.
    """
    from . import CLOUD

    if current_app.config["MODE"] != CLOUD or signed_in():
        return None
    return redirect(url_for("auth.login"))


# -- proving a form came from us --------------------------------------------

def csrf_token():
    """The token for this session, minted on first use.

    A template global, so a form gets it by calling it — there is no route that
    has to remember to pass it, and therefore no form that quietly loses it.
    """
    token = session.get(CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_KEY] = token
    return token


def check_csrf():
    """Refuse any write that did not carry this session's token.

    Registered as an app-wide `before_request` rather than per blueprint, so a
    route added later is covered by having been added. `compare_digest` because
    this is the one comparison in the login path where both sides are known to
    the attacker's browser and a timing difference would be real.

    **There is no switch to turn this off**, and that is on purpose: a
    `CSRF_ENABLED` flag is a flag somebody eventually sets wrongly in
    production, and it would leave the accepting path untested everywhere else.
    The test client in `tests/conftest.py` carries the token the way a browser
    does, so every form POST in the suite goes through this function rather
    than around it. A route that genuinely cannot carry one — a Stripe webhook
    is the coming example — is exempted here, by path, in the open.
    """
    if request.method in SAFE_METHODS:
        return None
    held = session.get(CSRF_KEY) or ""
    sent = request.form.get(CSRF_FIELD) or request.headers.get("X-CSRF-Token") or ""
    # Compared as bytes, and not for tidiness: `compare_digest` raises
    # `TypeError` on a `str` with a non-ASCII character in it, and the string
    # being compared came out of a form somebody else filled in. A 500 where a
    # 400 belongs is a bug anyone could trigger with one emoji.
    if not held or not hmac.compare_digest(sent.encode("utf-8"), held.encode("utf-8")):
        # 400 rather than 403: the usual cause is a page left open until the
        # session behind it went, and the fix is to reload it.
        abort(400, "That page was out of date. Go back, reload it and try again.")
    return None
