"""Connections and migrations. The only module that imports psycopg.

Cloud mode only. Single mode never imports this, which is what keeps a
Raspberry Pi from installing a Postgres driver it will never open — psycopg
lives in `requirements-cloud.txt`, not `requirements.txt`.

Three connection strings, and the difference matters:

    DATABASE_URL         DigitalOcean's connection pool, transaction mode.
                         What `web` and `worker` use, through `pool()` below.
    DATABASE_URL_DIRECT  The cluster itself. What migrations and pg_dump use.
                         CREATE INDEX CONCURRENTLY cannot run inside a
                         transaction block, and pg_dump errors against a
                         transaction-mode pool.
    DEV_DATABASE_URL     A database on the developer's own machine. Not a
                         variable: a constant below, so that no file carries it.

Never send a session-level `SET` through DATABASE_URL. A transaction-mode
pooler hands a server connection to its next client exactly as the last one
left it, so the setting lands on the worker or on somebody's request.
`SET LOCAL` inside a transaction is fine, because it ends with the transaction.
"""

import ipaddress
import logging
import os
import re
from pathlib import Path

import psycopg
from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

# The database development runs against, when nothing in the environment names
# one. `dev.py` serves it and `migrate.py` applies the schema to it, and they
# read the same constant: a launcher and a migration tool that disagreed about
# which database is the development one would leave a dashboard refusing to
# start against a schema its owner had just been told was up to date.
#
# **Hardcoded, so that no file has to carry it.** `.env` is copied into every
# new workspace and its keys are the names production uses, so a development
# value stored there is one that something reaching for the production database
# can be handed. A value only development uses belongs in the files only
# development runs. Neither caller can then reach a real service by accident:
# `migrate.py` reads no `.env`, so a cluster has to be named on its command line
# or exported on purpose, and both put this value through `on_this_machine`
# before using it — a URL with no host is a request about this machine only for
# as long as `PGHOST` agrees.
DEV_DATABASE_URL = "postgresql:///dinkydash_dev"

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


# How long a starting process waits for its first connection before it refuses
# to start. Long enough for a cold pool and a TLS handshake; short enough that a
# deploy fails before the platform's probe has given up on the container.
STARTUP_TIMEOUT = 10.0


def ready(pool, timeout=None):
    """Wait for the pool's first connection, or refuse to start.

    A pool opens in the background, and a wrong connection string is only a
    warning in its log: the process comes up, `/healthz` answers, the deploy is
    declared healthy, and every request that needs the database then waits
    thirty seconds and fails; an entry point built against a closed port
    still comes up in half a second and answers 200 on both hostnames.
    Waiting here turns that into a process that never
    starts, which under gunicorn is a container that never becomes healthy,
    which is a deploy that never goes live while the previous one carries on —
    and App Platform's own DEPLOYMENT_FAILED alert says so (DIN-54).

    Not called by the worker: it has no probe, and a worker that loops on a
    dead database sends no check-in, which is already the alert.

    The message names the variable and nothing else. A connection string
    carries a password, and this runs on a start-up path that logs.
    """
    from psycopg_pool import PoolTimeout

    # Read at call time rather than bound as a default, so a test can shorten it.
    timeout = STARTUP_TIMEOUT if timeout is None else timeout
    try:
        pool.wait(timeout=timeout)
    except PoolTimeout:
        raise RuntimeError(
            f"The database did not answer within {timeout:g} seconds. Cloud mode "
            "will not start without it; check DATABASE_URL.") from None


def on_this_machine(conninfo):
    """Whether a connection string names nothing but this machine.

    libpq's own parser is asked rather than the string read, because a host can
    hide in the query string (`postgresql:///x?host=...`), in a comma-separated
    list or in `hostaddr` — and a URL with **no** host falls back to `PGHOST`,
    so a hostless one is not local by construction. That is why the development
    default is checked like anything else rather than trusted for its shape.

    Loopback, a Unix socket directory, or libpq's own default socket. Raises if
    libpq cannot parse the string: a target nobody can read is not one to
    assume anything about.
    """
    from psycopg.conninfo import conninfo_to_dict

    params = conninfo_to_dict(conninfo)
    hosts = []
    for key in ("host", "hostaddr"):
        value = params.get(key) or os.environ.get("PG" + key.upper(), "")
        hosts.extend(str(value).split(","))
    return all(_local_host(host) for host in hosts)


def _local_host(host):
    host = host.strip()
    if not host or host.startswith("/") or host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def without_password(conninfo):
    """The same connection string, minus any password, for printing.

    A connection string is the useful thing to put in a message telling
    somebody which command to run, and the password is the one part of it that
    must not be. Returns keyword form, which `connect` accepts as readily as a
    URL, and needs quoting in a shell because it contains spaces.
    """
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    params = conninfo_to_dict(conninfo)
    params.pop("password", None)
    return make_conninfo(**params)


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
