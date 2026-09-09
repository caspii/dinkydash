"""Liveness means a completed pass, not successful model or calendar calls."""

import logging

import pytest
import requests

import worker
from worker import heartbeat


@pytest.fixture
def pass_calls(monkeypatch):
    calls = []
    monkeypatch.setattr("dinkydash.lifecycle.expire_trials", lambda pool: calls.append("expire"))
    monkeypatch.setattr(worker, "tick_all", lambda *a, **kw: calls.append("tick") or 0)
    monkeypatch.setattr(worker, "sweep_logins", lambda pool: calls.append("sweep") or 0)
    monkeypatch.setattr(heartbeat, "ping", lambda url: calls.append("ping"))
    return calls


def test_ping_follows_a_completed_pass_even_with_no_successful_families(pass_calls):
    worker.run_pass(object(), worker.Stopping(), "https://monitor.example/fake-token")
    assert pass_calls == ["expire", "tick", "sweep", "ping"]


def test_interrupted_pass_does_not_ping(pass_calls, monkeypatch):
    stopping = worker.Stopping()
    def interrupted(*a, **kw):
        pass_calls.append("tick")
        stopping.request()
        return 1
    monkeypatch.setattr(worker, "tick_all", interrupted)
    worker.run_pass(object(), stopping, "https://monitor.example/fake-token")
    assert pass_calls == ["expire", "tick", "sweep"]


def test_database_enumeration_failure_does_not_ping(pass_calls, monkeypatch):
    def fail(*a, **kw):
        raise RuntimeError("Database is unavailable")
    monkeypatch.setattr(worker, "tick_all", fail)
    with pytest.raises(RuntimeError):
        worker.run_pass(object(), worker.Stopping(), "https://monitor.example/fake-token")
    assert pass_calls == ["expire"]


def test_missing_configuration_is_visible_and_sends_nothing(monkeypatch, caplog):
    monkeypatch.delenv(heartbeat.ENVIRONMENT_KEY, raising=False)
    with caplog.at_level(logging.WARNING):
        assert heartbeat.configured_url() is None
    assert "not configured" in caplog.text
    assert heartbeat.ping(None) is False


@pytest.mark.parametrize("url", ["http://monitor.example/fake-token", "https://u:p@monitor.example/",
                                 "https://monitor.example/fake-token#fragment", "https://x:bad/",
                                 "https:///missing-host", "https://[broken"])
def test_invalid_url_is_rejected_without_echoing_it(monkeypatch, url):
    monkeypatch.setenv(heartbeat.ENVIRONMENT_KEY, url)
    with pytest.raises(ValueError) as error:
        heartbeat.configured_url()
    assert url not in str(error.value)


def test_https_ping_url_is_loaded(monkeypatch):
    monkeypatch.setenv(heartbeat.ENVIRONMENT_KEY, " https://monitor.example/fake-token ")
    assert heartbeat.configured_url() == "https://monitor.example/fake-token"


@pytest.fixture
def sent(monkeypatch):
    class Session:
        trust_env = True
        status_code = 200
        error = None
        def __init__(self):
            self.calls = []
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if self.error:
                raise self.error
            return self
    session = Session()
    monkeypatch.setattr(requests, "Session", lambda: session)
    return session


def test_ping_carries_no_data_and_uses_a_bounded_direct_request(sent):
    assert heartbeat.ping("https://monitor.example/fake-token") is True
    assert sent.trust_env is False
    assert sent.calls == [("https://monitor.example/fake-token", {
        "data": b"", "timeout": 5, "allow_redirects": False, "stream": True,
    })]


@pytest.mark.parametrize("code", [301, 401, 429, 500])
def test_rejections_do_not_retry_or_expose_the_url(sent, code, caplog):
    sent.status_code = code
    assert heartbeat.ping("https://monitor.example/fake-token") is False
    assert len(sent.calls) == 1
    assert "fake-token" not in caplog.text
    assert str(code) in caplog.text


@pytest.mark.parametrize("kind", [requests.Timeout, requests.ConnectionError])
def test_transport_failure_does_not_stop_the_worker_or_log_credentials(sent, kind, caplog):
    sent.error = kind("Could not connect to https://monitor.example/fake-token")
    assert heartbeat.ping("https://monitor.example/fake-token") is False
    assert len(sent.calls) == 1
    assert "fake-token" not in caplog.text
