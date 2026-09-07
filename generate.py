#!/usr/bin/env python3
"""Write the board. Run from cron.

    */5 * * * * cd /home/pi/dinkydash && venv/bin/python generate.py --tick >> generate.log 2>&1

`--tick` does only what the config says is owed: re-fetch the calendars every
`refresh_minutes`, write the brief once a day after `brief_time`, and exit
quietly when neither is due. Without it, a plain run does both at once, which
is what the old `0 6 * * *` line has always meant.

Everything interesting lives in the dinkydash package; this is the command-line
skin around dinkydash.runner.
"""

import argparse
import logging
import sys
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

try:
    import fcntl  # POSIX only; the board runs on a Pi
except ImportError:  # pragma: no cover - Windows has no flock
    fcntl = None

from dotenv import load_dotenv

from dinkydash import config as config_module
from dinkydash.claude_client import GenerationError
from dinkydash.runner import read_payload, refresh_calendars, run, write_brief
from dinkydash.schedule import due

load_dotenv()
log = logging.getLogger("dinkydash")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate the DinkyDash board.")
    parser.add_argument("--config", help="path to config.yaml")
    parser.add_argument("--date", help="generate for this date (YYYY-MM-DD) instead of today")
    parser.add_argument("--tick", action="store_true",
                        help="do only what is due now, and nothing when nothing is")
    parser.add_argument("--quiet", action="store_true", help="only log warnings and errors")
    args = parser.parse_args(argv)

    if args.tick and args.date:
        parser.error("--tick works from the real clock; --date is for one-off runs")

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

    # Generated data sits beside the config it was generated from, so --config
    # moves the payload and the history with it.
    base = Path(path).expanduser().parent
    if args.tick:
        with only_one_tick(base / LOCK_FILE) as mine:
            if not mine:
                log.warning("A previous tick is still running; skipping this one.")
                return 0
            return tick(config, base)

    today = date.fromisoformat(args.date) if args.date else config_module.today_for(config)
    try:
        payload = run(config, today=today, base=base)
    except GenerationError as exc:
        # The previous board is left in place rather than blanking the screen.
        log.error("%s", exc)
        log.error("Keeping the previous board.")
        return 1

    report(payload)
    return 0


LOCK_FILE = ".tick.lock"


@contextmanager
def only_one_tick(path):
    """Hold an exclusive lock for the tick, or yield False and let it be skipped.

    A tick can outlive its five-minute slot — several feeds timing out, then a
    slow model call — and the next one would find the brief still unwritten and
    pay for it a second time, with two history entries and a last-writer-wins
    race over the payload. The overlapping tick gives up instead: whatever is
    owed is still owed five minutes later.
    """
    if fcntl is None:
        yield True
        return
    handle = open(path, "a")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True
    finally:
        handle.close()  # releases the lock, and so does the process exiting


def tick(config, base):
    """Do what the clock and the config say is owed, and no more."""
    now = datetime.now(timezone.utc)
    payload = read_payload(config_module.data_path(config, base=base))
    owed = due(config, payload, now)

    if not any(owed.values()):
        # With a */5 cron line this is the normal case, so it is logged below
        # the default level — otherwise it would be the whole of generate.log.
        log.debug("Nothing due")
        return 0

    if owed["refresh"]:
        refresh_calendars(config, now=now, base=base)

    if owed["brief"]:
        today = now.astimezone(config_module.tzinfo_for(config)).date()
        try:
            report(write_brief(config, today=today, base=base))
        except GenerationError as exc:
            # Not fatal: the brief is simply due again on the next tick.
            log.error("%s", exc)
            log.error("Keeping the previous board; the next tick will try again.")
            return 1
    return 0


def report(payload):
    log.info("Headline: %s", payload["headline"])
    log.info("Note: %s", payload["note"])


if __name__ == "__main__":
    sys.exit(main())
