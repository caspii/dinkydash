"""What the cloud tick loop must do, and what one bad family must not do to the rest.

The loop itself is not tested — a `while True` with a sleep in it is not worth
a fake clock. `tick_all` is, because it holds the decisions: which families are
walked, what happens when one of them raises, and what reaches a log when it
does. `run_pass` is, because it decides what a check-in means (DIN-54).

Nothing here needs Postgres. `tick_all` takes its store factory and its tick
function as arguments, and `run_pass` its check-in, so the fakes below are the
whole test rig.
"""

import logging

import pytest

import worker
from dinkydash.budget import NoBudget
from worker import DEFAULT_INTERVAL, Pass, Stopping, interval, run_pass, tick_all


class FakePool:
    """A psycopg-shaped pool returning fixed rows for the family query."""

    def __init__(self, ids):
        self.ids, self.sql = ids, []

    def connection(self):
        return self

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, *args):
        self.sql.append(sql)

    def fetchall(self):
        return [(i,) for i in self.ids]


class FakeStore:
    def __init__(self, family_id):
        self.family_id = family_id

    def load_config(self):
        return {"family_id": self.family_id}


class FakeBudget(NoBudget):
    """An unrestricted test budget labelled with its family."""

    def __init__(self, family_id):
        self.family_id = family_id

def run(ids, tick, stopping=None, budget_factory=FakeBudget):
    """`tick_all` with every seam filled by a fake.

    The tick signature is `(config, store, budget=...)`, so the lambdas below
    take a `budget` keyword whether or not they look at it — the point of
    passing one at all is that a family's spend is decided per family, out here
    where the pool and the id are both known (DIN-43).
    """
    return tick_all(FakePool(ids), store_factory=FakeStore, tick=tick,
                    stopping=stopping, budget_factory=budget_factory)


class TestWalkingTheFamilies:
    def test_every_family_is_ticked(self):
        seen = []
        done = run(["a", "b", "c"], lambda config, store, budget=None: seen.append(store.family_id))
        assert seen == ["a", "b", "c"]
        assert done == Pass(ticked=3, failed=0)

    def test_no_families_is_not_an_error(self):
        assert run([], lambda config, store, budget=None: None) == Pass(0, 0)

    def test_the_config_comes_from_that_family_s_store(self):
        configs = []
        run(["a", "b"], lambda config, store, budget=None: configs.append(config))
        assert configs == [{"family_id": "a"}, {"family_id": "b"}]

    def test_lapsed_families_are_excluded_by_the_query(self):
        """PLAN.md's freeze: the board keeps its last state, the ticking stops."""
        pool = FakePool(["a"])
        tick_all(pool, store_factory=FakeStore, tick=lambda c, s: None)
        assert "status <> 'lapsed'" in " ".join(pool.sql)


class TestOneBadFamily:
    def test_a_raising_family_does_not_stop_the_others(self):
        """A shared worker that dies on the noisiest tenant serves the quietest worst."""
        seen = []

        def tick(config, store, budget=None):
            seen.append(store.family_id)
            if store.family_id == "b":
                raise RuntimeError("their calendar feed is down")

        done = run(["a", "b", "c"], tick)
        assert seen == ["a", "b", "c"]
        assert done == Pass(ticked=2, failed=1)

    def test_every_family_can_fail_without_raising(self):
        def tick(config, store, budget=None):
            raise RuntimeError("everything is down")

        assert run(["a", "b"], tick) == Pass(ticked=0, failed=2)

    def test_the_failure_log_names_the_id_and_not_the_config(self, caplog):
        """A config holds children's names, and a calendar URL is a password."""
        def tick(config, store, budget=None):
            raise RuntimeError("failed fetching https://cal.example/private-abc123/basic.ics")

        with caplog.at_level(logging.DEBUG):
            run(["fam-42"], tick)
        logged = " ".join(r.getMessage() for r in caplog.records)
        assert "fam-42" in logged
        assert "private-abc123" not in logged


class TestStopping:
    def test_a_stop_request_ends_the_pass_between_families(self):
        """SIGTERM during a redeploy must not cut a paid-for brief in half."""
        stopping = Stopping()
        seen = []

        def tick(config, store, budget=None):
            seen.append(store.family_id)
            stopping.request()

        done = run(["a", "b", "c"], tick, stopping=stopping)
        assert seen == ["a"]
        assert done == Pass(ticked=1, failed=0)

    def test_a_fresh_stopping_is_falsey(self):
        assert not Stopping()

    def test_requesting_makes_it_truthy(self):
        s = Stopping()
        s.request()
        assert s


