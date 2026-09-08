"""A counter of recent requests, per key, in this process and nowhere else.

The login request endpoint is limited twice, and the two halves are limited in
different places on purpose:

    per email address   `accounts.issue_link`, counted in Postgres, so it holds
                        across every web instance and survives a redeploy
    per client IP       here, in memory, because the alternative is a database
                        write on every unauthenticated request — which is
                        itself something to flood

**This is a spend control as much as a security one.** Every request that gets
through sends an email on the SendGrid account KeepTheScore also sends from,
and a bounce there costs a sender reputation that is not only ours.

**It counts per process.** The app runs `gunicorn --workers 2`, so the real
ceiling is twice what is written below, and a redeploy resets it. That is
accepted rather than overlooked: the number is chosen to be a bound on abuse,
not a precise quota, and PLAN.md phase 2's global spend breaker is what
actually stops a bill running away.
"""

import ipaddress
import threading
import time
from collections import OrderedDict, deque

# How many distinct keys are tracked before the oldest are forgotten. A flood
# wide enough to need more than this is a botnet rather than a nuisance, and
# forgetting is the right failure: a rate limiter that starts refusing everyone
# has turned an abusive account into an outage for every family.
MOST_KEYS = 10_000


class Limiter:
    """At most `most` events per `per` seconds, for each key.

    Thread-safe, because the service runs `--threads 4` and two requests from
    one address really do arrive at once.
    """

    def __init__(self, most, per, most_keys=MOST_KEYS):
        self.most = most
        self.per = per
        self.most_keys = most_keys
        self._seen = OrderedDict()
        self._lock = threading.Lock()

    def allow(self, key, now=None):
        """Record one event and say whether it was within the limit."""
        if not key:
            return True
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._seen.get(key)
            if hits is None:
                hits = self._seen[key] = deque()
            self._seen.move_to_end(key)

            cutoff = now - self.per
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self.most:
                return False
            hits.append(now)
            self._forget_the_oldest()
            return True

    def _forget_the_oldest(self):
        """Keep the map bounded. Called with the lock held."""
        while len(self._seen) > self.most_keys:
            self._seen.popitem(last=False)


# Which header carries the caller's address, in the order they are trusted.
#
# **`X-Forwarded-For` is not first, and on App Platform it is not the caller at
# all.** DigitalOcean's own documentation is explicit: "App Platform adds a
# do-connecting-ip HTTP header that contains the client's IP address... While
# the x-forwarded-for header is often used for this purpose, App Platform uses
# this header for the IP address of the DigitalOcean ingress server that
# forwarded the request to your app."
#
# That is worth stating because the obvious code is wrong here in a quiet way:
# keying a per-caller limit on `X-Forwarded-For` keys it on DigitalOcean, so
# every family in the world shares one bucket and the limit either never fires
# or fires for everybody. It reads correctly and it is wrong.
#
# `CF-Connecting-IP` is the same idea from Cloudflare, and it is second because
# App Platform *is* served through Cloudflare — `app.dinkydash.co` resolves to
# Cloudflare addresses and answers with a `cf-ray`, even though our own zone is
# DNS-only. Ours is not the edge in front of this app; DigitalOcean's is.
CALLER_HEADERS = ("DO-Connecting-IP", "CF-Connecting-IP")


def client_ip(request):
    """The address the request came from, as far as it can be known.

    Tries the platform's own header first, then a conventional proxy chain,
    then the socket. **Returns `""` rather than guessing**, and an empty key is
    one the limiter always allows — deliberately. If the caller cannot be
    identified, the failure worth having is "the per-caller limit does not
    fire" rather than "every caller shares one bucket", which is an outage
    wearing a rate limit's clothes. The per-address limit in
    `accounts.issue_link` is in Postgres and still bounds what any one account
    can spend.

    A header can be forged by anyone who can reach the container without going
    through the edge that sets it. There is no such path here — every hostname
    this app answers on resolves to Cloudflare addresses in front of
    DigitalOcean's ingress — and if there were, the cost is a bypassed spend
    control with a database-backed one behind it.
    """
    for header in CALLER_HEADERS:
        value = request.headers.get(header, "").strip()
        if value:
            return value

    # A conventional proxy chain, for anywhere that is not App Platform. Read
    # from the right, because a proxy *appends* what it saw: the last entry is
    # the one our own infrastructure wrote and the earlier ones are whatever
    # the caller sent. Private addresses are stepped over, because an internal
    # hop is always private and a real client on the internet never is.
    hops = [hop.strip()
            for hop in request.headers.get("X-Forwarded-For", "").split(",")
            if hop.strip()]
    for hop in reversed(hops):
        if _is_public(hop):
            return hop

    # The socket. On App Platform this is an internal address that differs
    # between requests, which is why it is last and why `""` is an acceptable
    # answer above it.
    remote = request.remote_addr or ""
    return remote if _is_public(remote) else ""


def _is_public(address):
    """Could this be a real client on the internet?

    Note for anyone writing a test against this: `is_private` is true for the
    documentation ranges too — `192.0.2.0/24`, `198.51.100.0/24` and
    `203.0.113.0/24`, the ones examples are supposed to use. A test written
    with those goes down the fallback branch above and proves nothing.
    """
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return not (parsed.is_private or parsed.is_loopback or parsed.is_reserved
                or parsed.is_link_local or parsed.is_unspecified)
