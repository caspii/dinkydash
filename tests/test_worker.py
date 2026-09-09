"""What the cloud tick loop must do, and what one bad family must not do to the rest.

The loop itself is not tested — a `while True` with a sleep in it is not worth
a fake clock. `tick_all` is, because it holds the decisions: which families are
walked, what happens when one of them raises, and what reaches a log when it
does.

Nothing here needs Postgres. `tick_all` takes its store factory and its tick
function as arguments, so the fakes below are the whole test rig.
"""

import logging

import pytest

from dinkydash.budget import NoBudget
from worker import DEFAULT_INTERVAL, Stopping, interval, tick_all


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
        assert done == 3

    def test_no_families_is_not_an_error(self):
        assert run([], lambda config, store, budget=None: None) == 0

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
        assert done == 2

    def test_every_family_can_fail_without_raising(self):
        def tick(config, store, budget=None):
            raise RuntimeError("everything is down")

        assert run(["a", "b"], tick) == 0

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
        assert done == 1

    def test_a_fresh_stopping_is_falsey(self):
        assert not Stopping()

    def test_requesting_makes_it_truthy(self):
        s = Stopping()
        s.request()
        assert s


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
