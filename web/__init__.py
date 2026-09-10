"""Build the Flask app for single or cloud mode.

Single mode shares one FileStore and needs no accounts. Cloud mode shares a
database pool, resolves stores per request, and requires a real session key.
CSRF and the no-referrer policy apply in both modes.
"""

import os

from flask import Flask, redirect, url_for

SINGLE, CLOUD = "single", "cloud"

SELF_HOSTED_KEY = "dinkydash-self-hosted"


def mode():
    return os.environ.get("DINKYDASH_MODE", SINGLE).strip().lower() or SINGLE


def create_app(store=None, *, pool=None):
    """Build the app, optionally injecting its storage dependency.

    Single mode accepts a store; cloud mode accepts a pool and constructs a
    family's store only after authenticating the request.
    """
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["MODE"] = mode()
    if app.config["MODE"] not in (SINGLE, CLOUD):
        raise ValueError("DINKYDASH_MODE must be 'single' or 'cloud'.")
    app.secret_key = _secret_key(app.config["MODE"])

    if app.config["MODE"] == CLOUD:
        if store is not None:
            raise ValueError("Cloud mode accepts a pool, not a store.")
        if pool is None:
            from dinkydash import db
            pool = db.pool()
    else:
        if pool is not None:
            raise ValueError("Single mode accepts a store, not a pool.")
        if store is None:
            from dinkydash.store import FileStore
            store = FileStore()
    app.config.update(STORE=store, POOL=pool)

    app.config["APP_HOST"] = os.environ.get("DINKYDASH_APP_HOST", "").strip()

    # Settings templates use `config` for the family's settings, not Flask's.
    app.jinja_env.globals["cloud"] = app.config["MODE"] == CLOUD

    from .session import configure as configure_session
    configure_session(app)

    from .assets import configure as configure_assets
    configure_assets(app)

    from .routes.board import bp as board_bp
    from .routes.settings import bp as settings_bp

    app.register_blueprint(board_bp)
    app.register_blueprint(settings_bp, url_prefix="/settings")

    if app.config["MODE"] == CLOUD:
        from .routes.auth import bp as auth_bp
        app.register_blueprint(auth_bp)

        from .routes.screen import bp as screen_bp
        app.register_blueprint(screen_bp)

        from .routes.admin import bp as admin_bp
        app.register_blueprint(admin_bp)

        from dinkydash.pgstore import NoSuchFamily

        @app.errorhandler(NoSuchFamily)
        def family_is_gone(exc):
            """Sign out sessions whose family has since been deleted."""
            from .session import sign_out
            sign_out()
            return redirect(url_for("auth.login"))

    @app.after_request
    def no_referrer(response):
        """Keep credential-bearing URLs out of outbound Referer headers."""
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    return app


def _secret_key(current_mode):
    key = os.environ.get("DINKYDASH_SECRET_KEY")
    if key:
        return key
    if current_mode == CLOUD:
        raise RuntimeError(
            "DINKYDASH_SECRET_KEY is not set. Cloud mode will not start without one."
        )
    return SELF_HOSTED_KEY
