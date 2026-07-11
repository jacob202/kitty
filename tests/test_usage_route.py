"""Tests for the read-only usage summary endpoint."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import usage as usage_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    ledger = tmp_path / "kitty_token_log.jsonl"
    monkeypatch.setattr(usage_route, "KITTY_TOKEN_LOG_FILE", ledger)
    app = FastAPI()
    app.include_router(usage_route.router)
    return TestClient(app), ledger


def _write_rows(ledger, *rows: dict) -> None:
    ledger.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def test_summary_uses_only_llm_usage_records_and_reports_storage_telemetry(client):
    test_client, ledger = client
    _write_rows(
        ledger,
        {
            "ts": 1.0,
            "date": "2026-07-10",
            "provider": "litellm",
            "model": "deepseek/deepseek-v4-flash",
            "operation": "chat.completions.create",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "metadata": {"route": "litellm_proxy"},
        },
        {
            "ts": "2026-07-10T10:00:00+00:00",
            "kind": "storage_write",
            "store": "todos",
            "op": "add",
            "key": "5",
            "ms": 1.5,
        },
    )

    response = test_client.get("/usage/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["totals"] == {"calls": 1, "tokens": 15}
    assert body["estimated_cost"]["usd"] >= 0
    assert body["ledger"] == {"llm_usage_records": 1, "storage_write_records": 1}


def test_summary_filters_usage_records_by_since_and_provider(client):
    test_client, ledger = client
    _write_rows(
        ledger,
        {
            "ts": 1.0,
            "date": "2026-07-09",
            "provider": "litellm",
            "model": "deepseek/deepseek-v4-flash",
            "operation": "chat.completions.create",
            "usage": {"total_tokens": 10},
            "metadata": {},
        },
        {
            "ts": 2.0,
            "date": "2026-07-10",
            "provider": "openrouter",
            "model": "deepseek/deepseek-r1",
            "operation": "brief.synthesis",
            "usage": {"total_tokens": 25},
            "metadata": {},
        },
    )

    response = test_client.get("/usage/summary?since=2026-07-10&provider=openrouter")

    assert response.status_code == 200
    assert response.json()["totals"] == {"calls": 1, "tokens": 25}


def test_summary_fails_loudly_for_corrupt_ledger_data(client):
    test_client, ledger = client
    ledger.write_text("not-json\n", encoding="utf-8")

    response = test_client.get("/usage/summary")

    assert response.status_code == 500
    assert "line 1" in response.json()["detail"]
    assert "invalid JSON" in response.json()["detail"]


def test_summary_fails_loudly_when_ledger_is_unreadable(client):
    test_client, ledger = client
    ledger.mkdir()

    response = test_client.get("/usage/summary")

    assert response.status_code == 500
    assert "unreadable" in response.json()["detail"]
