"""What `monitor.py` calls up, and what it calls down (DIN-54).

The script is the contract for "the hosted service is up", and the workflow
that runs it is only as good as these: a healthy service passes, a worker that
never ran or went quiet fails, a deploy that never arrives fails, and one
failing check never hides the others. Every fetch here is canned, every clock
is fake, and nothing reaches the network.
"""

import json

import pytest

import monitor

SITE, APP = "https://site.test", "https://app.test"
COMMIT = "924aedfbbfc1c768d5bbc9df8b3b3b90e605df80"


def healthy(commit=COMMIT):
    return {
        f"{SITE}/healthz": (200, json.dumps({"status": "ok", "commit": commit})),
        f"{SITE}/": (200, "<html>the site</html>"),
        f"{APP}/healthz": (200, json.dumps({"status": "ok", "commit": commit})),
        f"{APP}/login": (200, "<html>sign in</html>"),
        f"{APP}/healthz/worker": (200, json.dumps(
            {"status": "ok", "age_seconds": 61, "last_pass": {"families": 3}})),
    }


def answering(canned):
    """A fetch over canned `(status, body)` answers, recording what was asked."""
    asked = []

    def fetch(url, timeout=None):
        asked.append(url)
        return canned.get(url, (404, "not found"))

    fetch.asked = asked
    return fetch


def run(canned, **kwargs):
    """`monitor.run` against canned answers, with a clock that sleeping advances."""
    lines, now = [], [0.0]

    def sleep(seconds):
        now[0] += seconds

    fetch = answering(canned)
    status = monitor.run(SITE, APP, fetch=fetch, out=lines.append, sleep=sleep,
                         clock=lambda: now[0], **kwargs)
    return status, lines, fetch


def failures(lines):
    return [line for line in lines if line.startswith("FAIL")]


class TestAHealthyService:
    def test_every_check_passes_and_the_exit_status_is_zero(self):
        status, lines, _ = run(healthy())
        assert status == 0
        assert [line[:4] for line in lines] == ["PASS"] * 5

    def test_each_check_says_what_it_saw(self):
        _, lines, _ = run(healthy())
        assert any("site /healthz: ok, commit 924aedfbbfc1" in line for line in lines)
        assert any("app /healthz/worker: alive, last pass 61 s ago" in line for line in lines)

    def test_it_asks_for_exactly_the_five_paths(self):
        _, _, fetch = run(healthy())
        assert fetch.asked == [f"{SITE}/healthz", f"{SITE}/", f"{APP}/healthz",
                               f"{APP}/login", f"{APP}/healthz/worker"]


class TestWhatBringsItDown:
    def test_a_worker_that_never_ran(self):
        canned = healthy()
        canned[f"{APP}/healthz/worker"] = (503, json.dumps(
            {"status": "never", "age_seconds": None, "last_pass": None}))
        status, lines, _ = run(canned)
        assert status == 1
        assert failures(lines) == ["FAIL  app /healthz/worker: no pass has ever finished"]

    def test_a_worker_that_went_quiet(self):
        canned = healthy()
        canned[f"{APP}/healthz/worker"] = (503, json.dumps(
            {"status": "stale", "age_seconds": 1800, "last_pass": {}}))
        status, lines, _ = run(canned)
        assert status == 1
        assert failures(lines) == ["FAIL  app /healthz/worker: stale, last pass 1800 s ago"]

    def test_a_deploy_from_before_the_worker_status_existed(self):
        canned = healthy()
        canned[f"{APP}/healthz/worker"] = (404, "<html>not found</html>")
        status, lines, _ = run(canned)
        assert status == 1
        assert failures(lines) == ["FAIL  app /healthz/worker: HTTP 404"]

    def test_an_app_that_does_not_answer_at_all(self):
        canned = healthy()
        for path in ("/healthz", "/login", "/healthz/worker"):
            canned[f"{APP}{path}"] = (None, "URLError: [Errno 61] Connection refused")
        status, lines, _ = run(canned)
        assert status == 1
        assert len(failures(lines)) == 3
        assert "no answer (URLError: [Errno 61] Connection refused)" in failures(lines)[0]

    def test_a_marketing_page_that_500s(self):
        canned = healthy()
        canned[f"{SITE}/"] = (500, "<html>oops</html>")
        status, lines, _ = run(canned)
        assert status == 1
        assert failures(lines) == ["FAIL  site /: HTTP 500"]

    def test_a_health_path_that_answers_200_but_not_ok(self):
        canned = healthy()
        canned[f"{APP}/healthz"] = (200, json.dumps({"status": "degraded"}))
        status, lines, _ = run(canned)
        assert status == 1
        assert failures(lines) == ["FAIL  app /healthz: HTTP 200"]

    def test_a_health_path_that_is_not_json(self):
        canned = healthy()
        canned[f"{SITE}/healthz"] = (200, "<html>a maintenance page</html>")
        status, lines, _ = run(canned)
        assert status == 1
        assert failures(lines) == ["FAIL  site /healthz: HTTP 200"]

    def test_one_failure_does_not_hide_the_other_checks(self):
        canned = healthy()
        canned[f"{SITE}/"] = (500, "")
        _, lines, _ = run(canned)
        assert len(lines) == 5
        assert sum(line.startswith("PASS") for line in lines) == 4


