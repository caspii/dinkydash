"""The worker's pulse: what a heartbeat means, and what its row may hold (DIN-54).

* **the verdict is pure.** `ok`, `stale` or `never` from a row, a clock and an
  allowance, with no database and no clock of its own;
* **failed work is not a dead worker.** A pass in which every family raised
  still beat; the count is carried, the verdict is `ok`;
* **one row, overwritten**, and nothing in it names a family.

The verdict tests run everywhere; the row tests skip without
`DINKYDASH_TEST_DATABASE_URL`.
"""

from datetime import datetime, timedelta, timezone

import pytest

from dinkydash import heartbeat
from tests.conftest import forget_unowned_rows

NOW = datetime(2026, 9, 10, 20, 0, tzinfo=timezone.utc)


def row(age_seconds, families=3, failed=0, took_ms=1200):
    return {"passed_at": NOW - timedelta(seconds=age_seconds),
            "families": families, "failed": failed, "took_ms": took_ms}


class TestTheVerdict:
    def test_no_row_is_never(self):
        assert heartbeat.verdict(None, NOW) == {
            "status": "never", "age_seconds": None, "last_pass": None}

    @pytest.mark.parametrize("age", [0, 1, 299, 899, 900])
    def test_within_the_allowance_is_ok(self, age):
        said = heartbeat.verdict(row(age), NOW)
        assert said["status"] == "ok"
        assert said["age_seconds"] == age

    @pytest.mark.parametrize("age", [901, 3600, 86400 * 3])
    def test_beyond_it_is_stale(self, age):
        said = heartbeat.verdict(row(age), NOW)
        assert said["status"] == "stale"
        assert said["age_seconds"] == age

    def test_the_default_allowance_is_three_missed_passes(self):
        assert heartbeat.DEFAULT_STALE_AFTER == 900

    def test_the_allowance_is_a_parameter(self):
        assert heartbeat.verdict(row(100), NOW, stale_after=60)["status"] == "stale"
        assert heartbeat.verdict(row(100), NOW, stale_after=100)["status"] == "ok"

    def test_a_heartbeat_from_the_future_is_age_zero_and_not_an_error(self):
        """Two clocks disagreeing by a few seconds is not a worker from tomorrow."""
        said = heartbeat.verdict(row(-30), NOW)
        assert said == {**said, "status": "ok", "age_seconds": 0}

    def test_failed_families_do_not_make_a_live_worker_stale(self):
        said = heartbeat.verdict(row(10, families=3, failed=3), NOW)
        assert said["status"] == "ok"
        assert said["last_pass"]["failed"] == 3

    def test_it_carries_the_pass_for_the_operators_page(self):
        said = heartbeat.verdict(row(61, families=4, failed=1, took_ms=2500), NOW)
        assert said["last_pass"] == {
            "passed_at": "2026-09-10T19:58:59+00:00",
            "families": 4, "failed": 1, "took_ms": 2500}


# -- the row, in Postgres ----------------------------------------------------

@pytest.fixture
def pool(pg_pool):
    """The shared pool, with no heartbeat before the test and none left after."""
    forget_unowned_rows(pg_pool)
    yield pg_pool
    forget_unowned_rows(pg_pool)


class TestTheRow:
    def test_no_pass_yet_is_none(self, pool):
        assert heartbeat.last(pool) is None

    def test_a_beat_round_trips(self, pool):
        heartbeat.beat(pool, 3, 1, 1234, now=NOW)
        assert heartbeat.last(pool) == {
            "passed_at": NOW, "families": 3, "failed": 1, "took_ms": 1234}

    def test_a_beat_with_no_clock_given_is_now(self, pool):
        before = datetime.now(timezone.utc)
        heartbeat.beat(pool, 0, 0, 0)
        assert heartbeat.last(pool)["passed_at"] >= before - timedelta(seconds=1)

    def test_a_second_beat_overwrites_rather_than_accumulates(self, pool):
        heartbeat.beat(pool, 3, 1, 1234, now=NOW)
        heartbeat.beat(pool, 5, 0, 800, now=NOW + timedelta(minutes=5))
        assert heartbeat.last(pool) == {
            "passed_at": NOW + timedelta(minutes=5), "families": 5, "failed": 0,
            "took_ms": 800}
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM worker_heartbeat")
            assert cur.fetchone()[0] == 1

    def test_negative_counts_are_clamped_rather_than_refused(self, pool):
        """The table checks its counts; a bad number must not become a pass
        with no heartbeat, which would look like a dead worker."""
        heartbeat.beat(pool, -1, -1, -5, now=NOW)
        assert heartbeat.last(pool) == {
            "passed_at": NOW, "families": 0, "failed": 0, "took_ms": 0}

    def test_the_row_names_no_family(self, pool):
        with pool.connection() as conn, conn.cursor() as cur:
            cur.execute("""SELECT column_name FROM information_schema.columns
                           WHERE table_name = 'worker_heartbeat'""")
            columns = {name for (name,) in cur.fetchall()}
        assert columns == {"name", "passed_at", "families", "failed", "took_ms"}
