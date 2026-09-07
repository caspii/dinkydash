"""The board itself, plus a preview harness for the target screen sizes."""

import os

from flask import Blueprint, current_app, render_template, url_for

from dinkydash import board as board_view
from dinkydash import config as config_module
from web import manifest as manifest_module

bp = Blueprint("board", __name__)

PREVIEW_SIZES = [
    ("Raspberry Pi panel", 800, 480),
    ("TV / monitor", 1280, 720),
    ("Old iPad", 1024, 768),
]


def current_store():
    return current_app.config["STORE"]


def current_config():
    return current_store().load_config()


@bp.route("/")
def index():
    store = current_store()
    config = store.load_config()
    today = config_module.today_for(config)
    view = board_view.build_view(config, store.load_payload(config), today)
    return render_template("board.html", view=view)


@bp.route("/manifest.webmanifest")
def manifest():
    """A wall panel saved to a tablet's home screen: full screen, no browser.

    Separate from the settings manifest, and deliberately so — one is a screen
    you leave on, the other is a page you visit.
    """
    config = current_config()
    # The saved app keeps its own background until the board paints, so it has
    # to match the theme or a dark board flashes white on every open.
    colour = "#17120f" if config.get("theme") == "dark" else "#ffffff"
    return manifest_module.response(
        id=url_for("board.index"),
        name=config.get("family_name") or "DinkyDash",
        short_name=config.get("family_name") or "DinkyDash",
        description="Today's agenda, whose turn it is, and what is coming up.",
        start_url=url_for("board.index"),
        display="fullscreen",
        background_color=colour,
        theme_color=colour,
    )


@bp.route("/preview")
def preview():
    """Every target screen at once, so a layout change can be checked in one go."""
    return render_template("preview.html", sizes=PREVIEW_SIZES)


@bp.route("/healthz")
def healthz():
    """Is this process up, and which commit is it?

    **Deliberately touches nothing.** No config read, no database query, no
    file. A health check that depends on storage turns a slow query into a
    failed deploy and hands anyone who can reach the port a way to make the
    platform restart the app. "Is the WSGI worker answering" is the only
    question it should be able to answer wrongly.

    The SHA comes from the environment because a deployed checkout has no
    `.git` to ask. App Platform sets it; anything else falls back to "unknown".
    """
    return {
        "status": "ok",
        "commit": os.environ.get("GIT_SHA")
        or os.environ.get("APP_PLATFORM_COMPONENT_COMMIT")
        or os.environ.get("SOURCE_COMMIT")
        or "unknown",
    }, 200, {"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}
