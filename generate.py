#!/usr/bin/env python3
"""Write today's board. Run once a day from cron.

    0 6 * * * cd /home/pi/dinkydash && venv/bin/python generate.py >> generate.log 2>&1

Everything interesting lives in the dinkydash package; this is the command-line
skin around dinkydash.runner.run.
"""

import argparse
import logging
import sys
from datetime import date

from dotenv import load_dotenv

from dinkydash import config as config_module
from dinkydash.claude_client import GenerationError
from dinkydash.runner import run

load_dotenv()
log = logging.getLogger("dinkydash")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate today's DinkyDash board.")
    parser.add_argument("--config", help="path to config.yaml")
    parser.add_argument("--date", help="generate for this date (YYYY-MM-DD) instead of today")
    parser.add_argument("--quiet", action="store_true", help="only log warnings and errors")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    path = args.config or config_module.config_path()
    try:
        config = config_module.load_config(path)
    except FileNotFoundError:
        log.error("No config found at %s. Copy config.example.yaml to config.yaml.", path)
        return 1

    today = date.fromisoformat(args.date) if args.date else config_module.today_for(config)

    try:
        payload = run(config, today=today, base=config_module.config_path().parent)
    except GenerationError as exc:
        # The previous board is left in place rather than blanking the screen.
        log.error("%s", exc)
        log.error("Keeping the previous board.")
        return 1

    log.info("Headline: %s", payload["headline"])
    log.info("Note: %s", payload["note"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
