#!/usr/bin/env python3
"""Apply the database schema. Cloud mode only.

App Platform runs this as a **pre-deploy job**, so a failed migration fails the
deploy rather than half-updating a live app, and the schema is always ahead of
the code that needs it.

    python migrate.py            # apply what is outstanding
    python migrate.py --status   # say what would run, change nothing

It connects with `DATABASE_URL_DIRECT` — the cluster, not the pool. CREATE INDEX
CONCURRENTLY cannot run inside a transaction block, and a transaction-mode
PgBouncer is the wrong end for schema work (PLAN.md, Connection pooling).
"""

import argparse
import logging
import sys

from dotenv import load_dotenv

from dinkydash import db

load_dotenv()
log = logging.getLogger("dinkydash.migrate")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Apply the DinkyDash schema.")
    parser.add_argument("--status", action="store_true",
                        help="say what is outstanding and change nothing")
    parser.add_argument("--database-url", help="override DATABASE_URL_DIRECT")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        stream=sys.stdout)

    try:
        conn = db.connect(args.database_url)
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
