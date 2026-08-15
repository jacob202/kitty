from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def test_repository_probe_rejects_dirty_tree(monkeypatch, tmp_path: Path) -> None:
    from gateway import readiness

    def fake_git(args: list[str], cwd: Path) -> str:
        if args == ["rev-parse", "HEAD"]:
            return "abc123\n"
        if args == ["status", "--porcelain", "--untracked-files=normal"]:
            return " M gateway/app.py\n"
        raise AssertionError(args)

    monkeypatch.setattr(readiness, "_git", fake_git)
    result = readiness.repository_status(tmp_path, expected_commit="abc123")

    assert result["ready"] is False
    assert result["commit"] == "abc123"
    assert result["dirty"] is True
    assert "dirty" in result["reason"]


def test_repository_probe_rejects_expected_commit_mismatch(monkeypatch, tmp_path: Path) -> None:
    from gateway import readiness

    def fake_git(args: list[str], cwd: Path) -> str:
        if args == ["rev-parse", "HEAD"]:
            return "actual\n"
        if args == ["status", "--porcelain", "--untracked-files=normal"]:
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(readiness, "_git", fake_git)
    result = readiness.repository_status(tmp_path, expected_commit="expected")

    assert result["ready"] is False
    assert result["dirty"] is False
    assert "expected commit" in result["reason"]


@pytest.mark.asyncio
async def test_chat_readiness_fails_when_only_local_route_is_configured_but_down(monkeypatch) -> None:
    from gateway import readiness

    monkeypatch.setattr(
        readiness,
        "describe_providers",
        lambda: {
            "active": "auto",
            "providers": [
                {"name": "local", "configured": True, "disabled": False, "kind": "local", "base_url": "http://127.0.0.1:8010/v1"},
                {"name": "openrouter", "configured": False, "disabled": False, "kind": "api_credit", "base_url": "https://openrouter.ai/api/v1"},
            ],
        },
    )
    monkeypatch.setattr(readiness, "_local_provider_reachable", lambda _url: _async(False))

    result = await readiness.chat_status()

    assert result["ready"] is False
    assert result["usable"] == []
    assert result["configured"] == ["local"]


@pytest.mark.asyncio
async def test_chat_readiness_honors_exact_active_provider(monkeypatch) -> None:
    from gateway import readiness

    monkeypatch.setattr(
        readiness,
        "describe_providers",
        lambda: {
            "active": "local",
            "providers": [
                {"name": "local", "configured": True, "disabled": False, "kind": "local", "base_url": "http://127.0.0.1:8010/v1"},
                {"name": "openrouter", "configured": True, "disabled": False, "kind": "api_credit", "base_url": "https://openrouter.ai/api/v1"},
            ],
        },
    )
    monkeypatch.setattr(readiness, "_local_provider_reachable", lambda _url: _async(False))

    result = await readiness.chat_status()

    assert result["ready"] is False
    assert result["active"] == "local"
    assert result["usable"] == []


@pytest.mark.asyncio
async def test_chat_readiness_accepts_configured_cloud_route_without_spending(monkeypatch) -> None:
    from gateway import readiness

    monkeypatch.setattr(
        readiness,
        "describe_providers",
        lambda: {
            "active": "auto",
            "providers": [
                {"name": "local", "configured": True, "disabled": False, "kind": "local", "base_url": "http://127.0.0.1:8010/v1"},
                {"name": "openrouter", "configured": True, "disabled": False, "kind": "api_credit", "base_url": "https://openrouter.ai/api/v1"},
            ],
        },
    )
    monkeypatch.setattr(readiness, "_local_provider_reachable", lambda _url: _async(False))

    result = await readiness.chat_status()

    assert result["ready"] is True
    assert result["usable"] == ["openrouter"]
    assert result["probe_mode"] == "configuration-only for remote providers"


def test_builder_readiness_requires_real_integrity_checked_db(monkeypatch) -> None:
    from gateway import readiness
    from gateway.builder_doctor import Check

    monkeypatch.setattr(
        readiness,
        "_builder_database_checks",
        lambda: [Check("WARN", "db:open", "no queue DB yet")],
    )
    assert readiness.builder_status()["ready"] is False

    monkeypatch.setattr(
        readiness,
        "_builder_database_checks",
        lambda: [
            Check("PASS", "db:open", "/tmp/builder_queue.db"),
            Check("PASS", "db:integrity_check", "ok"),
        ],
    )
    assert readiness.builder_status()["ready"] is True


def test_ready_endpoint_fails_closed_while_liveness_stays_available(monkeypatch) -> None:
    from gateway import readiness
    from gateway.app import app

    async def fake_snapshot() -> dict:
        return {
            "status": "not_ready",
            "ready": False,
            "components": {"chat": {"ready": False, "reason": "no usable chat route"}},
        }

    monkeypatch.setattr(readiness, "readiness_snapshot", fake_snapshot)
    with patch.dict(os.environ, {"GATEWAY_SECRET": "test-secret", "KITTY_ENV": "prod"}):
        client = TestClient(app)
        health = client.get("/health")
        ready = client.get("/ready", headers={"Authorization": "Bearer test-secret"})

    assert health.status_code == 200
    assert ready.status_code == 503
    assert ready.json()["ready"] is False


async def _async(value: bool) -> bool:
    return value
