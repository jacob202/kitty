"""Tests for the /memories routes — long-term memory list and delete."""
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from gateway import memory as memory_module
from gateway.errors import KittyError
from gateway.routes import memories as memories_route

_MOCK_MEMORIES = [
    {"id": "mem_1", "text": "Jacobs birthday is Feb 14", "metadata": {"namespace": "facts"}},
    {"id": "mem_2", "text": "Prefers async communication", "metadata": {"namespace": "patterns"}},
]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        memory_module, "list_memories",
        lambda namespace=None, limit=50: (
            [m for m in _MOCK_MEMORIES if namespace is None or m["metadata"]["namespace"] == namespace]
        )[:limit],
    )

    def _delete_memory(memory_id: str) -> bool:
        return any(m["id"] == memory_id for m in _MOCK_MEMORIES)

    monkeypatch.setattr(memory_module, "delete_memory", _delete_memory)

    app = FastAPI()

    @app.exception_handler(KittyError)
    def _handle_kitty_error(request, exc: KittyError):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(memories_route.router)
    return TestClient(app)


class TestListMemories:
    def test_happy_path(self, client):
        r = client.get("/memories")
        assert r.status_code == 200
        body = r.json()
        assert "memories" in body
        assert len(body["memories"]) == 2

    def test_filters_by_namespace(self, client):
        r = client.get("/memories", params={"namespace": "facts"})
        assert r.status_code == 200
        for m in r.json()["memories"]:
            assert m["metadata"]["namespace"] == "facts"

    def test_empty_namespace_returns_empty(self, client):
        r = client.get("/memories", params={"namespace": "nonexistent"})
        assert r.status_code == 200
        assert r.json()["memories"] == []

    def test_limit_param(self, client):
        r = client.get("/memories", params={"limit": 1})
        assert r.status_code == 200
        assert len(r.json()["memories"]) == 1


class TestDeleteMemory:
    def test_happy_path(self, client):
        r = client.delete("/memories/mem_1")
        assert r.status_code == 200
        body = r.json()
        assert body["deleted"] is True
        assert body["memory_id"] == "mem_1"

    def test_not_found_returns_404(self, client):
        r = client.delete("/memories/nonexistent")
        assert r.status_code == 404
        body = r.json()
        assert "was not found" in body["message"]
        assert "memory_id" in str(body)
