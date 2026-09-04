"""The board itself, plus a preview harness for the target screen sizes."""

from flask import Blueprint, current_app, render_template

from dinkydash import board as board_view
from dinkydash import config as config_module

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


@bp.route("/preview")
def preview():
    """Every target screen at once, so a layout change can be checked in one go."""
    return render_template("preview.html", sizes=PREVIEW_SIZES)
