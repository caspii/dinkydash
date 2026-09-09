"""Upgrade existing spend without losing charges during a rolling deployment."""

from datetime import date


def test_backfill_and_old_writers_keep_a_non_identifying_total(pg_pool):
    from dinkydash import db

    # An isolated copy of the previous schema, removed by transaction rollback.
    with pg_pool.connection() as conn, conn.transaction(force_rollback=True):
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA spend_migration_test")
            cur.execute("SET LOCAL search_path TO spend_migration_test, public")
            upgrade = db.MIGRATIONS_DIR / "004_global_model_spend.sql"
            for path in db.migrations():
                if path == upgrade:
                    break
                cur.execute(path.read_text())
            cur.execute("""INSERT INTO families (screen_token)
                           VALUES ('migration-test-one'), ('migration-test-two') RETURNING id""")
            first, second = [row[0] for row in cur.fetchall()]
            today, yesterday = date(2026, 9, 9), date(2026, 9, 8)
            cur.executemany("INSERT INTO model_spend (day, family_id, calls) VALUES (%s, %s, %s)",
                            [(today, first, 3), (today, second, 5), (yesterday, first, 7)])
            cur.execute(upgrade.read_text())
            cur.execute("SELECT day, calls FROM global_model_spend ORDER BY day")
            assert cur.fetchall() == [(yesterday, 7), (today, 8)]

            # Existing app versions write only model_spend during rollout.
            cur.execute("""UPDATE model_spend SET calls = calls + 2
                           WHERE day = %s AND family_id = %s""", (today, first))
            cur.execute("UPDATE model_spend SET input_tokens = 1200, output_tokens = 90")
            with conn.transaction(force_rollback=True):
                cur.execute("UPDATE model_spend SET calls = calls + 1 WHERE day = %s", (today,))
            cur.execute("DELETE FROM families")
            cur.execute("SELECT * FROM global_model_spend ORDER BY day")
            assert [column.name for column in cur.description] == ["day", "calls"]
            assert cur.fetchall() == [(yesterday, 7), (today, 10)]
            cur.execute("SELECT count(*) FROM model_spend")
            assert cur.fetchone() == (0,)
