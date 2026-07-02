"""Tests for the /inbox routes (P2) — triage pass and triaged listing."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import desktop_store, triage
from gateway.routes import inbox as inbox_route


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Minimal app around the inbox router with an isolated DB, inbox, and stub LLM."""
    db_file = tmp_path / "kitty" / "kitty.db"
    inbox_file = tmp_path / "inbox.jsonl"
    monkeypatch.setattr(triage, "TRIAGE_DB_FILE", db_file, raising=False)
    real_read = desktop_store.read_inbox
    monkeypatch.setattr(
        desktop_store,
        "read_inbox",
        lambda limit=20, inbox_file=inbox_file: real_read(limit=limit, inbox_file=inbox_file),
    )
    monkeypatch.setattr(
        triage,
        "_default_llm",
        lambda prompt: json.dumps(
            {"bucket": "now", "confidence": 0.9, "rationale": "do it today"}
        ),
    )
    app = FastAPI()
    app.include_router(inbox_route.router)
    test_client = TestClient(app)
    test_client.inbox_file = inbox_file
    return test_client


def test_triage_pass_returns_counts(client):
    desktop_store.append_text_capture(text="ship the thing", inbox_file=client.inbox_file)

    r = client.post("/inbox/triage")

    assert r.status_code == 200
    body = r.json()
    assert body["processed"] == 1
    assert body["counts"]["now"] == 1


def test_triaged_listing_after_pass(client):
    desktop_store.append_text_capture(text="ship the thing", inbox_file=client.inbox_file)
    client.post("/inbox/triage")

    r = client.get("/inbox/triaged")

    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["bucket"] == "now"
    assert entries[0]["text"] == "ship the thing"


def test_triaged_bucket_filter_rejects_unknown_bucket(client):
    r = client.get("/inbox/triaged", params={"bucket": "nonsense"})

    assert r.status_code == 400


def test_triaged_bucket_filter_returns_only_that_bucket(client):
    desktop_store.append_text_capture(text="ship the thing", inbox_file=client.inbox_file)
    client.post("/inbox/triage")

    now_entries = client.get("/inbox/triaged", params={"bucket": "now"}).json()["entries"]
    drop_entries = client.get("/inbox/triaged", params={"bucket": "drop"}).json()["entries"]

    assert len(now_entries) == 1
    assert drop_entries == []
