"""Tests for the /chronicle/tips endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import chronicle as chronicle_route

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(chats: list[dict], monkeypatch) -> TestClient:
    # Monkeypatch the store reference inside the service module, which is where
    # the actual store call now lives (the route delegates to the service).
    monkeypatch.setattr(chronicle_route.chats_store, "list_chats", lambda: chats)
    app = FastAPI()
    app.include_router(chronicle_route.router)
    return TestClient(app)


def _chat(
    *,
    title: str = "untitled",
    messages: list[dict] | None = None,
    model: str = "deepseek/deepseek-v4-flash",
    created_at: str | None = None,
    objective: str | None = None,
) -> dict:
    return {
        "id": title,
        "title": title,
        "messages": messages or [],
        "model": model,
        "createdAt": created_at or "2026-07-01T10:00:00+00:00",
        "updatedAt": created_at or "2026-07-01T10:00:00+00:00",
        "objective": objective,
    }


# ---------------------------------------------------------------------------
# HTTP layer tests
# ---------------------------------------------------------------------------

class TestChronicleEndpoint:
    def test_returns_200_and_required_keys(self, monkeypatch):
        client = _make_client([], monkeypatch)
        response = client.get("/chronicle/tips")
        assert response.status_code == 200
        body = response.json()
        assert "tips" in body
        assert "tip_count" in body
        assert "summary" in body

    def test_empty_history_returns_new_user_tip(self, monkeypatch):
        client = _make_client([], monkeypatch)
        body = client.get("/chronicle/tips").json()
        assert body["summary"]["session_count"] == 0
        assert any("first session" in tip.lower() for tip in body["tips"])

    def test_tip_count_matches_tips_list(self, monkeypatch):
        chats = [_chat(title=f"chat {i}", messages=[{"role": "user"}, {"role": "assistant"}]) for i in range(5)]
        client = _make_client(chats, monkeypatch)
        body = client.get("/chronicle/tips").json()
        assert body["tip_count"] == len(body["tips"])

    def test_summary_session_count(self, monkeypatch):
        chats = [_chat() for _ in range(7)]
        client = _make_client(chats, monkeypatch)
        body = client.get("/chronicle/tips").json()
        assert body["summary"]["session_count"] == 7

    def test_summary_message_count(self, monkeypatch):
        msgs = [{"role": "user"}, {"role": "assistant"}]
        chats = [_chat(messages=msgs) for _ in range(4)]
        client = _make_client(chats, monkeypatch)
        body = client.get("/chronicle/tips").json()
        assert body["summary"]["message_count"] == 8

    def test_peak_hour_detected(self, monkeypatch):
        chats = [
            _chat(created_at="2026-07-10T09:15:00+00:00"),
            _chat(created_at="2026-07-11T09:30:00+00:00"),
            _chat(created_at="2026-07-12T09:45:00+00:00"),
        ]
        client = _make_client(chats, monkeypatch)
        body = client.get("/chronicle/tips").json()
        assert body["summary"]["peak_hour"] == 9
        assert any("09:00" in tip for tip in body["tips"])

    def test_top_topics_extracted_from_titles(self, monkeypatch):
        chats = [
            _chat(title="python refactoring help"),
            _chat(title="python testing strategies"),
            _chat(title="database migration python"),
        ]
        client = _make_client(chats, monkeypatch)
        body = client.get("/chronicle/tips").json()
        assert "python" in body["summary"]["top_topics"]

    def test_no_objective_tip_fires_for_three_or_more_sessions(self, monkeypatch):
        chats = [_chat(title=f"chat {i}", objective=None) for i in range(3)]
        client = _make_client(chats, monkeypatch)
        body = client.get("/chronicle/tips").json()
        assert any("thread goal" in tip.lower() for tip in body["tips"])

    def test_objective_set_suppresses_no_objective_tip(self, monkeypatch):
        chats = [_chat(title="chat with goal", objective="build the thing")]
        client = _make_client(chats, monkeypatch)
        body = client.get("/chronicle/tips").json()
        assert not any("thread goal" in tip.lower() for tip in body["tips"])

    def test_short_sessions_tip(self, monkeypatch):
        chats = [_chat(messages=[{"role": "user"}]) for _ in range(6)]
        client = _make_client(chats, monkeypatch)
        body = client.get("/chronicle/tips").json()
        assert any("longer thread" in tip.lower() for tip in body["tips"])

    def test_single_model_tip(self, monkeypatch):
        chats = [_chat(model="deepseek/deepseek-v4-flash") for _ in range(4)]
        client = _make_client(chats, monkeypatch)
        body = client.get("/chronicle/tips").json()
        assert body["summary"]["model_spread"] == 1
        assert any("single model" in tip.lower() for tip in body["tips"])

    def test_multiple_models_suppresses_single_model_tip(self, monkeypatch):
        chats = [
            _chat(model="deepseek/deepseek-v4-flash"),
            _chat(model="gpt-4o"),
            _chat(model="claude-3-haiku"),
        ]
        client = _make_client(chats, monkeypatch)
        body = client.get("/chronicle/tips").json()
        assert not any("single model" in tip.lower() for tip in body["tips"])
