"""The bot check in front of the sign-in form, and nothing else.

`/login` is the one page cloud mode serves to somebody with no session, and
every request that gets through it spends something: an email leaves on the
SendGrid account KeepTheScore also sends from, and whoever opens what arrives
starts a family and a trial. The two rate limits bound how fast one caller and
one address can do that. Neither can tell a person from a script working slowly
through a list of harvested addresses, one address at a time, under both.

Cloudflare's Turnstile is the check because App Platform is already served
through Cloudflare, and because verifying an answer is one HTTPS POST rather
than a dependency.

**It is off unless both keys are set.** That is what keeps self-hosting, local
development and the test suite working with no account and no network — and a
self-hoster has no `/login` at all, so this never runs there. Switching it on is
setting `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY`; there is no third flag
to disagree with them.

**The secret key never reaches a template.** The site key is public by design —
it is rendered into the form and read by anybody who views source — and the
secret is only ever sent to Cloudflare from the server.

**A challenge Cloudflare refuses is refused here. A challenge we could not put
to Cloudflare is allowed.** The same trade `ratelimit.client_ip` makes: with the
spend breaker and both rate limits still behind this, a Cloudflare outage that
let some scripted sign-ups through is a smaller failure than one that stopped
every family signing in, which would be an outage wearing a bot check's clothes.
"""

import logging
import os

import requests

log = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# The form field the widget writes its answer into. Cloudflare's name, not ours.
FIELD = "cf-turnstile-response"

# Long enough for a round trip to Cloudflare, short enough that an unreachable
# one does not hold a gunicorn thread open while somebody waits to sign in.
SECONDS = 5

# Cloudflare documents no bound, and an answer is a token rather than a payload.
# Anything past this is not one, and is refused without being sent anywhere.
LONGEST_ANSWER = 4096


def site_key():
    """The public half, for the form. `""` when Turnstile is not switched on."""
    return os.environ.get("TURNSTILE_SITE_KEY", "").strip()


def _secret_key():
    return os.environ.get("TURNSTILE_SECRET_KEY", "").strip()


def configured():
    """Is there both a widget to render and a secret to check its answer with?

    Both or neither. A site key with no secret would render a challenge nobody
    verifies, which is worse than no challenge: it looks like a control.
    """
    return bool(site_key() and _secret_key())


def passed(answer, caller=""):
    """Did this answer come from somebody who did the challenge?

    `caller` is the address from `ratelimit.client_ip`, passed to Cloudflare as
    `remoteip` so an answer solved elsewhere and replayed from another host can
    be spotted. It is already known to Cloudflare, which is the edge in front of
    this app, so sending it tells them nothing new.
    """
    if not configured():
        return True
    if not answer or len(answer) > LONGEST_ANSWER:
        return False

    fields = {"secret": _secret_key(), "response": answer}
    if caller:
        fields["remoteip"] = caller
    try:
        reply = requests.post(VERIFY_URL, data=fields, timeout=SECONDS)
        reply.raise_for_status()
        outcome = reply.json()
    except (requests.RequestException, ValueError) as exc:
        # Deliberately allowed through — see the module docstring. Logged as a
        # warning because a control that has stopped working should say so.
        log.warning("Could not put a sign-in challenge to Cloudflare: %s",
                    type(exc).__name__)
        return True

    if outcome.get("success"):
        return True
    log.info("A sign-in challenge was refused: %s",
             ", ".join(outcome.get("error-codes") or ["no reason given"]))
    return False
