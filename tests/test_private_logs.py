"""Exercise the service entry points with invented family text and credentials."""

import logging
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import unquote

import pytest

import generate as cli
from dinkydash import runner
from dinkydash.claude_client import GenerationError
from dinkydash.store import FileStore
from test_worker import FakeBudget, FakePool
from web.routes.auth import quieten_the_request_log
from worker import tick_all


@pytest.mark.parametrize("logger_name", ["werkzeug", "gunicorn.access"])
@pytest.mark.parametrize("path", [
    "/s/abcdEfghjkmn",
    "/s/abcd%45fghjkmn",
    "/s/abcdEfghjkmn/manifest.webmanifest",
    "/s/short",
    "/s/abcd!fghjkmn",
    "/s/abcd💛fghjkmn",
    "/%73/abcdEfghjkmn",
    "%2Fs%2FabcdEfghjkmn",
    "/s%2FabcdEfghjkmn",
    "/S/abcdEfghjkmn",
    "/s/abcd/efghjkmn",
    "/s/abcd?efghjkmn",
    "/s/abcd'fghjkmn",
    '/s/abcd"fghjkmn',
])
def test_request_loggers_redact_the_whole_credential_even_when_invalid(
        logger_name, path, caplog):
    quieten_the_request_log()
    with caplog.at_level(logging.INFO, logger=logger_name):
        logging.getLogger(logger_name).info('GET %s HTTP/1.1 %d', path, 404)
    message = caplog.records[-1].getMessage()
    assert "[redacted]" in message
    assert "abcd" not in message and "fghjkmn" not in message and "short" not in message
    assert "HTTP/1.1 404" in message


@pytest.mark.parametrize("logger_name", ["werkzeug", "gunicorn.access"])
def test_request_loggers_preserve_ordinary_request_fields(logger_name, caplog):
    quieten_the_request_log()
    with caplog.at_level(logging.INFO, logger=logger_name):
        logging.getLogger(logger_name).info("GET %s HTTP/1.1 %d", "/settings/people", 200)
    assert caplog.records[-1].getMessage() == "GET /settings/people HTTP/1.1 200"


@pytest.mark.parametrize("encoded", ["%20", "%09", "%0A", "%C2%A0", "%27", "%22"])
@pytest.mark.parametrize("server", ["gunicorn", "werkzeug"])
def test_server_formatting_cannot_expose_the_tail_of_a_decoded_token(encoded, server, caplog):
    path = f"/s/abcd{encoded}fghjkmn"
    quieten_the_request_log()
    with caplog.at_level(logging.INFO):
        if server == "gunicorn":
            glogging = pytest.importorskip("gunicorn.glogging")
            # Use the real atoms and escaping, without changing global handlers.
            logger = object.__new__(glogging.Logger)
            logger.cfg = SimpleNamespace(accesslog="-", access_log_format=
                                         '"%(m)s %(U)s %(H)s" %(s)s')
            logger.access_log = logging.getLogger("gunicorn.access")
            environ = {"REQUEST_METHOD": "GET", "RAW_URI": path,
                       "PATH_INFO": unquote(path), "SERVER_PROTOCOL": "HTTP/1.1"}
            response = SimpleNamespace(status="404 NOT FOUND", headers=[], sent=0)
            logger.access(response, {}, environ, timedelta())
        else:
            from werkzeug.serving import WSGIRequestHandler

            handler = object.__new__(WSGIRequestHandler)
            handler.path, handler.command, handler.request_version = path, "GET", "HTTP/1.1"
            handler.client_address = ("127.0.0.1", 1234)
            handler.log_request(404)

    assert "abcd" not in caplog.text and "fghjkmn" not in caplog.text
    assert "[redacted]" in caplog.text
    assert "HTTP/1.1" in caplog.text and "404" in caplog.text


@pytest.fixture
def generated_store(tmp_path, monkeypatch):
    path = tmp_path / "config.yaml"
    path.write_text('family_name: "Invented family"\ncalendars: []\n')
    store = FileStore(path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")

    def generated(config, today, events, **kwargs):
        return {"generated_for_date": today.isoformat(),
                "headline": "Private headline marker", "note": "Private note marker",
                "note_kind": "fact", "input_tokens": 123, "output_tokens": 45}

    monkeypatch.setattr(runner, "generate", generated)
    return store


def test_real_worker_tick_logs_metadata_without_generated_text(generated_store, caplog):
    with caplog.at_level(logging.INFO):
        assert tick_all(FakePool(["family"]), store_factory=lambda _: generated_store,
                        budget_factory=FakeBudget) == 1
    assert "Board written for" in caplog.text
    assert "123 tokens in, 45 out" in caplog.text
    assert "Private headline marker" not in caplog.text
    assert "Private note marker" not in caplog.text
    assert generated_store.load_payload(generated_store.load_config())["headline"] == "Private headline marker"


def test_an_explicit_cli_run_still_reports_its_result(generated_store, caplog):
    with caplog.at_level(logging.INFO):
        assert cli.main(["--config", str(generated_store.config_path)]) == 0
    assert "Private headline marker" in caplog.text
    assert "Private note marker" in caplog.text


def test_a_failed_worker_generation_still_reports_the_failure(generated_store, caplog, monkeypatch):
    def failed(*args, **kwargs):
        raise GenerationError("Provider unavailable")

    monkeypatch.setattr(runner, "generate", failed)
    with caplog.at_level(logging.INFO):
        tick_all(FakePool(["family"]), store_factory=lambda _: generated_store,
                 budget_factory=FakeBudget)
    assert "Provider unavailable" in caplog.text
    assert "the next tick will try again" in caplog.text
