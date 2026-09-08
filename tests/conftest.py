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
    forget_ownerless_tokens(pool)
    yield pool
    pool.close()


def forget_ownerless_tokens(pool):
    """Delete every sign-up token, which nothing else will.

    A sign-up token has no `user_id` — that is the whole point of it (DIN-41),
    and it is why `login_tokens.user_id` became nullable. The consequence is
    that `ON DELETE CASCADE` from `families` does not reach one, so a test that
    posts an address and never clicks the link leaves a row behind that outlives
    its own database.

    In production the sweep takes it fifteen minutes later. Here the scratch
    database is reused between runs, so three abandoned sign-ups for one address
    silently exhaust `MOST_LIVE_LINKS` and the next run fails somewhere else
    entirely. Once when the pool is built, and again after every family.
    """
    with pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM login_tokens WHERE user_id IS NULL")


@pytest.fixture
def pg_family(pg_pool):
    """One empty family, and everything belonging to it removed afterwards.

    Returns its id. Truncating `families` cascades to every other table, which
    is also a live check that the foreign keys really do cascade — Phase 5's
    hard delete depends on exactly that.
    """
    from dinkydash import config as config_module

    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO families (screen_token, config)
                   VALUES (%s, '{}'::jsonb) RETURNING id""",
                # A real one, from `config.ID_ALPHABET`. It used to be
                # `"tok" + urandom(6).hex()`, which is a fine unique string and
                # is **not a token this app would ever issue** — hex has `0` and
                # `1` in it and the alphabet deliberately does not. Once
                # `/s/<token>` started refusing malformed tokens before querying
                # (DIN-42), a fixture token that could not exist made every
                # screen test fail for the wrong reason.
                (config_module.new_screen_token(),),
            )
            family_id = cur.fetchone()[0]
    yield family_id
    with pg_pool.connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM families WHERE id = %s", (family_id,))
    # Not part of that cascade, and not reachable from it — see above.
    forget_ownerless_tokens(pg_pool)


# -- a test client that behaves like a browser ------------------------------
#
# Every form the settings UI renders carries a CSRF token, and `web.session`
# refuses a write without one. There is deliberately no switch to turn that off
# — see the note in `check_csrf` — so the client below fills the field in the
# way a browser filling in a rendered form would.
#
# The effect is that all ~30 existing POSTs in the suite now go *through* the
# CSRF check rather than around it, which is the whole reason for doing it this
# way. A test that wants to see the check refuse something passes its own
# `csrf_token` (a wrong one, or none at all, via a plain `app.test_client()`).

from flask.testing import FlaskClient  # noqa: E402

CSRF_KEY = "csrf"
CSRF_FIELD = "csrf_token"


class SigningClient(FlaskClient):
    """A client that carries this session's CSRF token on every write."""

    WRITES = {"POST", "PUT", "PATCH", "DELETE"}

    def open(self, *args, **kwargs):
        if kwargs.get("method", "GET").upper() in self.WRITES:
            with self.session_transaction() as stored:
                token = stored.get(CSRF_KEY)
                if not token:
                    token = stored[CSRF_KEY] = "a-test-csrf-token"
            data = kwargs.get("data")
            if data is None:
                kwargs["data"] = {CSRF_FIELD: token}
            elif isinstance(data, dict):
                data.setdefault(CSRF_FIELD, token)
        return super().open(*args, **kwargs)


def board_path(pg_pool, family_id):
    """Where that family's board is served in cloud mode: `/s/<token>`.

    A wall panel cannot sign in, so the board moved off `/` (DIN-42) and `/`
    became the way in to the settings. Every test that used to GET `/` for a
    board in cloud mode goes through here instead.
    """
    from dinkydash import screens

    return f"/s/{screens.token_for(pg_pool, family_id)}"


def client_for(app):
    """`app.test_client()`, signing its writes. What every fixture here uses."""
    app.test_client_class = SigningClient
    app.config["TESTING"] = True
    return app.test_client()
