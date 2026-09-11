"""Run the hosted dashboard and marketing site together for local development.

Uses two spawned processes in the launcher's process group. No reloader or
debugger subprocesses: restart the run action after changing Python/content.
Production uses wsgi.py; a self-hosted Pi continues to use app.py.

**Only a database on this machine.** A workspace's `.env` can carry a remote
`DATABASE_URL`, and a launcher that connects to whatever it finds is a local
preview of somebody's production. `require_local_database` refuses anything
that is not loopback or a Unix socket, before a connection is opened.
"""

import ipaddress
import logging
import multiprocessing
import os
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
START_TIMEOUT = 15
STOP_TIMEOUT = 5


def configure():
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
    for name in ("DATABASE_URL", "DINKYDASH_SECRET_KEY"):
        if not os.environ.get(name, "").strip():
            raise RuntimeError(f"{name} is required; set it in the environment or .env.")
    require_local_database(os.environ["DATABASE_URL"])
    from web import SELF_HOSTED_KEY

    if os.environ["DINKYDASH_SECRET_KEY"] == SELF_HOSTED_KEY:
        raise RuntimeError("DINKYDASH_SECRET_KEY must be a private development key.")

    def port(name, default):
        try:
            value = int(os.environ.get(name, default))
            if 1 <= value <= 65535:
                return value
        except ValueError:
            pass
        raise RuntimeError(f"{name} must be an integer between 1 and 65535.")

    if "CONDUCTOR_PORT" in os.environ:
        dashboard = port("CONDUCTOR_PORT", 5000)
        website = dashboard + 1
    else:
        dashboard = port("DINKYDASH_PORT", 5000)
        website = port("DINKYDASH_WEBSITE_PORT", dashboard + 1)
    if website > 65535 or website == dashboard:
        raise RuntimeError("Dashboard and website need distinct ports between 1 and 65535.")

    os.environ.update(
        DINKYDASH_MODE="cloud",
        DINKYDASH_APP_URL=f"http://{HOST}:{dashboard}",
        # Let dashboard URLs use the local request host, not a production .env value.
        DINKYDASH_APP_HOST="",
    )
    return {"Dashboard": dashboard, "Website": website}


def require_local_database(url):
    """Refuse a database that is not on this machine.

    A workspace's `.env` may hold a remote `DATABASE_URL`, and this launcher
    connects to whatever it is given. Without this check the default run
    action can be a production database: the dashboard it then serves on
    127.0.0.1 is that database, and its start-up check runs through a pooler
    shared with the real service.

    Only a loopback address or a Unix socket is accepted, with no override:
    an escape hatch would end up in `.env` as well.
    libpq's own parser is used because a host can hide in the query string
    (`postgresql:///x?host=...`), in a comma-separated list or in `hostaddr`,
    and an absent host falls back to `PGHOST`. The message names the variable
    and never the value: a connection string carries a password.
    """
    from psycopg.conninfo import conninfo_to_dict

    try:
        params = conninfo_to_dict(url)
    except Exception:
        raise RuntimeError("DATABASE_URL is not a valid connection string.") from None
    hosts = []
    for key in ("host", "hostaddr"):
        value = params.get(key) or os.environ.get("PG" + key.upper(), "")
        hosts.extend(str(value).split(","))
    if not all(_on_this_machine(host) for host in hosts):
        raise RuntimeError(
            "DATABASE_URL is not a database on this machine. The launcher only runs "
            "against a local development database such as postgresql:///dinkydash_dev; "
            "a copied .env may be pointing it at the hosted pool.")


