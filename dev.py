"""Run the hosted dashboard and marketing site together for local development.

Uses two spawned processes in the launcher's process group. No reloader or
debugger subprocesses: restart the run action after changing Python/content.
Production uses wsgi.py; a self-hosted Pi continues to use app.py.

**Only a database on this machine.** A workspace's `.env` can carry a remote
`DATABASE_URL`, and a launcher that connects to whatever it finds is a local
preview of somebody's production. `require_local_database` refuses anything
that is not loopback or a Unix socket, before a connection is opened.

**And it does not have to be named at all.** `db.DEV_DATABASE_URL` is the
default, so `.env` needs no `DATABASE_URL` entry and a development value does
not sit under the name production uses for its pooled connection. `migrate.py`
defaults to the same constant, so the database this serves is the database that
has the schema.
"""

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

    from dinkydash.db import DEV_DATABASE_URL

    load_dotenv(ROOT / ".env", override=False)
    # A session key cannot be defaulted the way a database name can: it has to
    # be private, and a launcher that invents one signs cookies with a value
    # nobody chose.
    if not os.environ.get("DINKYDASH_SECRET_KEY", "").strip():
        raise RuntimeError(
            "DINKYDASH_SECRET_KEY is required; set it in the environment or .env.")
    if not os.environ.get("DATABASE_URL", "").strip():
        os.environ["DATABASE_URL"] = DEV_DATABASE_URL
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
    an escape hatch would end up in `.env` as well. `db.on_this_machine` is
    what reads the string, so the launcher and `migrate.py` accept the same
    set. The message names the variable and never the value: a connection
    string carries a password.
    """
    from dinkydash import db

    try:
        local = db.on_this_machine(url)
    except Exception:
        raise RuntimeError("DATABASE_URL is not a valid connection string.") from None
    if not local:
        raise RuntimeError(
            "DATABASE_URL is not a database on this machine. The launcher only runs "
            "against a local development database such as postgresql:///dinkydash_dev; "
            "a copied .env may be pointing it at the hosted pool.")


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
            f"Database validation failed ({type(exc).__name__}). Check DATABASE_URL, "
            f"then apply the schema with: {migrate_command()}"
        ) from None
    if any(path.name not in applied for path in db.migrations()):
        raise RuntimeError(
            f"Database migrations are missing. Apply them with: {migrate_command()}")


def migrate_command():
    """A command to migrate the database this launcher is about to serve.

    Written to be pasted into a fresh terminal, which is where somebody reading
    this will be, so it can assume nothing that terminal does not have. Not
    `$DATABASE_URL`: this process was given that by `.env` or by the run
    environment, and a shell somewhere else has neither. Not a bare `python`
    either — `sys.executable` is the interpreter that has the dependencies
    installed, written relative to the repository when it lives there, which is
    the `venv/bin/python` the rest of the documentation uses.

    `migrate.py` has a default of its own and never reads `DATABASE_URL`, which
    in production is the pooler and the wrong end for schema work. So a database
    other than the default has to be named again here, with its password taken
    out: a message like this is pasted into terminals and chat windows.
    """
    from dinkydash import db

    interpreter = Path(sys.executable)
    if interpreter.is_relative_to(ROOT):
        interpreter = interpreter.relative_to(ROOT)
    url = os.environ.get("DATABASE_URL", "")
    if url == db.DEV_DATABASE_URL:
        return f"{interpreter} migrate.py"
    try:
        return f'{interpreter} migrate.py --database-url "{db.without_password(url)}"'
    except Exception:
        # An unparseable URL is the failure being reported, not a thing to quote.
        return f"{interpreter} migrate.py --database-url <the database DATABASE_URL names>"


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
