"""Signups and activations: counted once each, and kept after deletion (DIN-37).

Four claims:

* **a signup is a family created**, counted by the row appearing, whatever
  made it — the click on the emailed link in production, plain SQL here;
* **an activation is the first calendar link saved**, and it counts once.
  Removing the calendar and adding it back is not a second activation, and a
  calendar with no link in it is not one at all;
* **deleting the family leaves both counts where they were**, the way the
  spend total does (DIN-49), and the row that survives has no family in it;
* **the migration backfills** what can be known about the families that
  predate it, and a family created while the old code is still running is
  counted exactly once.

The roll-up is pure and is tested with no database. The rest skips without
`DINKYDASH_TEST_DATABASE_URL`, like the rest of the Postgres half.
"""

from datetime import date

import pytest

from dinkydash import growth

A_CALENDAR = {"id": "cal12345", "label": "School",
              "url": "https://example.com/private-xxxx/basic.ics", "enabled": True}


# -- the roll-up, with no database in sight ---------------------------------

class TestByWeek:
    TODAY = date(2026, 9, 10)  # a Thursday; its week starts Monday the 7th

    def test_every_week_in_the_span_is_present_even_when_empty(self):
        weeks = growth.by_week([], 4, self.TODAY)
        assert [w.start for w in weeks] == [date(2026, 8, 17), date(2026, 8, 24),
                                            date(2026, 8, 31), date(2026, 9, 7)]
        assert all((w.signups, w.activations) == (0, 0) for w in weeks)

    def test_a_day_lands_in_the_week_of_its_monday(self):
        rows = [(date(2026, 9, 6), 2, 1),   # a Sunday: the week of 31 August
                (date(2026, 9, 7), 3, 0)]   # a Monday: this week
        by_start = {w.start: w for w in growth.by_week(rows, 4, self.TODAY)}
        assert by_start[date(2026, 8, 31)][1:] == (2, 1)
        assert by_start[date(2026, 9, 7)][1:] == (3, 0)

    def test_days_in_one_week_add_up(self):
        rows = [(date(2026, 9, 7), 1, 0), (date(2026, 9, 8), 2, 1), (date(2026, 9, 10), 0, 1)]
        latest = growth.by_week(rows, 1, self.TODAY)[-1]
        assert (latest.signups, latest.activations) == (3, 2)

    def test_a_day_before_the_span_is_left_out(self):
        rows = [(date(2026, 8, 16), 9, 9)]  # the Sunday before a 4-week span
        assert all(w.signups == 0 for w in growth.by_week(rows, 4, self.TODAY))

    def test_a_day_after_today_is_left_out_too(self):
        # A clock skew or a hand-edited row must not invent a future column.
        rows = [(date(2026, 9, 14), 5, 5)]
        weeks = growth.by_week(rows, 2, self.TODAY)
        assert weeks[-1].start == date(2026, 9, 7)
        assert all(w.signups == 0 for w in weeks)

    def test_oldest_first_and_the_latest_week_is_last(self):
        weeks = growth.by_week([], 12, self.TODAY)
        assert len(weeks) == 12
        assert weeks == sorted(weeks)
        assert weeks[-1].start == date(2026, 9, 7)

    def test_totals_count_everything_whatever_the_span(self):
        rows = [(date(2025, 1, 1), 4, 1), (date(2026, 9, 10), 1, 1)]
        assert growth.totals(rows) == (5, 2)
        assert growth.totals([]) == (0, 0)


# -- the counter, in Postgres ------------------------------------------------

def counts(pool):
    """`{day: (signups, activations)}`, straight from the table."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT day, signups, activations FROM growth_by_day")
        return {day: (s, a) for day, s, a in cur.fetchall()}


def today(pool):
    """The database's UTC date, which is the one the trigger stamps with."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT (now() AT TIME ZONE 'UTC')::date")
        return cur.fetchone()[0]


def activated_at(pool, family_id):
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT activated_at FROM families WHERE id = %s", (family_id,))
        return cur.fetchone()[0]


