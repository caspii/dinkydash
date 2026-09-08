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


def client_ip(request):
    """The address the request came from, as far as it can be known.

    **Read `X-Forwarded-For` from the right, not the left.** A proxy appends
    the address it saw, so entries near the end were written by our own
    infrastructure and entries near the front are whatever the caller sent.
    Trusting the leftmost — which is the obvious reading, and the wrong one —
    would let one script claim a thousand addresses and walk straight past the
    limit above.

    **Skipping private addresses on the way is what makes it safe either way.**
    If App Platform ever puts a second hop in front of the container, the last
    entry becomes an internal `10.x` and every family in the world would share
    one bucket — twenty sign-ins an hour, globally, and it would look like a
    mail problem rather than a rate limit. An internal hop is always a private
    address and a real client on the internet never is, so the first public
    address from the right is the client under either arrangement.

    Falls back to the socket address, which is what a Pi and a test see.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    for hop in reversed(hops):
        if _is_public(hop):
            return hop
    # Everything was private or unparseable: local development, or a proxy
    # arrangement nobody here anticipated. The rightmost is still the closest
    # thing to the truth, and being over-strict is the safe direction.
    if hops:
        return hops[-1]
    return request.remote_addr or ""


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
