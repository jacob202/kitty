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


def test_council_route_dispatches_through_http(monkeypatch) -> None:
    backend = FakeBackend()
    # Route uses the default backend unless injected; swap it for the fake.
    monkeypatch.setattr("gateway.council._default_backend", lambda: backend)

    with TestClient(app) as client:
        resp = client.post("/council", json={"message": "research X and implement Y"})

    assert resp.status_code == 200
    body = resp.json()
    agents = {r["assigned_to"] for r in body["results"]}
    assert {"claude", "deepseek"} <= agents
    assert len(backend.calls) == 2  # one dispatch per decomposed task


def test_council_route_handles_trivial_inline(monkeypatch) -> None:
    backend = FakeBackend()
    monkeypatch.setattr("gateway.council._default_backend", lambda: backend)

    with TestClient(app) as client:
        resp = client.post("/council", json={"message": "what port is the gateway on"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["results"][0]["assigned_to"] == "council"  # inline, no agent
    assert backend.calls == []