def a_family(pool, config="{}"):
    from dinkydash import config as config_module
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("INSERT INTO families (screen_token, config) VALUES (%s, %s::jsonb) "
                    "RETURNING id", (config_module.new_screen_token(), config))
        return cur.fetchone()[0]


def forget(pool, family_id):
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM families WHERE id = %s", (family_id,))


@pytest.fixture
def store(pg_pool, pg_family):
    from dinkydash.pgstore import PostgresStore
    return PostgresStore(pg_pool, pg_family)


class TestTheCounter:
    def test_a_new_family_is_a_signup_today_and_nothing_else(self, pg_pool):
        day = today(pg_pool)
        before = counts(pg_pool).get(day, (0, 0))
        family_id = a_family(pg_pool)
        try:
            assert counts(pg_pool)[day] == (before[0] + 1, before[1])
            assert activated_at(pg_pool, family_id) is None
        finally:
            forget(pg_pool, family_id)

    def test_saving_a_calendar_is_an_activation(self, pg_pool, pg_family, store):
        day = today(pg_pool)
        before = counts(pg_pool).get(day, (0, 0))
        config = store.load_config()
        config["calendars"] = [dict(A_CALENDAR)]
        store.save_config(config)
        assert counts(pg_pool)[day] == (before[0], before[1] + 1)
        assert activated_at(pg_pool, pg_family) is not None

    def test_an_activation_counts_once(self, pg_pool, pg_family, store):
        config = store.load_config()
        config["calendars"] = [dict(A_CALENDAR)]
        store.save_config(config)
        first = activated_at(pg_pool, pg_family)
        after_one = counts(pg_pool)

        # A second calendar, then none at all, then one again.
        config["calendars"].append(dict(A_CALENDAR, id="cal67890", label="Swimming"))
        store.save_config(config)
        config["calendars"] = []
        store.save_config(config)
        config["calendars"] = [dict(A_CALENDAR)]
        store.save_config(config)

        assert counts(pg_pool) == after_one
        assert activated_at(pg_pool, pg_family) == first

    def test_a_calendar_with_no_link_is_not_an_activation(self, pg_pool, pg_family, store):
        before = counts(pg_pool)
        config = store.load_config()
        config["calendars"] = [{"id": "cal12345", "label": "School", "url": "", "enabled": True}]
        store.save_config(config)
        assert counts(pg_pool) == before
        assert activated_at(pg_pool, pg_family) is None

    def test_an_odd_document_does_not_break_the_save(self, pg_pool, pg_family):
        """A trigger that raised here would be a 500 on somebody's settings page."""
        before = counts(pg_pool)
        with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            for odd in ('{"calendars": "nonsense"}', '{"calendars": {"url": "x"}}',
                        '{"calendars": [1, "two", null]}', '{"calendars": null}', '{}'):
                cur.execute("UPDATE families SET config = %s::jsonb WHERE id = %s",
                            (odd, pg_family))
        assert counts(pg_pool) == before
        assert activated_at(pg_pool, pg_family) is None

    def test_a_family_born_with_a_calendar_is_both_at_once(self, pg_pool):
        day = today(pg_pool)
        before = counts(pg_pool).get(day, (0, 0))
        family_id = a_family(pg_pool, '{"calendars": [{"url": "https://example.com/x.ics"}]}')
        try:
            assert counts(pg_pool)[day] == (before[0] + 1, before[1] + 1)
            assert activated_at(pg_pool, family_id) is not None
        finally:
            forget(pg_pool, family_id)

    def test_deleting_the_family_changes_nothing(self, pg_pool):
        family_id = a_family(pg_pool, '{"calendars": [{"url": "https://example.com/x.ics"}]}')
        after = counts(pg_pool)
        forget(pg_pool, family_id)
        assert counts(pg_pool) == after

    def test_the_hard_delete_changes_nothing_either(self, pg_pool, pg_family, store):
        """`accounts.delete_family` is what the account page calls."""
        from dinkydash import accounts

        config = store.load_config()
        config["calendars"] = [dict(A_CALENDAR)]
        store.save_config(config)
        after = counts(pg_pool)
        assert accounts.delete_family(pg_pool, pg_family)
        assert counts(pg_pool) == after

    def test_the_table_holds_a_date_and_two_counts_and_nothing_else(self, pg_pool):
        with pg_pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM growth_by_day LIMIT 0")
            assert [c.name for c in cur.description] == ["day", "signups", "activations"]

    def test_history_is_the_table_oldest_first(self, pg_pool):
        with pg_pool.connection() as conn, conn.transaction(), conn.cursor() as cur:
            cur.execute("DELETE FROM growth_by_day")
            cur.executemany("INSERT INTO growth_by_day VALUES (%s, %s, %s)",
                            [(date(2026, 9, 9), 2, 1), (date(2026, 9, 1), 1, 0)])
        assert growth.history(pg_pool) == [(date(2026, 9, 1), 1, 0), (date(2026, 9, 9), 2, 1)]

    def test_families_now_is_a_count_of_rows(self, pg_pool):
        before = growth.families_now(pg_pool)
        family_id = a_family(pg_pool)
        try:
            assert growth.families_now(pg_pool) == before + 1
        finally:
            forget(pg_pool, family_id)
        assert growth.families_now(pg_pool) == before