def _on_this_machine(host):
    """Loopback, a Unix socket directory, or libpq's default socket."""
    host = host.strip()
    if not host or host.startswith("/") or host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_database():
    """Reachable database with every repository migration applied, and nothing else.

    `require_local_database` has already refused a remote one. This is what runs
    when the check goes ahead, so it has to be safe through a transaction-mode
    pooler as well: see `applied_migrations`.
    """
    from dinkydash import db
    from psycopg.conninfo import make_conninfo

    try:
        conninfo = make_conninfo(os.environ["DATABASE_URL"], connect_timeout=5)
        with db.connect(conninfo) as conn:
            applied = applied_migrations(conn)
    except Exception as exc:
        # Driver exceptions can contain credentials or connection details.
        raise RuntimeError(
            f"Database validation failed ({type(exc).__name__}). Check DATABASE_URL "
            "and apply migrations to your development database with migrate.py."
        ) from None
    if any(path.name not in applied for path in db.migrations()):
        raise RuntimeError("Database migrations are missing; run migrate.py on your development database.")


def applied_migrations(conn):
    """The migration names the database records, read in one short read-only transaction.

    `SET LOCAL`, never `SET`. A session-level setting outlives this connection
    on a transaction-mode pooler and lands on whichever client is handed the
    server connection next. Both settings end with the transaction, and
    `tests/test_dev.py` asserts the session is left exactly as it was found.
    """
    with conn.transaction():
        conn.execute("SET LOCAL transaction_read_only = on")
        conn.execute("SET LOCAL statement_timeout = '5s'")
        return {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}


def serve(name, port, ready):
    """Signal readiness only after the real app has initialized and bound its port."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # the supervisor handles Ctrl-C
    logging.basicConfig(level=logging.INFO, format=f"[{name}] %(message)s")
    pool = None
    try:
        from werkzeug.serving import make_server

        if name == "Dashboard":
            from web import create_app

            app = create_app()
            pool = app.config["POOL"]
            pool.wait(timeout=5)
        else:
            from website.site import create_site_app

            app = create_site_app()
        with make_server(HOST, port, app, threaded=True) as server:
            ready.send(True)
            ready.close()
            server.serve_forever()
    except (Exception, SystemExit) as exc:
        print(f"{name} failed to start or serve on port {port} ({type(exc).__name__}).",
              file=sys.stderr, flush=True)
        raise SystemExit(1) from None
    finally:
        ready.close()
        if pool is not None:
            pool.close()


def supervise(ports):
    context = multiprocessing.get_context("spawn")
    children = []
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        for name, port in ports.items():
            if stopping:
                return 0
            reader, writer = context.Pipe(duplex=False)
            process = context.Process(target=serve, args=(name, port, writer), name=name)
            process.start()
            writer.close()
            children.append((name, process, reader))
            print(f"Starting {name} (PID {process.pid}) on port {port}.", flush=True)

        pending = {name for name, _, _ in children}
        deadline = time.monotonic() + START_TIMEOUT
        while not stopping:
            for name, process, reader in children:
                if process.exitcode is not None:
                    raise RuntimeError(f"{name} exited unexpectedly (status {process.exitcode}); stopping both apps.")
                if name in pending and reader.poll():
                    try:
                        reader.recv()
                    except EOFError:
                        raise RuntimeError(f"{name} failed during startup; stopping both apps.") from None
                    pending.remove(name)
                    if not pending:
                        print(f"Dashboard: http://{HOST}:{ports['Dashboard']}/login", flush=True)
                        print(f"Website:   http://{HOST}:{ports['Website']}/", flush=True)
                        print("Use Chrome or Firefox for local sign-in (Secure cookies). "
                              "Restart this command after code/content changes. Ctrl-C stops both apps.", flush=True)
            if pending and time.monotonic() >= deadline:
                raise RuntimeError(f"Startup timed out: {', '.join(sorted(pending))}; stopping both apps.")
            time.sleep(0.1)
        return 0
    finally:
        for _, process, reader in children:
            reader.close()
            if process.is_alive():
                process.terminate()
        deadline = time.monotonic() + STOP_TIMEOUT
        for _, process, _ in children:
            process.join(max(0, deadline - time.monotonic()))
            if process.is_alive():
                process.kill()
                process.join()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main():
    try:
        ports = configure()
        validate_database()
        return supervise(ports)
    except ImportError as exc:
        print(f"Development dependency missing ({exc.name}); install requirements-cloud.txt.", file=sys.stderr)
    except (RuntimeError, OSError) as exc:
        print(f"Development startup failed: {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