class TestTheCheckIn:
    """A check-in means a pass finished — not that every family succeeded (DIN-54).

    `run_pass` is the only place that knows whether a pass finished, so it is
    the only place that checks in. Everything it calls is replaced by a fake
    that records the order; the pool is any object, because none of the fakes
    look at it.
    """

    @pytest.fixture
    def rig(self, monkeypatch):
        calls, check_ins = [], []
        monkeypatch.setenv("DINKYDASH_WORKER_INTERVAL", "300")
        monkeypatch.setattr("dinkydash.lifecycle.expire_trials",
                            lambda pool: calls.append("expire") or 0)
        monkeypatch.setattr(worker, "tick_all",
                            lambda pool, stopping=None: calls.append("tick") or Pass(2, 1))
        monkeypatch.setattr(worker, "sweep_logins",
                            lambda pool: calls.append("sweep") or 0)

        def check_in(every, took):
            calls.append("check_in")
            check_ins.append((every, took))

        return calls, check_ins, check_in

    def test_a_completed_pass_checks_in_last_with_the_interval_and_its_duration(self, rig):
        calls, check_ins, check_in = rig
        assert run_pass(object(), Stopping(), check_in=check_in) == Pass(2, 1)
        assert calls == ["expire", "tick", "sweep", "check_in"]
        ((every, took),) = check_ins
        assert every == 300
        assert took >= 0

    def test_a_pass_in_which_every_family_failed_is_still_a_live_worker(self, rig, monkeypatch):
        """Failed work is a Sentry event of its own; a dead worker is a different thing."""
        calls, check_ins, check_in = rig
        monkeypatch.setattr(worker, "tick_all",
                            lambda pool, stopping=None: calls.append("tick") or Pass(0, 3))
        assert run_pass(object(), Stopping(), check_in=check_in) == Pass(0, 3)
        assert len(check_ins) == 1

    def test_an_interrupted_pass_does_not_check_in(self, rig, monkeypatch):
        """A stop request mid-walk is a redeploy, not a finished pass."""
        calls, check_ins, check_in = rig
        stopping = Stopping()

        def interrupted(pool, stopping=None):
            calls.append("tick")
            stopping.request()
            return Pass(1, 0)

        monkeypatch.setattr(worker, "tick_all", interrupted)
        assert run_pass(object(), stopping, check_in=check_in) is None
        assert "check_in" not in calls
        assert check_ins == []

    def test_a_pass_that_cannot_list_the_families_neither_checks_in_nor_raises(
            self, rig, monkeypatch, caplog):
        """A dead database is the usual cause. The worker keeps looping, the
        check-in goes missed, and missed is the alert."""
        calls, check_ins, check_in = rig

        def dead(pool, stopping=None):
            calls.append("tick")
            raise RuntimeError("connection failed")

        monkeypatch.setattr(worker, "tick_all", dead)
        with caplog.at_level(logging.ERROR):
            assert run_pass(object(), Stopping(), check_in=check_in) is None
        assert calls == ["expire", "tick"]
        assert "next pass" in caplog.text

    def test_a_check_in_that_cannot_be_sent_does_not_stop_the_worker(self, rig, caplog):
        calls, check_ins, _ = rig

        def broken(every, took):
            raise RuntimeError("no route to host")

        with caplog.at_level(logging.ERROR):
            assert run_pass(object(), Stopping(), check_in=broken) == Pass(2, 1)
        assert "check-in" in caplog.text.lower()

    def test_housekeeping_failing_does_not_stop_the_pass_or_the_check_in(self, rig, monkeypatch):
        calls, check_ins, check_in = rig
        monkeypatch.setattr("dinkydash.lifecycle.expire_trials",
                            lambda pool: (_ for _ in ()).throw(RuntimeError("no")))
        assert run_pass(object(), Stopping(), check_in=check_in) == Pass(2, 1)
        assert calls[-1] == "check_in"

    def test_no_stopping_at_all_is_a_pass_that_finishes(self, rig):
        calls, check_ins, check_in = rig
        assert run_pass(object(), check_in=check_in) == Pass(2, 1)
        assert len(check_ins) == 1

    def test_the_real_check_in_is_the_default(self, rig, monkeypatch):
        calls, check_ins, _ = rig
        monkeypatch.setattr("dinkydash.sentry.check_in",
                            lambda every, took: check_ins.append("real"))
        run_pass(object(), Stopping())
        assert check_ins == ["real"]

    def test_the_default_check_in_is_a_no_op_without_a_dsn(self, rig, monkeypatch):
        """No DSN, no network: the pass finishes and nothing is reached for."""
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        monkeypatch.setattr("dinkydash.sentry._enabled", False)
        assert run_pass(object(), Stopping()) == Pass(2, 1)


class TestInterval:
    def test_it_defaults_to_five_minutes(self, monkeypatch):
        monkeypatch.delenv("DINKYDASH_WORKER_INTERVAL", raising=False)
        assert interval() == DEFAULT_INTERVAL == 300

    def test_the_environment_overrides_it(self, monkeypatch):
        monkeypatch.setenv("DINKYDASH_WORKER_INTERVAL", "30")
        assert interval() == 30

    def test_nonsense_falls_back_rather_than_crashing(self, monkeypatch):
        """A typo in an app spec must not stop every family's board updating."""
        monkeypatch.setenv("DINKYDASH_WORKER_INTERVAL", "five minutes")
        assert interval() == DEFAULT_INTERVAL

    @pytest.mark.parametrize("value", ["0", "-10"])
    def test_it_never_busy_loops(self, monkeypatch, value):
        monkeypatch.setenv("DINKYDASH_WORKER_INTERVAL", value)
        assert interval() >= 1
