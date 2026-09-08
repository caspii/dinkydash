"""The Flask app: the board on one route, the settings UI on the rest.

Two modes, and mode gates four things here — where the config is stored,
whether the session key is allowed to be a fallback, whether there is a login
at all, and whether the session cookie is `Secure`:

    DINKYDASH_MODE=single   config.yaml, no accounts, no login (the default)
    DINKYDASH_MODE=cloud    Postgres, magic links, and a real secret key or it
                            will not start

Self-hosted mode has no accounts and no login — it serves one family on a home
network. Anyone who can reach the port can edit the config, which is the same
trust model as the config file it writes. Cloud mode cannot inherit that: there
the session *is* the authentication, so `web/routes/auth.py` is registered and
both `/` and `/settings` are behind it.

`Secure` on the cookie is the fourth gate and the only one that is not a
feature: a Pi serves plain HTTP on a LAN, and a `Secure` cookie is never sent
over it. CSRF, by contrast, is on in **both** modes — see `web/session.py`.

**Where the config is stored is also *whose* config**, which is why cloud mode
holds no store here at all: `web/family.py` builds one per request from the
family on the session. What this module owns is the pool behind them, built
once and shared.

Everything else below `create_app` is mode-blind. The routes ask
`family.current_store()` and never learn what they were given.
"""

import os

from flask import Flask, redirect, url_for

SINGLE, CLOUD = "single", "cloud"

# Harmless with no accounts: it only ever signs flash messages on a LAN-local
# app. A forgeable session in cloud mode is a forgeable login, which is why
# `_secret_key` refuses to reach for this one there.
SELF_HOSTED_KEY = "dinkydash-self-hosted"


def mode():
    return os.environ.get("DINKYDASH_MODE", SINGLE).strip().lower() or SINGLE


def create_app(store=None, pool=None):
    """The app. `store` and `pool` are seams for tests and for `app.py`.

    In **single mode** one `FileStore` is built here and every request shares
    it: one family, one file, no session to ask.

    In **cloud mode** `STORE` stays `None` and `web/family.py` builds one per
    request from the family on the session. An injected `store` is still used
    for its pool, but **it is not used to serve a request** — cloud mode reads
    the family from the session and from nowhere else, so there is no argument
    to `create_app` that can quietly turn multi-tenancy off.
    """
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["MODE"] = mode()
    app.secret_key = _secret_key(app.config["MODE"])
    # Every route reads and writes through `family.current_store()`, and none
    # of them is told what is behind it (PLAN.md decision 10).
    app.config["STORE"] = store if store is not None else _fixed_store(app.config["MODE"])
    # One pool for the life of the process, shared by every request's store and
    # by the two things that are not one family's rows: signing somebody in,
    # and the login-token sweep. **Never one pool per request** — the cluster
    # has 22 connections and a PgBouncer in front of them.
    app.config["POOL"] = _pool_for(app.config["MODE"], store, pool)

    # The hostname this board answers on, for the one URL that has to be built
    # outside a browser: the sign-in link in an email. **Not `request.host`**,
    # which is the `Host` header and is written by whoever is calling — an
    # attacker who could set it would have a victim's link mailed to their own
    # server. `wsgi.py` refusing to route an unknown host closes that too, but
    # a credential should not depend on a rule in another file.
    app.config["APP_HOST"] = os.environ.get("DINKYDASH_APP_HOST", "").strip()

    # The templates need to know the mode too, and they cannot ask Flask's own
    # `config` for it: the settings pages pass the *family's* config dict under
    # that name and shadow it.
    app.jinja_env.globals["cloud"] = app.config["MODE"] == CLOUD

    from .session import configure as configure_session
    configure_session(app)

    from .routes.board import bp as board_bp
    from .routes.settings import bp as settings_bp

    app.register_blueprint(board_bp)
    app.register_blueprint(settings_bp, url_prefix="/settings")

    if app.config["MODE"] == CLOUD:
        # Not registered in single mode, so `/login` is a 404 there rather than
        # a page that exists and refuses. One family on their own network has
        # nobody to sign in.
        from .routes.auth import bp as auth_bp
        app.register_blueprint(auth_bp)

        from dinkydash.pgstore import NoSuchFamily

        @app.errorhandler(NoSuchFamily)
        def family_is_gone(exc):
            """A signed-in session naming a family that no longer exists.

            A session lasts thirty days and an account can be deleted inside
            one, so this is reachable without anything being wrong. Signing the
            holder out and sending them to `/login` is the honest answer; a 500
            would be a bug report about a working feature.
            """
            from .session import sign_out
            sign_out()
            return redirect(url_for("auth.login"))

    @app.after_request
    def no_referrer(response):
        """Never tell anybody else what URL the reader is on.

        Cloud mode puts the board at `/s/<token>`, and that token is a bearer
        credential — whoever has the URL sees the family's day. Any outbound
        request from the page, and any link somebody follows off it, would
        otherwise hand the whole URL to a third party in the `Referer` header.

        Set here rather than in the templates so it covers every response
        including redirects and errors, and set in single mode too: a header
        that only exists in one mode is a header nobody tests.
        """
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    return app


def _secret_key(current_mode):
    key = os.environ.get("DINKYDASH_SECRET_KEY")
    if key:
        return key
    if current_mode == CLOUD:
        # Refusing to start is the point. A hardcoded key in a multi-tenant app
        # lets anybody mint a session cookie for any family, and the failure is
        # silent — everything works, for everyone, including strangers.
        raise RuntimeError(
            "DINKYDASH_SECRET_KEY is not set. Cloud mode will not start without one."
        )
    return SELF_HOSTED_KEY


def _fixed_store(current_mode):
    """The one store a whole process shares, or `None` when each request needs its own.

    Cloud mode gets `None` on purpose. There is no "the" family there, so a
    store built at start-up could only be built from an environment variable —
    which is what this replaced, and what served whoever the environment said
    to whoever asked.
    """
    if current_mode == CLOUD:
        return None
    from dinkydash.store import FileStore
    return FileStore()


def _pool_for(current_mode, store, pool):
    """The connection pool for this process, or `None` if it needs none.

    The import is inside the branch on purpose: `dinkydash.db` pulls in
    psycopg, which lives in `requirements-cloud.txt` and is not installed on a
    Pi.

    A supplied `pool` wins, then one hanging off a supplied `store` — both are
    how the tests hand in a scratch database. Only a cloud app that was given
    neither opens a connection, which is what lets a test build a cloud app
    around a `FileStore` without one.
    """
    if pool is not None:
        return pool
    on_the_store = getattr(store, "pool", None)
    if on_the_store is not None:
        return on_the_store
    if current_mode != CLOUD or store is not None:
        return None

    from dinkydash import db
    return db.pool()
