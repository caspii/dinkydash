"""The Flask app: the board on one route, the settings UI on the rest.

Two modes, and mode gates exactly two things here — where the config is stored,
and whether the session key is allowed to be a fallback:

    DINKYDASH_MODE=single   config.yaml, no accounts, no login (the default)
    DINKYDASH_MODE=cloud    Postgres, and a real secret key or it will not start

Self-hosted mode has no accounts and no login — it serves one family on a home
network. Anyone who can reach the port can edit the config, which is the same
trust model as the config file it writes. Cloud mode cannot inherit that: there
the session *is* the authentication.

Everything below `create_app` is mode-blind. The routes take a store out of
`app.config` and never learn which one they were given.
"""

import os

from flask import Flask

SINGLE, CLOUD = "single", "cloud"

# Harmless with no accounts: it only ever signs flash messages on a LAN-local
# app. A forgeable session in cloud mode is a forgeable login, which is why
# `_secret_key` refuses to reach for this one there.
SELF_HOSTED_KEY = "dinkydash-self-hosted"


def mode():
    return os.environ.get("DINKYDASH_MODE", SINGLE).strip().lower() or SINGLE


def create_app(store=None):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["MODE"] = mode()
    app.secret_key = _secret_key(app.config["MODE"])
    # Every route reads and writes through this one object, and none of them is
    # told what is behind it. Cloud mode hands in a different store and nothing
    # below this line changes (PLAN.md decision 10).
    app.config["STORE"] = store or _default_store(app.config["MODE"])

    from .routes.board import bp as board_bp
    from .routes.settings import bp as settings_bp

    app.register_blueprint(board_bp)
    app.register_blueprint(settings_bp, url_prefix="/settings")

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


def _default_store(current_mode):
    """The store this process should use when the caller did not supply one.

    The cloud imports are inside the branch on purpose: `dinkydash.pgstore` and
    `dinkydash.db` pull in psycopg, which lives in `requirements-cloud.txt` and
    is not installed on a Pi.
    """
    if current_mode != CLOUD:
        from dinkydash.store import FileStore
        return FileStore()

    from dinkydash import db
    from dinkydash.pgstore import PostgresStore

    # One family for now. Phase 1 replaces this with the family on the session,
    # checked against the id in the URL before it reaches a query — the whole
    # point of DIN-31 being the schema and not yet the multi-tenancy.
    return PostgresStore(db.pool(), db.require("DINKYDASH_FAMILY_ID"))
