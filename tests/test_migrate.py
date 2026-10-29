"""Which database `migrate.py` applies the schema to.

The only question this file asks, because it is the only one whose wrong answer
is quiet. A migration tool pointed at the wrong database either reports a schema
that is already up to date — which reads as success — or changes a live one,
which reads as nothing at all until later.

Nothing here connects: `target()` is the decision, and the decision is what has
to hold. psycopg is imported inside the tests, so a self-hoster's suite still
collects without the cloud driver.
"""

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def no_inherited_database(monkeypatch):
    """A developer's own shell must not decide what these tests see.

    `PGHOST` and `PGHOSTADDR` included: libpq reads them when a URL names no
    host, which is the whole subject of two of the tests below.
    """
    for name in ("DATABASE_URL_DIRECT", "PGHOST", "PGHOSTADDR"):
        monkeypatch.delenv(name, raising=False)


def target(*args):
    import migrate

    return migrate.target(*args)


def test_nothing_named_means_the_development_database():
    """`python migrate.py` at a laptop is a request about that laptop."""
    from dinkydash.db import DEV_DATABASE_URL

    conninfo, where = target()
    assert conninfo == DEV_DATABASE_URL
    assert "development" in where


def test_it_never_reads_database_url(monkeypatch):
    """`migrate.py` never reads `DATABASE_URL`: in production that is the pooler."""
    monkeypatch.setenv("DATABASE_URL", "postgresql:///somebody_elses_dev")
    assert target()[0] != "postgresql:///somebody_elses_dev"


@pytest.mark.parametrize("variable", ["PGHOST", "PGHOSTADDR"])
def test_the_default_is_refused_when_libpq_would_send_it_elsewhere(monkeypatch, variable):
    """A URL with no host is local only for as long as libpq's fallbacks agree."""
    monkeypatch.setenv(variable, "10.0.0.9" if variable == "PGHOSTADDR" else "db.example")
    with pytest.raises(ValueError, match="PGHOST"):
        target()


@pytest.mark.parametrize("value", ["/tmp", "127.0.0.1", "localhost"])
def test_a_local_fallback_leaves_the_default_alone(monkeypatch, value):
    from dinkydash.db import DEV_DATABASE_URL

    monkeypatch.setenv("PGHOST", value)
    assert target()[0] == DEV_DATABASE_URL


def test_a_named_database_is_not_second_guessed(monkeypatch):
    """Naming one is the consent, and production is legitimately somewhere else."""
    monkeypatch.setenv("PGHOST", "db.example")
    assert target("postgresql://cluster.example/db")[0] == "postgresql://cluster.example/db"
    monkeypatch.setenv("DATABASE_URL_DIRECT", "postgresql://cluster.example/db")
    assert target()[0] == "postgresql://cluster.example/db"


def test_the_platforms_own_variable_is_used(monkeypatch):
    """App Platform's pre-deploy job sets it in the container's environment."""
    monkeypatch.setenv("DATABASE_URL_DIRECT", "postgresql://cluster.example/db")
    conninfo, where = target()
    assert conninfo == "postgresql://cluster.example/db"
    assert where == "DATABASE_URL_DIRECT"


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_variable_is_not_a_database(monkeypatch, blank):
    from dinkydash.db import DEV_DATABASE_URL

    monkeypatch.setenv("DATABASE_URL_DIRECT", blank)
    assert target()[0] == DEV_DATABASE_URL


def test_an_explicit_url_wins(monkeypatch):
    monkeypatch.setenv("DATABASE_URL_DIRECT", "postgresql://cluster.example/db")
    conninfo, where = target("postgresql:///scratch")
    assert conninfo == "postgresql:///scratch"
    assert "command line" in where


@pytest.mark.parametrize("blank", ["", "   "])
def test_an_empty_flag_is_refused_rather_than_fallen_back_from(monkeypatch, blank):
    """`--database-url "$UNSET"` must not quietly become some other database."""
    monkeypatch.setenv("DATABASE_URL_DIRECT", "postgresql://cluster.example/db")
    with pytest.raises(ValueError):
        target(blank)


def test_a_supplied_connection_string_is_never_repeated(monkeypatch):
    """The name is logged, and a string somebody supplied can carry a password.

    The development default is the exception and is printed in full: it is a
    constant in the repository, so there is nothing in it to keep.
    """
    monkeypatch.setenv("DATABASE_URL_DIRECT", "postgresql://cluster.example/db")
    assert "cluster.example" not in target()[1]
    assert "other.example" not in target("postgresql://other.example/db")[1]


def test_dotenv_is_not_read(tmp_path):
    """A developer's `.env` holds the live cluster under production's own key.

    Run from a directory holding such a file, in a subprocess, because reading
    `.env` is something an import does once and no monkeypatched environment
    can undo.
    """
    (tmp_path / ".env").write_text("DATABASE_URL_DIRECT=postgresql://cluster.example/live\n")
    environment = {k: v for k, v in os.environ.items() if k != "DATABASE_URL_DIRECT"}
    environment["PYTHONPATH"] = str(ROOT)
    chosen = subprocess.run(
        [sys.executable, "-c", "import migrate; print(migrate.target()[0])"],
        cwd=tmp_path, capture_output=True, text=True, env=environment)
    assert chosen.returncode == 0, chosen.stderr
    assert "cluster.example" not in chosen.stdout
    assert "dinkydash_dev" in chosen.stdout
