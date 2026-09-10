"""What the worker has been doing, for whoever is watching from outside. Cloud only.

    GET /healthz/worker     200 if a pass finished recently, 503 if not

Registered only in cloud mode, like `auth`, `screen` and `admin`. A self-hosted
board has cron rather than a worker, and its board already shows a stale day
for what it is.

**This is not the platform's health check, and it must never become it.**
`/healthz` (`web/routes/board.py`) is what App Platform probes, and it reads
nothing on purpose: a probe that depends on the database turns a slow query
into a restarted container and a rolled-back deploy. This path *does* read the
database — one row, by primary key — and answers 503 when the worker has gone
quiet, which is exactly what a probe must not do and exactly what an external
monitor wants. `.github/workflows/monitor.yml` asks it every fifteen minutes
and after every deploy; `tests/test_deploy_spec.py` fails if the spec ever
points the probe here.

**No session, no family, no token.** The row it reads has no family in it
(`dinkydash/heartbeat.py`), and what it says — when the last pass finished,
how many families it walked, how many raised, how long it took — is about the
service, not about anybody. It is public so that the monitor needs no secret,
and `no-store` and `noindex` because a status line is not content.

The one thing a stranger can do with it is make the app read a row. That is a
primary-key lookup, bounded by the pool, and the same class of cost as a
`/s/<token>` that misses — which is not rate-limited either until it misses
often.
"""

import os
from datetime import datetime, timezone

from flask import Blueprint, current_app, make_response

from dinkydash import heartbeat

bp = Blueprint("status", __name__)

# Seconds since the last completed pass before the worker is presumed dead.
# Defaults to three missed five-minute passes (`heartbeat.DEFAULT_STALE_AFTER`).
STALE_AFTER = "DINKYDASH_WORKER_STALE_AFTER"

HEADERS = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}


@bp.route("/healthz/worker")
def worker():
    row = heartbeat.last(current_app.config["POOL"])
    said = heartbeat.verdict(row, datetime.now(timezone.utc), stale_after())
    response = make_response(said, 200 if said["status"] == "ok" else 503)
    for header, value in HEADERS.items():
        response.headers[header] = value
    return response


def stale_after():
    """How old the last pass may be, in seconds: the environment, or the default.

    Nonsense falls back rather than failing, the way `worker.interval` does: a
    typo in an app spec should not make every status request a 500.
    """
    try:
        return max(1, int(os.environ.get(STALE_AFTER, heartbeat.DEFAULT_STALE_AFTER)))
    except ValueError:
        return heartbeat.DEFAULT_STALE_AFTER
