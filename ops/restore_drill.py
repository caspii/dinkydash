"""Restore a logical backup into a disposable, socket-only PostgreSQL cluster.

Run with ``python -m ops.restore_drill --pg-bin /path/to/postgresql/bin``.
The source comes from DATABASE_URL_DIRECT. No existing restore target is accepted.
See doc/recovery.md for the isolation, monthly schedule and failure procedure.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from unittest.mock import patch
from uuid import uuid4


REPO = Path(__file__).resolve().parents[1]
TOOLS = ("initdb", "pg_ctl", "pg_dump", "pg_restore", "createdb")


class DrillError(RuntimeError):
    """An operator-safe failure message, without source or restored content."""


def tool_environment():
    # Do not inherit PGHOST/PGSERVICE/PGOPTIONS or a model/email credential.
    return {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "HOME")
            if key in os.environ}


def command(pg_bin, name, args, env, *, timeout=300):
    try:
        subprocess.run([str(pg_bin / name), *map(str, args)], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        # pg_restore can quote a failed COPY row; libpq can quote credentials.
        raise DrillError(f"{name} failed; private tool output was discarded.") from None


def source_environment(source, root):
    """Put the connection parameters in a private libpq service file, not argv."""
    from psycopg.conninfo import conninfo_to_dict

    try:
        params = conninfo_to_dict(source)
    except Exception:
        raise DrillError("The source is not a valid PostgreSQL connection string.") from None
    if "service" in params or not params.get("dbname"):
        raise DrillError("The source must explicitly name a database, without service indirection.")
    if any("\n" in value or "\r" in value or value != value.strip() for value in params.values()):
        raise DrillError("The source contains values unsupported by a libpq service file.")
    params["options"] = params.get("options", "") + " -c default_transaction_read_only=on"
    params["connect_timeout"] = "15"
    service = root / "source.service"
    service.touch(mode=0o600)
    service.write_text("[drill_source]\n" + "".join(f"{key}={value}\n" for key, value in params.items()))
    return dict(tool_environment(), PGSERVICEFILE=str(service), PGSERVICE="drill_source")


@contextmanager
def isolated_cluster(pg_bin, scratch_parent=None):
    """Only a newly initialised cluster, never an existing host or database."""
    if scratch_parent is not None:
        scratch_parent = Path(scratch_parent).resolve()
        if scratch_parent == REPO or REPO in scratch_parent.parents or any(
                (path / ".git").exists() for path in (scratch_parent, *scratch_parent.parents)):
            raise DrillError("Scratch data must live outside the repository.")
    # Avoid TMPDIR putting a database inside a checkout. /tmp also keeps Unix
    # socket names below PostgreSQL's platform-specific length limit on macOS.
    parent = scratch_parent or Path("/tmp")
    root = Path(tempfile.mkdtemp(prefix="dinkydash-restore-", dir=parent))
    data, sockets = root / "data", root / "socket"
    env = tool_environment()
    try:
        if len(os.fsencode(sockets / ".s.PGSQL.5432")) >= 100:
            raise DrillError("Scratch socket path is too long; use /tmp as the parent.")
        os.chmod(root, 0o700)
        sockets.mkdir(mode=0o700)
        command(pg_bin, "initdb", ["-D", data, "-U", "restore_operator",
                                   "--auth=trust", "--encoding=UTF8", "--no-locale"], env)
        # PostgreSQL config syntax needs quotes doubled, not shell quoting.
        socket_path = str(sockets).replace("'", "''")
        with (data / "postgresql.conf").open("a") as config:
            config.write(f"\nlisten_addresses = ''\nunix_socket_directories = '{socket_path}'\n"
                         "unix_socket_permissions = 0700\n")
        command(pg_bin, "pg_ctl", ["-D", data, "-l", root / "postgres.log",
                                   "-w", "-t", "30", "start"], env, timeout=40)
        local = dict(env, PGHOST=str(sockets), PGPORT="5432",
                     PGUSER="restore_operator", PGDATABASE="dinkydash_restore_drill")
        command(pg_bin, "createdb", ["dinkydash_restore_drill"], local)
        from psycopg.conninfo import make_conninfo
        url = make_conninfo(host=str(sockets), port=5432, user="restore_operator",
                            dbname="dinkydash_restore_drill")
        yield root, local, url
    finally:
        # Even a failed restore/start attempt must not leave a server alive.
        # Never remove the data directory if stopping fails.
        if (data / "postmaster.pid").exists():
            try:
                command(pg_bin, "pg_ctl", ["-D", data, "-m", "immediate",
                                           "-w", "-t", "30", "stop"], env, timeout=40)
            except DrillError:
                raise DrillError(f"Scratch server could not stop; private data retained at {root}.") from None
        shutil.rmtree(root)


@contextmanager
def offline_app(url):
    """Allow only Unix sockets during app checks; discard all inherited secrets."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def no_dns(*_args, **_kwargs):
        raise DrillError("The restored app attempted an outbound DNS lookup.")

    def guarded(method):
        def connect(sock, address):
            if sock.family != socket.AF_UNIX:
                raise DrillError("The restored app attempted an outbound connection.")
            return method(sock, address)
        return connect

    env = dict(tool_environment(), DINKYDASH_MODE="cloud",
               DATABASE_URL=url, DATABASE_URL_DIRECT=url,
               DINKYDASH_SECRET_KEY=secrets.token_urlsafe(32),
               DINKYDASH_APP_HOST="restore.invalid",
               DINKYDASH_SITE_URL="https://site.restore.invalid",
               DINKYDASH_FAMILY_CALLS_A_DAY="0", DINKYDASH_GLOBAL_CALL_FLOOR="0",
               DINKYDASH_GLOBAL_CALLS_PER_FAMILY="0")
    disabled = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with patch.dict(os.environ, env, clear=True), \
                patch.object(socket.socket, "connect", guarded(original_connect)), \
                patch.object(socket.socket, "connect_ex", guarded(original_connect_ex)), \
                patch.object(socket, "getaddrinfo", no_dns):
            yield
    finally:
        logging.disable(disabled)


