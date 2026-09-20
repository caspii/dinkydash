#!/usr/bin/env python3
"""Apply the database schema. Cloud mode only.

App Platform runs this as a **pre-deploy job**, so a failed migration fails the
deploy rather than half-updating a live app, and the schema is always ahead of
the code that needs it.

    python migrate.py            # apply what is outstanding
    python migrate.py --status   # say what would run, change nothing

**It does not read `.env`.** That file is a development file whose keys are the
names production uses, and the `DATABASE_URL_DIRECT` in a developer's copy is
the live cluster. A tool that loaded it would read "apply my schema change" as
"apply it to the running service" — the opposite of what somebody at a laptop
means, and silent, because a schema that is already up to date says so either
way. App Platform sets the variable in the container's own environment and has
no `.env` at all, so the pre-deploy job is unaffected.

Which database, in order:

    --database-url        whatever it names. Naming it is the consent, so an
                          empty value is refused rather than fallen back from.
    DATABASE_URL_DIRECT   the environment's own value: the platform's, or one
                          exported on purpose.
    neither               `db.DEV_DATABASE_URL`, this machine's development
                          database — the one `dev.py` serves. Checked with
                          `db.on_this_machine` rather than trusted for its
                          shape, because a URL with no host is redirected by
                          `PGHOST`, which would make the local default remote.

`DATABASE_URL_DIRECT` is the cluster rather than the pool. CREATE INDEX
CONCURRENTLY cannot run inside a transaction block, and a transaction-mode
PgBouncer is the wrong end for schema work (see dinkydash/db.py).
"""

import argparse
import logging
import os
import sys

from dinkydash import db

log = logging.getLogger("dinkydash.migrate")


def target(database_url=None):
    """The database to migrate, and a name for it that carries no password.

    The name is printed before anything connects, because the wrong database is
    otherwise indistinguishable from the right one: both answer, and both can
    report a schema that is up to date. It says where the value came from and
    never what it is — a connection string carries a password and this runs on
    a path that logs.
    """
    if database_url is not None:
        if not database_url.strip():
            raise ValueError(
                "--database-url is empty. Leave it out to migrate the development "
                "database, or give it a value.")
        return database_url, "the database given on the command line"
    direct = os.environ.get("DATABASE_URL_DIRECT", "").strip()
    if direct:
        return direct, "DATABASE_URL_DIRECT"
    if not db.on_this_machine(db.DEV_DATABASE_URL):
        raise ValueError(
            "PGHOST or PGHOSTADDR names a database somewhere else, and the "
            f"default {db.DEV_DATABASE_URL} has no host of its own to override "
            "it. Unset them, or say which database with --database-url.")
    return db.DEV_DATABASE_URL, f"the development database ({db.DEV_DATABASE_URL})"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Apply the DinkyDash schema.")
    parser.add_argument("--status", action="store_true",
                        help="say what is outstanding and change nothing")
    parser.add_argument("--database-url",
                        help="the database to migrate; defaults to DATABASE_URL_DIRECT "
                             "if it is set in the environment, and otherwise to this "
                             "machine's development database")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        stream=sys.stdout)

    try:
        conninfo, where = target(args.database_url)
    except ValueError as exc:
        log.error("%s", exc)
        return 1
    log.info("Migrating %s", where)

    try:
        conn = db.connect(conninfo)
    except Exception as exc:
        # Never the connection string itself — it carries a password.
        log.error("Could not reach the database: %s", type(exc).__name__)
        return 1

    try:
        if args.status:
            return status(conn)
        applied = db.migrate(conn)
        for name in applied:
            log.info("Applied %s", name)
        return 0
    except Exception:
        log.exception("Migration failed; nothing further was applied")
        return 1
    finally:
        conn.close()


def status(conn):
    """What has run and what has not. Read-only apart from the bookkeeping table."""
    db._ensure_bookkeeping(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM schema_migrations")
        done = {row[0] for row in cur.fetchall()}
    outstanding = [p.name for p in db.migrations() if p.name not in done]
    for name in sorted(done):
        log.info("applied     %s", name)
    for name in outstanding:
        log.info("OUTSTANDING %s", name)
    if not outstanding:
        log.info("Schema is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
