"""The dashboard itself, plus a preview harness for the target screen sizes.

**Where the dashboard lives is the one thing mode changes here**, and it changes
because of authentication rather than layout. Single mode serves it at `/`:
one family, no session, and the URL somebody types into a Pi's kiosk browser.
Cloud mode cannot, because a wall panel has no way to sign in — so there the
dashboard is at `/s/<token>` (`web/routes/screen.py`) and `/` is the front door of
the signed-in area, redirecting to the settings.

`render_board` and `manifest_for` below are what the two routes share, so the
dashboard is one piece of code reached two ways rather than two that drift.
"""

import os

from flask import (Blueprint, current_app, redirect, render_template, request,
                   url_for)

from dinkydash import board as board_view
from dinkydash import config as config_module
from web import CLOUD
from web import manifest as manifest_module
from web.family import current_store
from web.session import guard
from web.urls import board_path

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
    """Cloud mode: the dashboard is a family's dashboard, so it needs a session.

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
    """The dashboard, or — in cloud mode — the way in to the settings.

    The mode check is an authentication one, which is the only kind this file
    is allowed. In cloud mode `/` is behind `guard()`, so a signed-out visitor
    has already been sent to `/login` before this runs and the only person
    reaching this line is signed in. Their dashboard is not here: it is at the
    screen URL, which is the one a panel can open without a cookie.
    """
    if current_app.config["MODE"] == CLOUD:
        return redirect(url_for("settings.home"))
    return render_board(current_store())


def render_board(store, manifest_url=None, access=None):
    """The dashboard page for whichever family that store is for.

    Shared with `web/routes/screen.py`, so the signed-in view and the wall
    panel render the same page from the same code. `manifest_url` is the only
    difference between them and it is one link in the head: the panel's
    manifest has to be reachable without a session, or "save to home screen"
    gets a redirect to `/login` instead of a name and an icon.
    Hosted callers also pass access state, so a lapsed panel cannot keep
    recomputing the day. Active cloud dashboards retain parity with single mode.
    """
    config = store.load_config()
    payload = store.load_payload(config)
    if access and access.ended:
        view = board_view.build_lapsed_view(config, payload, access.show_last_board)
    else:
        today = config_module.today_for(config)
        view = board_view.build_view(config, payload, today)
    return render_template("board.html", view=view,
                           manifest_url=manifest_url or url_for("board.manifest"))


def manifest_for(config, url):
    """A wall panel saved to a tablet's home screen: full screen, no browser.

    Separate from the settings manifest, and deliberately so — one is a screen
    you leave on, the other is a page you visit. They must keep different
    `id`s: share one and the phone treats them as a single app.
    """
    # The saved app keeps its own background until the dashboard paints, so it has
    # to match the theme or a dark dashboard flashes white on every open.
    colour = "#17120f" if config.get("theme") == "dark" else "#ffffff"
    return manifest_module.response(
        id=url,
        name=config.get("family_name") or "DinkyDash",
        short_name=config.get("family_name") or "DinkyDash",
        description="Today's agenda, whose turn it is, and what is coming up.",
        start_url=url,
        display="fullscreen",
        background_color=colour,
        theme_color=colour,
    )


@bp.route("/manifest.webmanifest")
def manifest():
    return manifest_for(current_config(), url_for("board.index"))


@bp.route("/preview")
def preview():
    """Show the dashboard at each target screen size."""
    return render_template("preview.html", sizes=PREVIEW_SIZES,
                           board_url=board_path())


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
