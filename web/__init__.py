"""The Flask app: the board on one route, the settings UI on the rest.

Self-hosted mode has no accounts and no login — it serves one family on a home
network. Anyone who can reach the port can edit the config, which is the same
trust model as the config file it writes.
"""

import os
from pathlib import Path

from flask import Flask

from dinkydash import config as config_module
from dinkydash import runner


def load_payload(config):
    """The last generated payload, or None if nothing has been generated yet."""
    return runner.read_payload(config_module.data_path(config))


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    # Only ever used to sign flash messages on a LAN-local app.
    app.secret_key = os.environ.get("DINKYDASH_SECRET_KEY", "dinkydash-self-hosted")
    app.config["CONFIG_PATH"] = Path(config_module.config_path())

    from .routes.board import bp as board_bp
    from .routes.settings import bp as settings_bp

    app.register_blueprint(board_bp)
    app.register_blueprint(settings_bp, url_prefix="/settings")
    return app
