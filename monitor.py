#!/usr/bin/env python3
"""Is the hosted service up, on the commit it should be, with a worker still ticking?

    python monitor.py                                 # the live service, now
    python monitor.py --commit <sha> --wait 900       # after a deploy: wait for that commit first
    python monitor.py --site http://localhost:5173 --app http://127.0.0.1:5173
                                                      # a local drill (doc/operations.md)

One line per check, and exit status 0 only when every check passed. This is
what `.github/workflows/monitor.yml` runs every fifteen minutes and after every
push to `main`; a failed run there is the alert (DIN-54).

**Why a script rather than a curl one-liner.** The checks are the contract —
what "up" means for this service — and a contract written in a workflow file
is a contract nobody tests. `tests/test_monitor.py` runs these against canned
answers: a worker that never ran, a stale one, a deploy that never arrives.

**Why the standard library.** The workflow runs on a bare runner with no
`pip install`, so this imports nothing the interpreter did not come with.

What it checks, and why each one is there:

* the marketing site answers `/` and `/healthz` — the pages that rank;
* the app answers `/healthz` and `/login` — the process is up and a page
  renders. `/login` needs no database, so it is a check on the code, not the
  cluster;
* the app answers `/healthz/worker` with 200 — a pass finished recently, which
  is the only thing that says the worker is alive, and it reads the database,
  which is the only thing here that says the app can reach it;
* with `--commit`, both `/healthz` report that commit — the deploy that was
  pushed is the deploy that is live. App Platform builds for several minutes
  after a push, so this is polled until it is true or `--wait` runs out.

Nothing here carries a secret, and nothing it reads is anybody's data.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

SITE = "https://dinkydash.co"
APP = "https://app.dinkydash.co"

TIMEOUT = 15   # seconds per request; a health path that takes longer is down
POLL = 20      # seconds between looks while waiting for a commit to go live


def fetch(url, timeout=TIMEOUT):
    """`(status, body)` for a GET. An HTTP error is a status; no answer is `None`."""
    request = urllib.request.Request(url, headers={"User-Agent": "dinkydash-monitor"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"


# -- the checks: each returns (passed, one line of detail) --------------------

def healthz(fetch, base, commit=None):
    """The process answers, and — if asked — it is running that commit."""
    status, body = fetch(base + "/healthz")
    said = _json(body)
    if status != 200 or said.get("status") != "ok":
        return False, _what_came_back(status, body)
    running = str(said.get("commit", "unknown"))
    if commit and not running.startswith(commit):
        return False, f"running {running[:12]}, not {commit[:12]}"
    return True, f"ok, commit {running[:12]}"


def page(fetch, url):
    """A page renders."""
    status, body = fetch(url)
    return status == 200, _what_came_back(status, body)


def worker(fetch, base):
    """A pass finished recently — the worker is alive and the app can reach the database."""
    status, body = fetch(base + "/healthz/worker")
    said = _json(body)
    state, age = said.get("status"), said.get("age_seconds")
    if status == 200 and state == "ok":
        return True, f"alive, last pass {age} s ago"
    if state == "never":
        return False, "no pass has ever finished"
    if state == "stale":
        return False, f"stale, last pass {age} s ago"
    return False, _what_came_back(status, body)


def wait_for(fetch, bases, commit, wait, sleep=time.sleep, clock=time.monotonic):
    """Poll until every base's `/healthz` reports `commit`, or `wait` seconds pass."""
    deadline = clock() + wait
    while True:
        if all(healthz(fetch, base, commit)[0] for base in bases):
            return True
        if clock() >= deadline:
            return False
        sleep(POLL)


def run(site=SITE, app=APP, commit=None, wait=0, fetch=fetch,
        sleep=time.sleep, clock=time.monotonic, out=print):
    """Every check, one line each. Returns the exit status."""
    failed = 0
    if commit and wait:
        arrived = wait_for(fetch, (site, app), commit, wait, sleep, clock)
        failed += not arrived
        out(f"{'PASS' if arrived else 'FAIL'}  commit {commit[:12]} live on both "
            f"hostnames{'' if arrived else f' (not within {wait} s)'}")

    checks = (
        ("site /healthz", lambda: healthz(fetch, site, commit)),
        ("site /", lambda: page(fetch, site + "/")),
        ("app /healthz", lambda: healthz(fetch, app, commit)),
        ("app /login", lambda: page(fetch, app + "/login")),
        ("app /healthz/worker", lambda: worker(fetch, app)),
    )
    for name, check in checks:
        passed, detail = check()
        failed += not passed
        out(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")
    return 0 if not failed else 1


def _json(body):
    try:
        said = json.loads(body)
    except (TypeError, ValueError):
        return {}
    return said if isinstance(said, dict) else {}


def _what_came_back(status, body):
    """A status code, or the transport error when there was no status at all."""
    if status is None:
        return f"no answer ({body})"
    return f"HTTP {status}"


def parse(argv=None):
    parser = argparse.ArgumentParser(
        description="Check the hosted service: the site, the app, the worker.")
    parser.add_argument("--site", default=SITE, help=f"the marketing site (default {SITE})")
    parser.add_argument("--app", default=APP, help=f"the app (default {APP})")
    parser.add_argument("--commit", help="the commit both /healthz must report")
    parser.add_argument("--wait", type=int, default=0,
                        help="seconds to wait for --commit to go live before checking")
    args = parser.parse_args(argv)
    args.site, args.app = args.site.rstrip("/"), args.app.rstrip("/")
    return args


def main(argv=None):
    args = parse(argv)
    return run(args.site, args.app, args.commit, args.wait)


if __name__ == "__main__":
    sys.exit(main())
