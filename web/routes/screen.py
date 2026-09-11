"""The dashboard on a wall: one unguessable URL, no session. Cloud mode only.

    GET /s/<token>                        the dashboard
    GET /s/<token>/manifest.webmanifest   so a tablet can save it to a home screen

Registered only when `DINKYDASH_MODE=cloud`, like `auth.py` — a self-hosted
dashboard is at `/` and has no token, so here this is a 404 rather than a route
that exists and refuses.

**Why the dashboard is not simply behind the login.** A kitchen tablet, a television
and a Raspberry Pi in kiosk mode have no way to sign in and nobody to do it: the
whole point of the product is a screen somebody stops thinking about. So the
credential moves into the URL, where a browser can hold it for months without a
person (PLAN.md, Screen URLs).

**That makes the token a bearer credential, and a long-lived one.** It has none
of a magic link's defences — no expiry, no single use — so the ones it does have
have to be kept working:

* **it reaches nothing but a dashboard.** No settings, no email address, nothing
  that writes. Both routes here are GETs, and both read through a
  `PostgresStore` scoped to the one family the token named;
* **rotation is the revocation**, on the settings page, and it is the whole of
  it;
* **it must not end up written down.** `Referrer-Policy: no-referrer` is on
  every response already (DIN-32), the page makes no third-party request, and
  every response here carries `X-Robots-Tag` and `Cache-Control: no-store`;
* **the path is in the access log, and that had to be dealt with.** Gunicorn's
  format is built from `%(U)s` — the path *without* the query string — which is
  exactly what keeps a magic link's `?t=` out of it. A token in the path is on
  the other side of that trade, and a panel reloading every five minutes writes
  it thousands of times. `auth.NoTokens` scrubs `/s/<token>` for the same reason
  it scrubs `?t=`, and `tests/test_screen.py` fails if it stops.

**The rate limit counts misses, not requests.** A valid token belongs to a
screen that will ask for this page every few minutes for years, and refusing it
is an outage on somebody's kitchen wall. A wrong one is a typo or a scan.
Counting only the misses lets the limiter be strict without ever being in a real
screen's way — and enumeration was never the real risk, since guessing 59 bits
at any rate at all is hopeless. What it actually buys is that nobody can make us
do the looking.
"""

import logging

from flask import (Blueprint, current_app, make_response, render_template,
                   request, url_for)

from dinkydash.lifecycle import access_for
from web import ratelimit
from web.family import store_for_token
from web.routes.board import manifest_for, render_board

log = logging.getLogger(__name__)

bp = Blueprint("screen", __name__)

# Wrong tokens per caller address per hour, in this process. Generous, because a
# family mistyping the URL onto three devices should not be locked out, and
# small enough that a scan is not free.
MOST_MISSES = 30
PER_SECONDS = 3600

# What a screen response always carries, whatever it is.
SCREEN_HEADERS = {
    # The URL is a credential, so the page must not be findable. Both halves:
    # one keeps it out of an index, the other stops a crawler following what is
    # on it.
    "X-Robots-Tag": "noindex, nofollow",
    # A shared cache holding a family's day under a URL anyone downstream can
    # replay is not a cache, it is a leak. A panel on flaky wifi keeps its last
    # dashboard in memory instead — the page fetches its next copy and only
    # swaps it in when one arrives (board.html) — so nothing about that needs
    # a weaker header. Surviving a reboot while offline would need a service
    # worker, and is still open (DIN-60).
    "Cache-Control": "no-store, private",
}


@bp.record_once
def _build_the_limiter(state):
    """One limiter per app rather than one per process.

    A module-level counter would be shared by every app built in a process,
    which is fine in production and wrong in a test suite that builds several.
    The same reasoning as `auth._build_the_limiter`, and the same shape.
    """
    state.app.config.setdefault(
        "SCREEN_LIMITER", ratelimit.Limiter(MOST_MISSES, PER_SECONDS))


@bp.route("/s/<token>")
def board(token):
    store = store_for_token(token)
    if store is None:
        return _refused()
    return _screen(render_board(
        store, manifest_url=url_for("screen.manifest", token=token),
        access=access_for(current_app.config["POOL"], store.family_id)))


@bp.route("/s/<token>/manifest.webmanifest")
def manifest(token):
    """The panel's own manifest, so saving it to a home screen gets a name.

    `board.manifest` is behind the session, so a tablet asking for it from a
    screen URL gets a redirect to `/login` and the saved icon is a browser
    default. This is the same manifest with the screen URL as its `start_url`
    and its `id` — which also keeps it distinct from the settings one, and
    sharing an `id` makes a phone treat the two as a single app.
    """
    store = store_for_token(token)
    if store is None:
        return _refused()
    return _screen(
        manifest_for(store.load_config(), url_for("screen.board", token=token)))


def _refused():
    """What a wrong token gets: a plain page, and never a hint.

    **404, never 403.** "Forbidden" would confirm the token exists and is merely
    not allowed, which is the one thing a guess must not learn. Mistyped,
    rotated away this morning and never issued are the same answer.

    The miss is counted here rather than in `store_for_token`, because this is
    the only place that knows a lookup failed — and only misses are counted, so
    a real screen asking every five minutes for a year is never refused.

    **The token is not echoed**, into the page or the log. It is a credential
    even when it is wrong, because a typo of a real one is nearly a real one.
    """
    limiter = current_app.config["SCREEN_LIMITER"]
    caller = ratelimit.client_ip(request)
    if not limiter.allow(caller):
        log.warning("Screen lookups from %s are over the limit (%s misses per "
                    "%s minutes, in this process).",
                    caller or "an unknown caller",
                    limiter.most, round(limiter.per / 60))
        return _screen(render_template(
            "screen_refused.html",
            heading="Too many tries",
            detail="Wait a while, then reload this page."), status=429)
    return _screen(render_template(
        "screen_refused.html",
        heading="This screen link does not work",
        detail="Check it against the one on your settings page. If the link "
               "was changed, every screen needs the new one."), status=404)


def _screen(body, status=200):
    """One place where the three rules above are applied."""
    response = make_response(body, status)
    for header, value in SCREEN_HEADERS.items():
        response.headers[header] = value
    return response