def verify_restored(url):
    """Migrate the scratch copy, read real tenants, and render in-process only."""
    from dinkydash import config as config_module, db
    from dinkydash import screens
    from dinkydash.lifecycle import access_for
    from dinkydash.pgstore import NoSuchFamily, PostgresStore

    with offline_app(url):
        with db.connect(url) as conn:
            conn.execute("SET statement_timeout = '30s'")
            applied = db.migrate(conn)
            recorded = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
            expected = {path.name for path in db.migrations()}
            if not expected <= recorded:
                raise DrillError("The restored schema is incomplete.")
            families = conn.execute(
                "SELECT id, config, screen_token FROM families ORDER BY created_at LIMIT 3"
            ).fetchall()
            family_count = conn.execute("SELECT count(*) FROM families").fetchone()[0]
            if not families:
                raise DrillError("The backup has no families to verify; the drill is incomplete.")

        pool = db.pool(url, min_size=1, max_size=2,
                       kwargs={"options": "-c statement_timeout=30000"})
        try:
            pool.wait(timeout=10)
            # The real cloud entry point creates both apps and dispatches on Host.
            # It builds its own pool; inject this scratch pool at that boundary.
            with patch.object(db, "pool", return_value=pool):
                from wsgi import create_application
                application = create_application()
            from werkzeug.test import Client
            from werkzeug.wrappers import Response
            from web import create_app
            from web.routes.board import render_board

            board_app = create_app(pool=pool)
            client = Client(application, Response)
            for host, path in (("restore.invalid", "/healthz"),
                               ("restore.invalid", "/login"),
                               ("site.restore.invalid", "/")):
                if client.get(path, base_url=f"https://{host}").status_code != 200:
                    raise DrillError("The restored application did not start cleanly.")

            invalid_tokens = 0
            for family_id, saved_config, token in families:
                store = PostgresStore(pool, family_id)
                config = store.load_config()
                if config != config_module.with_defaults(dict(saved_config or {})):
                    raise DrillError("A restored family read returned the wrong config.")
                store.load_payload(config)
                store.recent_notes(config, 30)
                # A legacy/malformed token can already exist in a source row.
                # Verify the data still renders, and that the route preserves
                # its rejection; report the source defect separately.
                with board_app.test_request_context():
                    render_board(store, access=access_for(pool, family_id))
                valid_token = screens.looks_like_a_token(token)
                invalid_tokens += not valid_token
                status = client.get(f"/s/{token}", base_url="https://restore.invalid").status_code
                if status != (200 if valid_token else 404):
                    raise DrillError(f"A restored family board could not be rendered (HTTP {status}).")
            try:
                PostgresStore(pool, uuid4()).load_config()
            except NoSuchFamily:
                pass
            else:
                raise DrillError("An unknown family was able to read a config.")
            return {"families_restored": family_count, "families_checked": len(families),
                    "schema_migrations": len(recorded), "migrations_applied": len(applied),
                    "app_startup": "passed", "outbound_connections": "blocked",
                    "sampled_invalid_screen_tokens": invalid_tokens}
        finally:
            pool.close()


def run(pg_bin, source, scratch_parent=None):
    pg_bin = Path(pg_bin).resolve()
    if not source:
        raise DrillError("The source environment variable is missing or empty.")
    if any(not (pg_bin / name).is_file() for name in TOOLS):
        raise DrillError("The PostgreSQL bin directory must contain every required tool.")
    started = time.monotonic()
    with isolated_cluster(pg_bin, scratch_parent) as (root, local, url):
        archive = root / "backup.dump"
        archive.touch(mode=0o600)
        # pg_dump itself is read-only; the session setting also enforces that.
        env = source_environment(source, root)
        command(pg_bin, "pg_dump", ["--format=custom", "--no-owner", "--no-acl",
                                    "--lock-wait-timeout=15000", "--file", archive], env)
        command(pg_bin, "pg_restore", ["--dbname=dinkydash_restore_drill", "--no-owner",
                                       "--no-acl", "--exit-on-error", "--single-transaction",
                                       archive], local)
        report = verify_restored(url)
    # Only a successful cleanup earns a successful drill.
    return dict(report, status="passed", cleanup="passed",
                backup_kind="fresh logical backup", finished_at=datetime.now(timezone.utc).isoformat(),
                elapsed_seconds=round(time.monotonic() - started, 1))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pg-bin", required=True, help="PostgreSQL server/client bin directory")
    parser.add_argument("--source-env", default="DATABASE_URL_DIRECT")
    parser.add_argument("--scratch-parent", type=Path, help="Private temporary data parent, outside the repo")
    args = parser.parse_args(argv)

    def interrupted(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        report = run(args.pg_bin, os.environ.get(args.source_env), args.scratch_parent)
    except (Exception, KeyboardInterrupt) as exc:
        # No traceback: exceptions can contain connection strings or family data.
        message = str(exc) if isinstance(exc, DrillError) else "Restore drill failed; private details suppressed."
        print(json.dumps({"status": "failed", "message": message}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
