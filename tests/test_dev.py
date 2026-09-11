"""Exercise the real two-process launcher against the opt-in scratch database."""

import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest

import dev


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    monkeypatch.setattr(dev, "ROOT", tmp_path)
    for name in ("CONDUCTOR_PORT", "DINKYDASH_PORT", "DINKYDASH_WEBSITE_PORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("DINKYDASH_SECRET_KEY", "development-test-key")
    # configure() changes these for its children; restore them after unit tests.
    monkeypatch.setenv("DINKYDASH_MODE", "single")
    monkeypatch.setenv("DINKYDASH_APP_URL", "https://app.example.test")
    monkeypatch.setenv("DINKYDASH_APP_HOST", "app.example.test")
    monkeypatch.setenv("SENDGRID_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")


def test_dotenv_defaults_and_environment_precedence(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("DATABASE_URL=postgresql:///example\nDINKYDASH_PORT=5200\n")
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.setenv("DINKYDASH_PORT", "5300")
    monkeypatch.setenv("DINKYDASH_MODE", "single")
    monkeypatch.setenv("DINKYDASH_APP_URL", "https://app.example.test")
    assert dev.configure() == {"Dashboard": 5300, "Website": 5301}
    assert os.environ["DINKYDASH_MODE"] == "cloud"
    assert os.environ["DINKYDASH_APP_URL"] == "http://127.0.0.1:5300"


@pytest.mark.parametrize("values, expected", [
    ({}, (5000, 5001)),
    ({"DINKYDASH_PORT": "5100", "DINKYDASH_WEBSITE_PORT": "5200"}, (5100, 5200)),
    ({"CONDUCTOR_PORT": "5400", "DINKYDASH_PORT": "bad", "DINKYDASH_WEBSITE_PORT": "bad"}, (5400, 5401)),
])
def test_ports(monkeypatch, values, expected):
    monkeypatch.setenv("DATABASE_URL", "postgresql:///example")
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    assert tuple(dev.configure().values()) == expected


@pytest.mark.parametrize("values, error", [
    ({"DATABASE_URL": " "}, "DATABASE_URL"),
    ({"DINKYDASH_SECRET_KEY": ""}, "DINKYDASH_SECRET_KEY"),
    ({"DINKYDASH_SECRET_KEY": "dinkydash-self-hosted"}, "private development key"),
    ({"CONDUCTOR_PORT": ""}, "CONDUCTOR_PORT"),
    ({"CONDUCTOR_PORT": "abc"}, "CONDUCTOR_PORT"),
    ({"CONDUCTOR_PORT": "0"}, "CONDUCTOR_PORT"),
    ({"CONDUCTOR_PORT": "65535"}, "distinct ports"),
    ({"DINKYDASH_PORT": "65535"}, "DINKYDASH_WEBSITE_PORT"),
    ({"DINKYDASH_WEBSITE_PORT": "5000"}, "distinct ports"),
    ({"DINKYDASH_WEBSITE_PORT": "65536"}, "DINKYDASH_WEBSITE_PORT"),
])
def test_invalid_configuration(monkeypatch, values, error):
    monkeypatch.setenv("DATABASE_URL", "postgresql:///example")
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=error):
        dev.configure()


@pytest.fixture
def ports():
    for _ in range(100):
        with socket.socket() as first, socket.socket() as second:
            first.bind((dev.HOST, 0))
            port = first.getsockname()[1]
            if port == 65535:
                continue
            try:
                second.bind((dev.HOST, port + 1))
            except OSError:
                continue
            return port, port + 1
    pytest.fail("Could not allocate adjacent test ports")


@pytest.fixture
def launch(tmp_path):
    processes = []

    def start(extra):
        log = tmp_path / f"run-{len(processes)}.log"
        with log.open("w") as output:
            process = subprocess.Popen(
                [sys.executable, "dev.py"], cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, **extra}, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        processes.append(process)
        return process, log

    yield start
    for process in processes:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        # Also clean up orphans if a lifecycle assertion failed.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def wait_ready(process, log):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        text = log.read_text()
        assert process.poll() is None, text
        if "Website:   http://" in text:
            return
        time.sleep(0.05)
    pytest.fail(log.read_text())


def assert_stopped(ports, log):
    for pid in re.findall(r"Starting \w+ \(PID (\d+)\)", log.read_text()):
        with pytest.raises(ProcessLookupError):
            os.kill(int(pid), 0)
    for port in ports:
        with socket.socket() as probe:
            assert probe.connect_ex((dev.HOST, port)) != 0


@pytest.mark.parametrize("shutdown", [signal.SIGINT, signal.SIGTERM])
def test_start_links_and_shutdown(pg_pool, ports, launch, shutdown):
    dashboard, website = ports
    process, log = launch({
        "DATABASE_URL": os.environ["DINKYDASH_TEST_DATABASE_URL"],
        "CONDUCTOR_PORT": str(dashboard),
        "DINKYDASH_MODE": "single",
        "DINKYDASH_APP_URL": "https://app.example.test",
    })
    wait_ready(process, log)
    assert f"Dashboard: http://127.0.0.1:{dashboard}/login" in log.read_text()
    # Both the homepage templates and Markdown links must lead to this run.
    for path in ("/", "/about/", "/ipad-calendar-display/"):
        with urlopen(f"http://{dev.HOST}:{website}{path}") as response:
            body = response.read().decode()
        assert f'href="http://{dev.HOST}:{dashboard}/login"' in body, path
        assert 'href="https://app.dinkydash.co/login"' not in body
    with urlopen(f"http://{dev.HOST}:{dashboard}/") as response:
        assert response.url.endswith("/login")  # cloud auth, never single mode
        assert response.status == 200
    if shutdown == signal.SIGTERM:
        os.killpg(process.pid, shutdown)  # Conductor can stop the whole group
    else:
        process.send_signal(shutdown)  # stopping only the supervisor works too
    assert process.wait(timeout=10) == 0, log.read_text()
    assert_stopped(ports, log)


@pytest.mark.parametrize("failed", ["Dashboard", "Website"])
def test_unexpected_exit_stops_sibling(pg_pool, ports, launch, failed):
    process, log = launch({
        "DATABASE_URL": os.environ["DINKYDASH_TEST_DATABASE_URL"],
        "DINKYDASH_PORT": str(ports[0]), "DINKYDASH_WEBSITE_PORT": str(ports[1]),
    })
    wait_ready(process, log)
    pid = int(re.search(rf"Starting {failed} \(PID (\d+)\)", log.read_text())[1])
    os.kill(pid, signal.SIGKILL)
    assert process.wait(timeout=10) == 1
    assert f"{failed} exited unexpectedly" in log.read_text()
    assert_stopped(ports, log)


@pytest.mark.parametrize("occupied", [0, 1])
def test_port_conflict_stops_both(pg_pool, ports, launch, occupied):
    with socket.socket() as blocker:
        blocker.bind((dev.HOST, ports[occupied]))
        blocker.listen()
        process, log = launch({
            "DATABASE_URL": os.environ["DINKYDASH_TEST_DATABASE_URL"],
            "CONDUCTOR_PORT": str(ports[0]),
        })
        assert process.wait(timeout=20) == 1
        assert ("Dashboard", "Website")[occupied] in log.read_text()
        assert "Website:   http://" not in log.read_text()
    assert_stopped(ports, log)


def test_missing_config_starts_neither(launch):
    process, log = launch({"DATABASE_URL": ""})
    assert process.wait(timeout=10) == 1
    assert "DATABASE_URL is required" in log.read_text()
    assert "Starting " not in log.read_text()


def test_unreachable_database_starts_neither(ports, launch):
    process, log = launch({"DATABASE_URL": f"postgresql://127.0.0.1:{ports[0]}/missing"})
    assert process.wait(timeout=10) == 1
    assert "Database validation failed" in log.read_text()
    assert "Starting " not in log.read_text()


def test_unmigrated_database_starts_neither(pg_pool, launch):
    from psycopg.conninfo import make_conninfo

    url = make_conninfo(os.environ["DINKYDASH_TEST_DATABASE_URL"],
                        options="-csearch_path=missing_schema")
    process, log = launch({"DATABASE_URL": url})
    assert process.wait(timeout=10) == 1
    assert "Database validation failed" in log.read_text()
    assert "Starting " not in log.read_text()


def lifecycle_worker(name, port, ready):
    """Real child processes for lifecycle cases a healthy Flask server won't cause."""
    if port:
        ready.send(True)
    if port == 1:
        return  # even status zero is unexpected for a long-running server
    while True:
        time.sleep(0.1)


@pytest.mark.parametrize("ports, error", [
    ({"Dashboard": 1, "Website": 2}, "Dashboard exited unexpectedly \\(status 0\\)"),
    ({"Dashboard": 0, "Website": 0}, "Startup timed out"),
])
def test_early_exit_and_timeout_reap_children(monkeypatch, ports, error):
    monkeypatch.setattr(dev, "serve", lifecycle_worker)
    monkeypatch.setattr(dev, "START_TIMEOUT", 2)
    with pytest.raises(RuntimeError, match=error):
        dev.supervise(ports)
    assert not dev.multiprocessing.active_children()
