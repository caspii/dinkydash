"""The board itself, plus a preview harness for the target screen sizes."""

import os

from flask import Blueprint, render_template, request, url_for

from dinkydash import board as board_view
from dinkydash import config as config_module
from web import manifest as manifest_module
from web.family import current_store
from web.session import guard

bp = Blueprint("board", __name__)

PREVIEW_SIZES = [
    ("Raspberry Pi panel", 800, 480),
    ("TV / monitor", 1280, 720),
    ("Old iPad", 1024, 768),
]

# **`/healthz` must answer with no session, or every deploy rolls itself back.**
# App Platform's health check arrives with no cookie and on a hostname nobody
# signed in on; a 302 to `/login` there fails the check three times and the
# platform reverts the release. It is also the one route that reads nothing, so
# there is no family for it to need.
OPEN_IN_CLOUD_MODE = {"board.healthz"}


@bp.before_request
def _needs_a_family():
    """Cloud mode: the board is a family's board, so it needs a session.

    Single mode has one family and no session, and `guard()` returns None there
    — this is the same code in both modes, deciding differently.
    """
    if request.endpoint in OPEN_IN_CLOUD_MODE:
        return None
    return guard()


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
    `.git` to ask. **App Platform does not set one on its own** — this read
    "unknown" in production from the first deploy until 8 September 2026,
    because the two fallbacks that used to be here (`APP_PLATFORM_COMPONENT_
    COMMIT`, `SOURCE_COMMIT`) were guesses at variable names that do not
    exist. What does exist is `${_self.COMMIT_HASH}`, a *bindable* variable:
    it has to be assigned to a key in the component's own `envs` before
    anything can read it, and it is component-scoped, so it cannot live in the
    app-level block with the rest. `.do/app.yaml` binds it to `GIT_SHA`, which
    is the one name `website/site.py` already agreed on.
    """
    return {
        "status": "ok",
        "commit": os.environ.get("GIT_SHA") or "unknown",
    }, 200, {"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}
