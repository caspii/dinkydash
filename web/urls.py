"""App origins and dashboard paths shared by routes and the login-link CLI."""

from flask import current_app, request, url_for

from web import CLOUD
from web.family import current_screen_token


def app_origin(host="", *, override=None):
    """Use HTTPS for a configured host; allow an explicit CLI preview origin."""
    if override:
        return override.rstrip("/")
    host = host.strip()
    return f"https://{host}" if host else "http://127.0.0.1:5000"


def absolute_url(path):
    """Put a local path on the configured HTTPS origin, even behind a TLS proxy.

    APP_HOST is set in cloud deployments. The request-host fallback supports
    development without that configuration.
    """
    host = current_app.config.get("APP_HOST") or request.host
    return app_origin(host) + path


def board_path():
    """Return this family's dashboard path in the current mode."""
    if current_app.config["MODE"] != CLOUD:
        return url_for("board.index")
    return url_for("screen.board", token=current_screen_token())
