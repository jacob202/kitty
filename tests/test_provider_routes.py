"""Focused tests for the provider restart route's public error boundary."""

from __future__ import annotations

import logging
import subprocess
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from gateway.routes import providers

LOGGER_NAME = "kitty.routes.providers"


@pytest.fixture
def provider_client():
    app = FastAPI()
    app.include_router(providers.router)
    return TestClient(app)


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["launchctl"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _raiser(exc):
    def _run(*args, **kwargs):
        raise exc

    return _run


@pytest.fixture
def one_probe_then_timeout(monkeypatch):
    """Collapse the 20s liveliness window to a single probe, then expire it."""
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr(providers.time, "monotonic", lambda: next(ticks, 21.0))
    monkeypatch.setattr(providers.time, "sleep", lambda _seconds: None)


def test_launchctl_oserror_is_logged_without_leaking_exception(monkeypatch, caplog):
    sentinel = "SENTINEL_LAUNCHCTL_OSERROR_7f2a"
    monkeypatch.setattr(providers.subprocess, "run", _raiser(OSError(sentinel)))

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        with pytest.raises(HTTPException) as raised:
            providers._restart_litellm()

    assert raised.value.status_code == 500
    assert raised.value.detail == providers._RESTART_FAILED_DETAIL
    assert sentinel not in raised.value.detail
    assert sentinel in caplog.text


def test_launchctl_timeout_is_logged_without_leaking_exception(monkeypatch, caplog):
    sentinel = "SENTINEL_LAUNCHCTL_TIMEOUT_91bd"
    monkeypatch.setattr(
        providers.subprocess,
        "run",
        _raiser(subprocess.TimeoutExpired(cmd=["launchctl", sentinel], timeout=15)),
    )

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        with pytest.raises(HTTPException) as raised:
            providers._restart_litellm()

    assert raised.value.status_code == 500
    assert raised.value.detail == providers._RESTART_FAILED_DETAIL
    assert sentinel not in raised.value.detail
    assert sentinel in caplog.text


@pytest.mark.parametrize("stream", ["stderr", "stdout"])
def test_launchctl_failure_output_is_logged_without_leaking(monkeypatch, caplog, stream):
    sentinel = f"SENTINEL_LAUNCHCTL_{stream.upper()}_3c8e"
    monkeypatch.setattr(
        providers.subprocess,
        "run",
        lambda *args, **kwargs: _completed(returncode=7, **{stream: sentinel}),
    )

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        with pytest.raises(HTTPException) as raised:
            providers._restart_litellm()

    assert raised.value.status_code == 500
    assert raised.value.detail == providers._RESTART_FAILED_DETAIL
    assert sentinel not in raised.value.detail
    assert sentinel in caplog.text


def test_health_probe_exception_is_logged_without_leaking(
    monkeypatch, caplog, one_probe_then_timeout
):
    sentinel = "SENTINEL_HEALTH_PROBE_5e31"
    monkeypatch.setattr(providers.subprocess, "run", lambda *args, **kwargs: _completed())
    monkeypatch.setattr(urllib.request, "urlopen", _raiser(urllib.error.URLError(sentinel)))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        with pytest.raises(HTTPException) as raised:
            providers._restart_litellm()

    assert raised.value.status_code == 500
    assert raised.value.detail == providers._RESTART_UNHEALTHY_DETAIL
    assert sentinel not in raised.value.detail
    assert sentinel in caplog.text
    assert "attempt 1" in caplog.text
    assert "retrying" in caplog.text


def test_switch_endpoint_hides_launchctl_failure(
    monkeypatch, caplog, provider_client
):
    sentinel = "SENTINEL_ENDPOINT_LAUNCHCTL_2a4e"
    monkeypatch.setattr(providers, "_active_state", lambda: {"active": "openrouter"})
    monkeypatch.setattr(providers, "_rewrite_config", lambda _target: None)
    monkeypatch.setattr(providers.subprocess, "run", _raiser(OSError(sentinel)))

    with caplog.at_level(logging.ERROR, logger=LOGGER_NAME):
        response = provider_client.post(
            "/api/providers/switch", json={"target": "agentrouter"}
        )

    assert response.status_code == 500
    assert response.json() == {"detail": providers._RESTART_FAILED_DETAIL}
    assert sentinel not in response.text
    assert sentinel in caplog.text


def test_switch_endpoint_hides_health_probe_failure(
    monkeypatch, caplog, provider_client
):
    sentinel = "SENTINEL_ENDPOINT_HEALTH_70bf"
    monkeypatch.setattr(providers, "_active_state", lambda: {"active": "openrouter"})
    monkeypatch.setattr(providers, "_rewrite_config", lambda _target: None)
    monkeypatch.setattr(providers.subprocess, "run", lambda *args, **kwargs: _completed())
    monkeypatch.setattr(urllib.request, "urlopen", _raiser(urllib.error.URLError(sentinel)))
    monkeypatch.setattr(
        providers,
        "time",
        SimpleNamespace(
            monotonic=iter([0.0, 1.0, 21.0]).__next__,
            sleep=lambda _seconds: None,
        ),
    )

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        response = provider_client.post(
            "/api/providers/switch", json={"target": "agentrouter"}
        )

    assert response.status_code == 500
    assert response.json() == {"detail": providers._RESTART_UNHEALTHY_DETAIL}
    assert sentinel not in response.text
    assert sentinel in caplog.text


def test_healthy_restart_returns_without_error(monkeypatch):
    monkeypatch.setattr(providers.subprocess, "run", lambda *args, **kwargs: _completed())

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: _Resp())

    assert providers._restart_litellm() is None
