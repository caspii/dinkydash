"""Connections and migrations. The only module that imports psycopg.

Cloud mode only. Single mode never imports this, which is what keeps a
Raspberry Pi from installing a Postgres driver it will never open — psycopg
lives in `requirements-cloud.txt`, not `requirements.txt`.

Two connection strings, and the difference matters (PLAN.md, Connection
pooling):

    DATABASE_URL         DigitalOcean's connection pool, transaction mode.
                         What `web` and `worker` use, through `pool()` below.
    DATABASE_URL_DIRECT  The cluster itself. What migrations and pg_dump use.
                         CREATE INDEX CONCURRENTLY cannot run inside a
                         transaction block, and pg_dump errors against a
                         transaction-mode pool.
"""

import logging
import os
import re
from pathlib import Path

import psycopg
from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

# A migration whose text carries this marker is applied outside a transaction,
# because some statements refuse to run inside one. CREATE INDEX CONCURRENTLY is
# the reason it exists: on a live table it is the difference between a fast index
# and locking out every family while it builds.
NO_TRANSACTION = "-- no-transaction"


def _prepare(conn):
    """What every connection needs before it is used.

    psycopg prepares a statement server-side once it repeats, and under
    transaction-mode pooling the next execution can land on a different backend
    connection — `prepared statement "..." does not exist`, intermittently,
    under load, after staging looked fine. Off everywhere, including local
    development and CI, so there is one behaviour rather than two.
    """
    conn.prepare_threshold = None


def pool(conninfo=None, min_size=1, max_size=3, **kwargs):
    """A bounded pool for one process.

    Small on purpose. DigitalOcean's own pool is what stops the cluster's 22
    connections running out; this one only saves a TCP and TLS handshake per
    request, so its size is a latency knob rather than a safety one.

    `max_lifetime` (1 hour) and `max_idle` (10 minutes) keep their psycopg
    defaults: a pooled connection handed out after the far end has quietly gone
    away is the "SSL connection has been closed unexpectedly" class of failure.
    """
    conninfo = conninfo or require("DATABASE_URL")
    return ConnectionPool(conninfo, min_size=min_size, max_size=max_size,
                          configure=_prepare, open=True, **kwargs)


def connect(conninfo=None):
    """One connection, outside any pool. For migrations and one-off scripts.

    Autocommit, so that `conn.transaction()` means what it looks like it means —
    see the note in `migrate`.
    """
    conn = psycopg.connect(conninfo or require("DATABASE_URL_DIRECT"), autocommit=True)
    _prepare(conn)
    return conn


def require(name):
    """An environment variable that cloud mode cannot start without.

    Never logs the value: a connection string carries a password, and the point
    of this function is to be safe to call from a startup path that logs.
    """
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Cloud mode needs it to start.")
    return value


def migrations(directory=None):
    """Every migration on disk, in the order its name sorts."""
    directory = Path(directory) if directory else MIGRATIONS_DIR
    return sorted(directory.glob("*.sql"))


def migrate(conn, directory=None):
    """Apply whatever has not been applied. Returns the names it ran.

    Each migration runs in its own transaction and is recorded in the same one,
    so a failure half way through leaves that migration entirely unapplied and
    the next run tries it again. Migrations marked `-- no-transaction` cannot
    have that guarantee and have to be written to be safe when re-run — which is
    why every index in them is `IF NOT EXISTS`.

    **The connection has to be autocommit**, and this is not a detail. Without
    it, psycopg opens an implicit transaction on the first statement — the
    SELECT below is enough — and `conn.transaction()` entered inside an open
    transaction is a *savepoint*, not a BEGIN. Every migration then appears to
    apply, releases its savepoint, and is thrown away when the connection
    closes. It is silent: no error, tables gone, `schema_migrations` empty.
    """
    was_autocommit = conn.autocommit
    conn.autocommit = True
    try:
        return _migrate(conn, directory)
    finally:
        conn.autocommit = was_autocommit


def _migrate(conn, directory):
    _ensure_bookkeeping(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM schema_migrations")
        done = {row[0] for row in cur.fetchall()}

    applied = []
    for path in migrations(directory):
        if path.name in done:
            continue
        sql = path.read_text()
        log.info("Applying %s", path.name)
        if NO_TRANSACTION in sql:
            _apply_unwrapped(conn, path, sql)
        else:
            _apply(conn, path, sql)
        applied.append(path.name)

    if not applied:
        log.info("Schema is up to date (%d migration(s) already applied)", len(done))
    return applied


def _apply(conn, path, sql):
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))


def _apply_unwrapped(conn, path, sql):
    """Statement by statement, outside a transaction.

    psycopg sends a multi-statement `execute` as one implicit transaction, which
    is exactly what CONCURRENTLY refuses, so the file is split first. The split
    is naive — a semicolon inside a string literal or a function body would
    break it — which is the price of the escape hatch and the reason the marker
    is opt-in rather than the default.
    """
    with conn.cursor() as cur:  # the connection is already autocommit; see migrate()
        for statement in _statements(sql):
            cur.execute(statement)
        cur.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))


def _statements(sql):
    stripped = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in stripped.split(";") if s.strip()]


def _ensure_bookkeeping(conn):
    """The table that records what has run. Created before anything else can."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    name       TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
