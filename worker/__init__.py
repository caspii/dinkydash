"""The cloud tick loop: the same tick a Pi's cron runs, over every family.

    python -m worker

A Raspberry Pi gets this from `*/5 * * * * generate.py --tick`. There is no
cron in an App Platform container, so cloud mode runs a process that sleeps
instead — same `schedule.due`, same `runner.refresh_calendars` and
`runner.write_brief`, same decisions. **Nothing about what is owed is decided
here**, which is the point: a second implementation of "is a brief due" would
be a second thing to get wrong.

**Why this is a separate component from `web`.** There is no lock on the tick
in cloud mode, so two processes running it would both refresh and both pay
Anthropic for the same brief. Web instances are scaled by traffic and there may
be several; there is exactly one worker. Keeping the loop out of the web
container is what makes "how many web instances" a free decision.

`generate.tick` is imported from the command-line module on purpose rather than
copied. It is the shared orchestration over config, store and clock, and
`tests/test_runner.py` already imports that module the same way.

Housekeeping runs once a pass: `sweep_logins` deletes expired magic-link tokens
and `lifecycle.expire_trials` records ended trials. Account access is also
checked before each fetch and model call, independently of the sweep.

**Every completed pass checks in with Sentry's cron monitor** (DIN-54,
`dinkydash/sentry.py`), and `run_pass` is where "completed" is decided: a stop
request that ended the walk early is not a finished pass, and neither is a
pass that could not list the families. Both send nothing, so the monitor's
next expected check-in goes *missed*, and missed is the alert. That is the
whole of the worker's liveness story. With no `SENTRY_DSN` the check-in is a
no-op and nothing here has a URL to reach.
"""

import logging
import os
import signal
import time
from collections import namedtuple

log = logging.getLogger("dinkydash.worker")

DEFAULT_INTERVAL = 300  # five minutes between passes; schedule.due decides what each owes

# What a pass did: how many families were ticked without raising, and how many
# raised. Both are counts of families, never of anything inside one.
Pass = namedtuple("Pass", "ticked failed")


class Stopping:
    """Set by SIGTERM, read between families.

    App Platform sends SIGTERM before it replaces a container. Finishing the
    family in hand and then stopping is the difference between a redeploy that
    is invisible and one that leaves a half-written dashboard — the brief has been
    paid for by the time it is written, so being killed between the API call
    and the save is the expensive way to lose.
    """

    def __init__(self):
        self.requested = False

    def request(self, *_args):
        log.info("Stop requested; finishing the family in hand.")
        self.requested = True

    def __bool__(self):
        return self.requested


def family_ids(pool):
    """Every family the worker should consider, oldest first.

    **The one deliberately unscoped read in the product.** Every `PostgresStore`
    query is scoped to a `family_id` and must stay that way, because there an id
    arrives from a URL and is a claim rather than a fact. Here there is no
    request and no user: the worker's whole job is to walk all of them, so the
    query lives outside the store rather than weakening it.

    Lapsed families are skipped. Access ending is a freeze: fetches and
    briefs stop while the dashboard keeps its last good state, and that is exactly
    "the worker does not tick them".
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT id FROM families
               WHERE status <> 'lapsed'
                 AND (status <> 'trialing' OR trial_ends_at > now())
               ORDER BY created_at""")
        return [row[0] for row in cur.fetchall()]


def tick_all(pool, store_factory=None, tick=None, stopping=None,
             budget_factory=None):
    """Tick every family once. Returns a `Pass`: how many ticked, how many raised.

    One family's bad calendar feed, missing config or Anthropic outage must not
    stop the others: a shared worker that dies on the noisiest tenant is a
    worker that serves the quietest ones worst. Each family is therefore its
    own try, and a failure is logged and left — the next pass simply finds the
    same thing still due, which is how the whole tick handles failure already.

    **Every family is ticked against a budget** (DIN-43), and it is built here
    rather than inside the tick for the same reason the store is: this is the
    only place that knows both the pool and which family. A refusal is an
    ordinary `GenerationError` inside `tick`, so it is already handled — the
    dashboard on the wall stays, and the next pass asks again.
    """
    from dinkydash.pgstore import PostgresStore
    store_factory = store_factory or (lambda fid: PostgresStore(pool, fid))
    if budget_factory is None:
        from dinkydash import budget as budget_module
        budget_factory = lambda fid: budget_module.for_family(pool, fid)  # noqa: E731
    if tick is None:
        from generate import tick

    done = failed = 0
    for family_id in family_ids(pool):
        if stopping:
            log.info("Stopping before family %s.", family_id)
            break
        try:
            store = store_factory(family_id)
            tick(store.load_config(), store, budget=budget_factory(family_id))
            done += 1
        except Exception:
            # The id, never the config: a family's config holds children's
            # names and a calendar URL is a password. `log.exception` writes
            # the traceback, which is about our code rather than their data.
            log.exception("Tick failed for family %s; leaving it for the next pass.",
                          family_id)
            failed += 1
    return Pass(done, failed)


