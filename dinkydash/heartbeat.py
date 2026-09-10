"""The worker's pulse: written after every completed pass, read by whoever asks. Cloud only.

    beat(pool, ticked, failed, took_ms)   the worker, once a pass has finished
    last(pool)                            the last pass, or None if none has ever finished
    verdict(row, now, stale_after)        ok, stale or never, with the age (pure)

**A heartbeat means a pass finished**: every family that was due was
considered, whatever happened to each. A family whose feed was down or whose
model call was refused is handled inside the tick and still counts as a live
worker — that is failed *work*, and `failed` counts it. What does not beat is
a pass that a stop request cut short, or one that could not list the families
at all: both leave the row as it was, so it goes stale.

**Stale is the alert.** `/healthz/worker` (`web/routes/status.py`) answers 503
once the last pass is older than `stale_after`, and the monitor workflow
(`.github/workflows/monitor.yml`) turns that into a failed run, which is an
email. The default allows three missed five-minute passes: enough for a
redeploy — App Platform starts the new worker before it stops the old one, but
not always promptly — and for one slow pass, without letting a dead worker
hide for long. Change `DINKYDASH_WORKER_INTERVAL` and this has to move with it.

**The fifth deliberately unscoped table, and the emptiest**: a name, a time and
three counts. No family identifier, no calendar, no generated text — the same
property `growth_by_day` has, for the same reason (`dinkydash/CLAUDE.md`).

Like `growth.py`, this imports no driver: it is handed a pool and asks it for
connections. `verdict` takes `now` rather than reading a clock, like everything
else in this package.
"""

from datetime import datetime, timezone

# The one loop there is. `python -m worker` walks every family; a second loop on
# its own cadence would report under its own name.
TICK = "tick"

# How old the last pass may be before the worker is presumed dead: three missed
# five-minute passes. `DINKYDASH_WORKER_STALE_AFTER` overrides it, in seconds.
DEFAULT_STALE_AFTER = 900


def beat(pool, ticked, failed, took_ms, name=TICK, now=None):
    """Record that a pass finished now. One row per loop, overwritten each time."""
    now = now or datetime.now(timezone.utc)
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute(
            """INSERT INTO worker_heartbeat (name, passed_at, families, failed, took_ms)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (name) DO UPDATE
                   SET passed_at = EXCLUDED.passed_at,
                       families = EXCLUDED.families,
                       failed = EXCLUDED.failed,
                       took_ms = EXCLUDED.took_ms""",
            (name, now, max(0, int(ticked)), max(0, int(failed)), max(0, int(took_ms))))


def last(pool, name=TICK):
    """The last completed pass, or None if there has never been one."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT passed_at, families, failed, took_ms
               FROM worker_heartbeat WHERE name = %s""", (name,))
        row = cur.fetchone()
    if row is None:
        return None
    passed_at, families, failed, took_ms = row
    return {"passed_at": passed_at, "families": families, "failed": failed,
            "took_ms": took_ms}


def verdict(row, now, stale_after=DEFAULT_STALE_AFTER):
    """What the last pass says about the worker: `ok`, `stale` or `never`.

    Pure. `row` is what `last` returned, `now` is the caller's clock and
    `stale_after` is in seconds. The answer carries the age, so a reader can
    see *how* stale, and the pass itself, so the operator's page can show it.
    The age is clamped at zero: a heartbeat a few seconds in the future is two
    clocks disagreeing, not a worker from tomorrow.
    """
    if row is None:
        return {"status": "never", "age_seconds": None, "last_pass": None}
    age = max(0, int((now - row["passed_at"]).total_seconds()))
    return {
        "status": "stale" if age > stale_after else "ok",
        "age_seconds": age,
        "last_pass": {
            "passed_at": row["passed_at"].isoformat(),
            "families": row["families"],
            "failed": row["failed"],
            "took_ms": row["took_ms"],
        },
    }
