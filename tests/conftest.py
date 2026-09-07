"""Shared fixtures.

The only thing here is the Postgres one, because it is the only fixture that
needs a resource the test suite cannot invent for itself.

**A self-hoster's `pytest` must pass with no database.** So the Postgres tests
skip unless `DINKYDASH_TEST_DATABASE_URL` is set, and nothing here imports
psycopg at module level — psycopg lives in `requirements-cloud.txt`, which a Pi
never installs. CI sets the variable against a service container, so the parity
assertions really do run on every push.

    DINKYDASH_TEST_DATABASE_URL=postgresql:///dinkydash_test venv/bin/python -m pytest
"""

import os

import pytest

TEST_DATABASE_URL = "DINKYDASH_TEST_DATABASE_URL"


def database_url():
    return os.environ.get(TEST_DATABASE_URL)


@pytest.fixture(scope="session")
def pg_pool():
    """A pool against a freshly migrated scratch database, or a skip.

    Session-scoped: migrating once and truncating between tests is a great deal
    faster than rebuilding the schema per test, and truncation is the thing that
    actually has to be reliable.
    """
    url = database_url()
    if not url:
        pytest.skip(f"{TEST_DATABASE_URL} is not set")

    from dinkydash import db

    conn = db.connect(url)
    try:
        db.migrate(conn)
    finally:
        conn.close()

    pool = db.pool(url, min_size=1, max_size=2)
    pool.wait(timeout=10)
    yield pool
    pool.close()


@pytest.fixture
def pg_family(pg_pool):
    """One empty family, and everything belonging to it removed afterwards.

    Returns its id. Truncating `families` cascades to every other table, which
    is also a live check that the foreign keys really do cascade — Phase 5's
    hard delete depends on exactly that.
    """
    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO families (screen_token, config)
                   VALUES (%s, '{}'::jsonb) RETURNING id""",
                ("tok" + os.urandom(6).hex(),),
            )
            family_id = cur.fetchone()[0]
    yield family_id
    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM families WHERE id = %s", (family_id,))