# -- the migration, over a schema that predates it --------------------------

def test_the_migration_backfills_and_then_counts_exactly_once(pg_pool):
    from dinkydash import db

    # An isolated copy of the previous schema, removed by transaction rollback,
    # the way tests/test_spend_migration.py does it.
    with pg_pool.connection() as conn, conn.transaction(force_rollback=True):
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA growth_migration_test")
            cur.execute("SET LOCAL search_path TO growth_migration_test, public")
            upgrade = db.MIGRATIONS_DIR / "006_growth.sql"
            for path in db.migrations():
                if path == upgrade:
                    break
                cur.execute(path.read_text())

            # Three families from before the counter existed: one never set up,
            # one with a calendar saved on the 5th, one with a link-less entry.
            cur.executemany(
                """INSERT INTO families (screen_token, config, created_at, updated_at)
                   VALUES (%s, %s::jsonb, %s, %s)""",
                [("growth-test-one", '{}', "2026-09-01 10:00+00", "2026-09-01 10:00+00"),
                 ("growth-test-two",
                  '{"calendars": [{"label": "School", "url": "https://example.com/a.ics"}]}',
                  "2026-09-02 10:00+00", "2026-09-05 10:00+00"),
                 ("growth-test-thr", '{"calendars": [{"label": "Empty", "url": ""}]}',
                  "2026-09-02 11:00+00", "2026-09-02 11:00+00")])
            cur.execute(upgrade.read_text())

            cur.execute("SELECT day, signups, activations FROM growth_by_day ORDER BY day")
            assert cur.fetchall() == [(date(2026, 9, 1), 1, 0), (date(2026, 9, 2), 2, 0),
                                      (date(2026, 9, 5), 0, 1)]
            cur.execute("SELECT screen_token, activated_at = updated_at FROM families "
                        "WHERE activated_at IS NOT NULL")
            assert cur.fetchall() == [("growth-test-two", True)]

            # From here on the trigger is in charge: the link-less family pastes
            # a real link, and a fourth family signs up.
            cur.execute("SELECT (now() AT TIME ZONE 'UTC')::date")
            day = cur.fetchone()[0]
            cur.execute("""UPDATE families
                           SET config = '{"calendars": [{"url": "https://example.com/b.ics"}]}'
                           WHERE screen_token = 'growth-test-thr'""")
            cur.execute("INSERT INTO families (screen_token) VALUES ('growth-test-fou')")
            cur.execute("SELECT signups, activations FROM growth_by_day WHERE day = %s", (day,))
            assert cur.fetchone() == (1, 1)

            # And nothing is ever subtracted.
            cur.execute("DELETE FROM families")
            cur.execute("SELECT sum(signups), sum(activations) FROM growth_by_day")
            assert cur.fetchone() == (4, 2)
