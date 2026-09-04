"""Flask entry point.

    flask run --host=0.0.0.0        # or: python app.py

Serves the board at / and the settings UI at /settings. Self-hosted mode has no
login: whoever can reach the port can edit the config.
"""

import logging
import os

from dotenv import load_dotenv

from web import create_app

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("DINKYDASH_HOST", "0.0.0.0"),
        port=int(os.environ.get("DINKYDASH_PORT", "5000")),
        debug=bool(os.environ.get("DINKYDASH_DEBUG")),
    )
