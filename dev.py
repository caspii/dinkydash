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
not sit under the name production uses for its pooled connection.

**It applies outstanding migrations before serving**, and only because the
database is on this machine and therefore disposable. Every other database is
migrated with `migrate.py`.

**Email is printed, never sent.** A workspace's `.env` carries the production
SendGrid key, and a sign-in form typed into locally would otherwise mail
whatever address was typed from the shared sending account. The dashboard's
`mail.send` writes each message to this terminal instead, so the sign-in link
is in the run output, and the key in the children's environment is replaced
with a placeholder that SendGrid would refuse.
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

# Not a key. Set so that what offers mail (the feedback form) still appears,
# and so that a send that got past `print_mail` would be refused by SendGrid.
DEV_MAIL_KEY = "dev-launcher-prints-mail"

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
        SENDGRID_API_KEY=DEV_MAIL_KEY,
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


def prepare_database():
    """Reachable, with every repository migration applied.

    Outstanding migrations are applied here rather than reported, so a branch
    that adds one starts on the next run instead of failing it. That is safe
    only because `require_local_database` has already refused anything that is
    not on this machine: a development database is disposable, and recreating
    it is the remedy for a migration that went wrong. `migrate.py` stays the
    tool for every other database.
    """
    from dinkydash import db
    from psycopg.conninfo import make_conninfo

    try:
        conninfo = make_conninfo(os.environ["DATABASE_URL"], connect_timeout=5)
        conn = db.connect(conninfo)
    except Exception as exc:
        # Driver exceptions can contain credentials or connection details.
        raise RuntimeError(
            f"Database connection failed ({type(exc).__name__}). Check DATABASE_URL "
            "and that Postgres is running.") from None
    try:
        applied = db.migrate(conn)
    except Exception as exc:
        raise RuntimeError(
            f"Applying migrations failed ({type(exc).__name__}). This is a local "
            "development database: drop and recreate it, then run this again.") from None
    finally:
        conn.close()
    for name in applied:
        print(f"Applied migration {name}.", flush=True)


def print_mail(to, subject, text, html=None, **_):
    """`mail.send` under the launcher: the message on this terminal, and nothing sent.

    The address is checked the way `mail.send` checks it, so a refusal behaves
    the same locally. The plain-text body carries the sign-in link, and this
    terminal is the only place it goes; it opens this machine's dashboard.
    The app puts every link on HTTPS and this server speaks plain HTTP, so
    links to it are printed as HTTP.
    """
    from dinkydash import mail

    recipient = mail._clean_address(to)
    text = text.replace(f"https://{HOST}:", f"http://{HOST}:")
    print(f"Email not sent (development) to {recipient}: {subject}\n\n{text}\n", flush=True)


def use_terminal_mail():
    from dinkydash import mail

    mail.send = print_mail


def serve(name, port, ready):
    """Signal readiness only after the real app has initialized and bound its port."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # the supervisor handles Ctrl-C
    logging.basicConfig(level=logging.INFO, format=f"[{name}] %(message)s")
    pool = None
    try:
        from werkzeug.serving import make_server

        if name == "Dashboard":
            from web import create_app

            use_terminal_mail()
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
        prepare_database()
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