def run_pass(pool, stopping=None, check_in=None):
    """One pass: housekeeping, every family, the sweep — then the check-in.

    Returns the `Pass`, or None when the pass did not finish.

    **The check-in is sent only after a completed pass**, and from here rather
    than from `tick_all`, because "finished" is decided here. A stop request
    that ended the walk early is not a finished pass; nor is one that could
    not list the families, which is the one thing `tick_all` cannot catch per
    family because there is no family yet — a database that cannot be reached
    is the usual cause. Both send nothing, so the monitor's next expected
    check-in goes missed, and missed is the alert (DIN-54). A family whose
    tick raised is *inside* the pass and is counted in `failed`; the pass
    still finished, and the failure is a Sentry event of its own.

    A check-in that cannot be sent is logged and otherwise ignored. The dashboards
    were written; a pulse that stops the worker is a pulse that kills the
    patient.

    `check_in` is injectable for the tests; the real one is `sentry.check_in`.
    """
    if check_in is None:
        from dinkydash import sentry
        check_in = sentry.check_in
    from dinkydash import lifecycle

    started = time.monotonic()
    try:
        expired = lifecycle.expire_trials(pool)
        if expired:
            log.info("Ended %s expired trial(s).", expired)
    except Exception:
        # Callers still check the deadline themselves if housekeeping fails.
        log.exception("Could not mark expired trials; retrying next pass.")

    try:
        result = tick_all(pool, stopping=stopping)
    except Exception:
        log.exception("The pass could not list the families; leaving it for the "
                      "next pass. No check-in.")
        return None
    swept = sweep_logins(pool)
    took = time.monotonic() - started
    if stopping:
        log.info("Pass interrupted by a stop request after %.1fs; no check-in.", took)
        return None

    log.info("Pass complete: %s families ticked, %s failed, in %.1fs; %s dead "
             "login token(s) deleted.", result.ticked, result.failed, took, swept)
    try:
        check_in(interval(), took)
    except Exception:
        log.exception("Could not send the check-in; the pass itself finished.")
    return result


def sweep_logins(pool):
    """Delete login tokens that have expired. Returns how many went.

    Here rather than in `tick_all` because it is not per-family: one statement
    over one table, once a pass. The web service could do it on a request
    instead, but a sweep on somebody's page load is a slow page for whoever
    happens to arrive at the wrong moment.

    Never raises. A table of dead hashes growing for five more minutes is not
    worth a pass of unwritten dashboards, and the next pass tries again — which is
    how the whole tick handles failure already.
    """
    from dinkydash import accounts

    try:
        return accounts.sweep(pool)
    except Exception:
        log.exception("The login-token sweep failed; leaving it for the next pass.")
        return 0


def interval():
    """Seconds between passes. A knob for testing, not a per-family setting.

    How often a *family's* calendars are refreshed is `refresh_minutes` in
    their own config, and `schedule.due` is what reads it. This only decides
    how often the worker asks the question.
    """
    try:
        return max(1, int(os.environ.get("DINKYDASH_WORKER_INTERVAL", DEFAULT_INTERVAL)))
    except ValueError:
        log.warning("DINKYDASH_WORKER_INTERVAL is not a number; using %s.",
                    DEFAULT_INTERVAL)
        return DEFAULT_INTERVAL


def main():  # pragma: no cover - the loop itself; tick_all is what is tested
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    from dinkydash import db, sentry

    # Before anything that can fail: a worker that cannot reach its database
    # is exactly the report worth having. A no-op without SENTRY_DSN.
    sentry.init("worker")

    stopping = Stopping()
    signal.signal(signal.SIGTERM, stopping.request)
    signal.signal(signal.SIGINT, stopping.request)

    pool = db.pool()
    every = interval()
    log.info("Worker started; a pass every %s seconds.", every)

    while not stopping:
        run_pass(pool, stopping)

        # Sleep in slices so SIGTERM is noticed in seconds rather than minutes.
        # App Platform kills a container that ignores it for too long, and
        # being killed is what the graceful stop exists to avoid.
        deadline = time.monotonic() + every
        while not stopping and time.monotonic() < deadline:
            time.sleep(min(1, max(0, deadline - time.monotonic())))

    log.info("Worker stopped.")
    return 0
