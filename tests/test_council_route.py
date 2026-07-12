"""End-to-end test for the /council HTTP route (no real model calls)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from gateway.council import TaskDispatch

from gateway.app import app


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[TaskDispatch] = []

    def run(self, agent: str, dispatch: TaskDispatch) -> str:
        self.calls.append(dispatch)
        return f"ok:{agent}"

    def synthesize(self, question: str, parts: list, state: str) -> str:
        return "ok-answer"


def test_council_route_dispatches_through_http(monkeypatch) -> None:
    backend = FakeBackend()
    # Route uses the default backend unless injected; swap it for the fake.
    monkeypatch.setattr("gateway.council._default_backend", lambda: backend)

    with TestClient(app) as client:
        resp = client.post("/council", json={"message": "research X then implement Y"})

    assert resp.status_code == 200
    body = resp.json()
    agents = {r["assigned_to"] for r in body["results"]}
    assert {"claude", "deepseek"} <= agents
    assert len(backend.calls) == 2  # one dispatch per decomposed task
    # Response exposes routing + timing metadata.
    assert len(body["routing"]) == 2
    assert body["routing"][0].keys() >= {"task_id", "category", "agent", "priority"}
    assert len(body["timings"]) == 2
    assert body["timings"][0].keys() >= {"task_id", "ms"}
    assert body["total_ms"] >= 0


def test_council_route_greeting_shortcircuits(monkeypatch) -> None:
    backend = FakeBackend()
    monkeypatch.setattr("gateway.council._default_backend", lambda: backend)

    with TestClient(app) as client:
        resp = client.post("/council", json={"message": "hi"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []          # no agent invoked
    assert backend.calls == []            # run never called
    assert "Hello" in body["answer"]
    assert body["routing"] == [] and body["timings"] == []
