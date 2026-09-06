"""The board itself, plus a preview harness for the target screen sizes."""

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


def current_config():
    return config_module.load_config(current_app.config["CONFIG_PATH"])


@bp.route("/")
def index():
    from web import load_payload
    config = current_config()
    today = config_module.today_for(config)
    view = board_view.build_view(config, load_payload(config), today)
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
