"""The Flask app: the board on one route, the settings UI on the rest.

Self-hosted mode has no accounts and no login — it serves one family on a home
network. Anyone who can reach the port can edit the config, which is the same
trust model as the config file it writes.
"""

import os

from flask import Flask

from dinkydash.store import FileStore


def create_app(store=None):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    # Only ever used to sign flash messages on a LAN-local app.
    app.secret_key = os.environ.get("DINKYDASH_SECRET_KEY", "dinkydash-self-hosted")
    # Every route reads and writes through this one object, and none of them is
    # told what is behind it. Cloud mode hands in a different store here and
    # nothing below this line changes (PLAN.md decision 10).
    app.config["STORE"] = store or FileStore()

    from .routes.board import bp as board_bp
    from .routes.settings import bp as settings_bp

    app.register_blueprint(board_bp)
    app.register_blueprint(settings_bp, url_prefix="/settings")
    return app
