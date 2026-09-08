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
# **`X-Forwarded-For` is not in this list, and that is the whole point.**
# DigitalOcean's documentation is explicit: "App Platform adds a
# `do-connecting-ip` HTTP header that contains the client's IP address... While
# the `x-forwarded-for` header is often used for this purpose, App Platform uses
# this header for the IP address of the DigitalOcean ingress server that
# forwarded the request to your app."
#
# So `X-Forwarded-For` here is a *public* address shared by every request that
# reaches us. Reading it — even as a last resort, even from the right — hands
# every caller in the world the same key, which is the shared bucket this
# ordering exists to prevent: twenty sign-in requests an hour between all of
# them, and it would look like a mail problem. It was written that way once,
# with a fallback that only ever ran on App Platform and therefore only ever
# recreated the bug.
#
# `CF-Connecting-IP` is the same idea from Cloudflare, and it is second because
# App Platform *is* served through Cloudflare — `app.dinkydash.co` resolves to
# Cloudflare addresses and answers with a `cf-ray`, even though our own zone is
# DNS-only. Ours is not the edge in front of this app; DigitalOcean's is.
CALLER_HEADERS = ("DO-Connecting-IP", "CF-Connecting-IP")


def client_ip(request):
    """The address the request came from, or `""` if it cannot be known.

    **`""` is a real answer, not a failure to produce one**, and the limiter
    always allows an empty key. If callers cannot be told apart, the failure
    worth having is "the per-caller limit does not fire" rather than "everybody
    shares one bucket", which is an outage wearing a rate limit's clothes. The
    per-address limit in `accounts.issue_link` is in Postgres and still bounds
    what any one account can spend. `web.routes.auth` logs the empty case once
    per process, so a control that has stopped working says so.

    The socket address is the last resort and is only used when it is public —
    a plain deployment with no proxy in front. On App Platform it is an
    internal `10.244.x` that differs between requests, which is no more use as
    a key than nothing at all.

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

    remote = (request.remote_addr or "").strip()
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
