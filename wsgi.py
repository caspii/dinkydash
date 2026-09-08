"""The cloud entry point: two Flask apps, one container, routed on the hostname.

    gunicorn "wsgi:application"

`dinkydash.co` is the marketing site; `app.dinkydash.co` is the board and the
settings UI. They are separate Flask apps and stay that way — `website/site.py`
explains why, and both of them want to own `/`. What this module adds is the
one thing that lets them share a container: a look at the `Host` header, above
both apps, before either sees the request.

**Why one container.** `qrpage.co` and `abc-league` already run this way in the
same DigitalOcean account — one App Platform service, one gunicorn, marketing
and application together. A second service would be $5 a month to buy isolation
that has no revenue behind it yet. See PLAN.md, Hosting and deployment.

**This is routing, not a mode gate.** The rule that mode gates four things and
no others still holds: neither app below knows this file exists, neither one
checks a hostname, and single mode never loads it. `app.py` is untouched and is
still what a Pi runs.

**Unknown hostnames get the site, never the board.** App Platform always hands
out an `.ondigitalocean.app` name whatever custom domains are configured, and
its health check uses it — so an unknown host has to answer, or a deploy rolls
itself back. Sending it to the site is also the safer of the two: the site
holds no family's data, and it already marks any non-canonical hostname
`noindex`.
"""

import os

from web import CLOUD, mode


def dispatch(site_app, board_app, board_host):
    """Route by hostname: `board_host` gets the board, everything else the site.

    Both apps are WSGI callables, so this is a WSGI callable too and gunicorn
    cannot tell the difference.
    """
    board_host = _normalise(board_host)

    def application(environ, start_response):
        # `HTTP_HOST` and not `X-Forwarded-Host`. The forwarded header is
        # written by whoever is upstream, and upstream of App Platform is the
        # public internet — trusting it would let a stranger pick which app
        # answers by setting a header. App Platform passes the real Host
        # through, which is what the custom domains are matched on anyway.
        host = _normalise(environ.get("HTTP_HOST", ""))
        app = board_app if host == board_host else site_app
        return app(environ, start_response)

    return application


def _normalise(host):
    """Lower-cased and without the port: `App.Example.com:8080` -> `app.example.com`.

    Hostnames are case-insensitive, and a `Host` header carries the port
    whenever it is not the scheme's default — which it is not when gunicorn
    listens on 8080 behind a proxy.
    """
    return (host or "").strip().lower().split(":")[0]


def _board_host():
    """The hostname the board answers on. Required, and only in cloud mode.

    Defaulting this would be the wrong kind of helpful. A typo in the app spec
    would leave the board silently unreachable while the marketing site served
    every request with a 404 — a failure that looks like a routing bug for as
    long as it takes somebody to think of the header.
    """
    host = os.environ.get("DINKYDASH_APP_HOST")
    if not host:
        raise RuntimeError(
            "DINKYDASH_APP_HOST is not set. wsgi.py cannot route without it."
        )
    return host


def create_application():
    """Build the dispatcher from the environment. Cloud mode only."""
    if mode() != CLOUD:
        # Single mode has one app, no hostname to match on, and no reason to
        # import the site's Markdown renderer onto a Raspberry Pi.
        raise RuntimeError(
            "wsgi.py is the cloud entry point. Single mode runs app.py."
        )

    from web import create_app
    from website.site import create_site_app

    return dispatch(create_site_app(), create_app(), _board_host())


application = create_application() if mode() == CLOUD else None
