"""Restore drills never target an existing database or expose private output."""

import os
from pathlib import Path
import socket
import subprocess
import tempfile

import pytest

from ops.restore_drill import (DrillError, command, isolated_cluster, main,
                               offline_app, run, source_environment, tool_environment)


def test_child_tools_do_not_inherit_production_configuration(monkeypatch):
    for key in ("PGHOST", "PGSERVICE", "PGOPTIONS", "DATABASE_URL", "ANTHROPIC_API_KEY",
                "SENDGRID_API_KEY", "STRIPE_SECRET_KEY"):
        monkeypatch.setenv(key, "private-value")
    assert not set(tool_environment()) & {
        "PGHOST", "PGSERVICE", "PGOPTIONS", "DATABASE_URL", "ANTHROPIC_API_KEY",
        "SENDGRID_API_KEY", "STRIPE_SECRET_KEY",
    }


def test_scratch_under_the_repository_is_refused():
    from ops.restore_drill import REPO
    with pytest.raises(DrillError, match="outside the repository"):
        with isolated_cluster(Path("/unused"), REPO / ".context"):
            pytest.fail("Should refuse before creating a database")


def test_private_tool_errors_are_not_exposed(monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr=b"private-calendar-and-password")
    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(DrillError) as error:
        command(Path("/unused"), "pg_restore", [], {})
    assert "private-calendar-and-password" not in str(error.value)
    assert "pg_restore failed" in str(error.value)


def test_source_credentials_are_private_and_read_only(tmp_path):
    pytest.importorskip("psycopg")
    env = source_environment("dbname=source user=reader password=fake-password", tmp_path)
    service = Path(env["PGSERVICEFILE"])
    assert service.stat().st_mode & 0o777 == 0o600
    assert "default_transaction_read_only=on" in service.read_text()
    assert "password=fake-password" in service.read_text()
    assert "fake-password" not in str(env)


def test_app_checks_block_network_and_remove_credentials(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "private-key")
    monkeypatch.setenv("DATABASE_URL", "private-production-url")
    with offline_app("host=/private/scratch dbname=drill"):
        assert "ANTHROPIC_API_KEY" not in os.environ
        assert os.environ["DATABASE_URL"] == "host=/private/scratch dbname=drill"
        with pytest.raises(DrillError, match="DNS"):
            socket.getaddrinfo("example.com", 443)
        with socket.socket() as sock:
            with pytest.raises(DrillError, match="outbound"):
                sock.connect(("127.0.0.1", 443))
            with pytest.raises(DrillError, match="outbound"):
                sock.connect_ex(("127.0.0.1", 443))
    assert os.environ["DATABASE_URL"] == "private-production-url"
    assert os.environ["ANTHROPIC_API_KEY"] == "private-key"


def test_cli_fails_closed_without_a_source(monkeypatch, capsys):
    monkeypatch.delenv("RESTORE_TEST_SOURCE", raising=False)
    assert main(["--pg-bin", "/unused", "--source-env", "RESTORE_TEST_SOURCE"]) == 1
    assert '"status": "failed"' in capsys.readouterr().out


def test_failed_start_is_cleaned_up(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise DrillError("initdb failed")
    monkeypatch.setattr("ops.restore_drill.command", fail)
    with pytest.raises(DrillError):
        with isolated_cluster(Path("/unused"), tmp_path):
            pytest.fail("Should never start")
    assert not list(tmp_path.iterdir())


@pytest.fixture
def scratch_parent():
    # Unix socket names have a ~100-byte limit; pytest's macOS TMPDIR is longer.
    with tempfile.TemporaryDirectory(prefix="dd-test-", dir="/tmp") as directory:
        yield Path(directory)


@pytest.fixture
def pg_bin():
    value = os.environ.get("DINKYDASH_TEST_PG_BIN")
    if not value:
        pytest.skip("DINKYDASH_TEST_PG_BIN is not set (full restore integration)")
    return Path(value)


@pytest.mark.parametrize("legacy_token", [False, True])
def test_round_trip_real_backup_and_cleanup(pg_pool, pg_family, pg_bin, scratch_parent, legacy_token):
    from dinkydash import config as config_module
    from dinkydash.pgstore import PostgresStore
    from tests.conftest import database_url
    from psycopg.conninfo import make_conninfo

    if legacy_token:
        with pg_pool.connection() as conn:
            conn.execute("UPDATE families SET screen_token = %s WHERE id = %s",
                         ("00112233445566778899aabb", pg_family))

    store = PostgresStore(pg_pool, pg_family)
    config = config_module.with_defaults({"family_name": "Restore test family", "timezone": "UTC"})
    store.save_config(config)
    store.save_brief(config, {"generated_for_date": "2026-09-09",
                             "generated_at": "2026-09-09T06:00:00+00:00",
                             "headline": "A synthetic headline", "note": "A synthetic note"})
    # CI deliberately keeps its invented password in PGPASSWORD, outside the
    # URL. The drill accepts only explicit source parameters, not PG defaults.
    source = make_conninfo(database_url(), password=os.environ.get("PGPASSWORD"))
    report = run(pg_bin, source, scratch_parent)
    assert report["status"] == "passed"
    assert report["families_checked"] >= 1
    assert report["cleanup"] == "passed"
    assert report["sampled_invalid_screen_tokens"] == int(legacy_token)
    assert not list(scratch_parent.iterdir())
    # Source is intact, including its brief, after the scratch cluster is gone.
    assert store.load_payload(config)["headline"] == "A synthetic headline"


def test_failed_restore_cleans_up_the_real_server(pg_bin, scratch_parent, monkeypatch):
    def fail_dump(pg_bin, name, args, env, **kwargs):
        if name == "pg_dump":
            raise DrillError("Synthetic backup failure")
        return command(pg_bin, name, args, env, **kwargs)
    monkeypatch.setattr("ops.restore_drill.command", fail_dump)
    with pytest.raises(DrillError, match="Synthetic backup failure"):
        run(pg_bin, "dbname=not_used", scratch_parent)
    assert not list(scratch_parent.iterdir())