class TestWaitingForACommit:
    def test_a_commit_that_is_already_live_is_a_pass_with_no_waiting(self):
        status, lines, _ = run(healthy(), commit=COMMIT, wait=900)
        assert status == 0
        assert lines[0] == f"PASS  commit {COMMIT[:12]} live on both hostnames"

    def test_a_short_prefix_of_the_commit_is_enough(self):
        status, _, _ = run(healthy(), commit=COMMIT[:7], wait=900)
        assert status == 0

    def test_it_polls_until_the_commit_arrives(self):
        looks, old = [], healthy("f2e4080aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        new = healthy()

        def fetch(url, timeout=None):
            looks.append(url)
            # The old release answers the first two rounds; the new one after.
            # Rounds are counted on the site, which is asked first every time.
            return (old if looks.count(f"{SITE}/healthz") <= 2 else new)[url]

        lines, now = [], [0.0]
        status = monitor.run(SITE, APP, commit=COMMIT, wait=900, fetch=fetch,
                             out=lines.append, sleep=lambda s: now.__setitem__(0, now[0] + s),
                             clock=lambda: now[0])
        assert status == 0
        assert lines[0].startswith("PASS  commit")
        assert now[0] == 2 * monitor.POLL

    def test_a_commit_that_never_arrives_fails_within_the_wait(self):
        status, lines, fetch = run(healthy("f2e4080aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
                                   commit=COMMIT, wait=900)
        assert status == 1
        assert lines[0] == f"FAIL  commit {COMMIT[:12]} live on both hostnames (not within 900 s)"
        # And the health checks say which release is actually running.
        assert "FAIL  app /healthz: running f2e4080aaaaa, not 924aedfbbfc1" in lines
        # It gave up on the clock, not on a number of tries.
        assert fetch.asked.count(f"{SITE}/healthz") >= 900 // monitor.POLL

    def test_with_no_wait_the_commit_is_still_checked_once(self):
        status, lines, _ = run(healthy("f2e4080aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"), commit=COMMIT)
        assert status == 1
        assert not lines[0].endswith("hostnames")
        assert len(failures(lines)) == 2


class TestTheCommandLine:
    def test_the_defaults_are_the_live_service(self):
        args = monitor.parse([])
        assert (args.site, args.app) == ("https://dinkydash.co", "https://app.dinkydash.co")
        assert args.commit is None and args.wait == 0

    def test_a_local_drill_names_its_own_hosts(self):
        args = monitor.parse(["--site", "http://localhost:5173/",
                              "--app", "http://127.0.0.1:5173/",
                              "--commit", "abc", "--wait", "30"])
        assert (args.site, args.app) == ("http://localhost:5173", "http://127.0.0.1:5173")
        assert (args.commit, args.wait) == ("abc", 30)

    def test_it_imports_nothing_outside_the_standard_library(self):
        """The workflow runs it on a bare runner with no `pip install`."""
        import sys
        from pathlib import Path
        source = Path(monitor.__file__).read_text()
        imported = {line.split()[1].split(".")[0] for line in source.splitlines()
                    if line.startswith(("import ", "from "))}
        assert imported <= set(sys.stdlib_module_names)

    @pytest.mark.parametrize("body", ["", "null", "[1, 2]", "{not json"])
    def test_an_odd_body_is_not_a_crash(self, body):
        assert monitor._json(body) == {}
