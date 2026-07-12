"""HTTP-layer contract tests for gateway/routes/memories.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.memory import MemoryError


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# --- GET /memories ---


def test_list_memories_returns_items(client: TestClient) -> None:
    items = [
        {"id": "mem-1", "memory": "Jacob prefers concise plans", "metadata": {"namespace": "facts"}},
        {"id": "mem-2", "memory": "Ships on Fridays", "metadata": {"namespace": "patterns"}},
    ]
    with patch("gateway.memory.list_memories", return_value=items) as mock_list:
        response = client.get("/memories")

    assert response.status_code == 200
    assert response.json() == {"memories": items}
    mock_list.assert_called_once_with(namespace=None, limit=50)


def test_list_memories_passes_namespace_and_limit_through(client: TestClient) -> None:
    with patch("gateway.memory.list_memories", return_value=[]) as mock_list:
        response = client.get("/memories", params={"namespace": "facts", "limit": 5})

    assert response.status_code == 200
    assert response.json() == {"memories": []}
    mock_list.assert_called_once_with(namespace="facts", limit=5)


def test_list_memories_invalid_limit_returns_422(client: TestClient) -> None:
    response = client.get("/memories", params={"limit": "not-a-number"})

    assert response.status_code == 422


def test_list_memories_backend_error_returns_500(client: TestClient) -> None:
    with patch("gateway.memory.list_memories", side_effect=MemoryError("mem0 unreachable")):
        response = client.get("/memories")

    assert response.status_code == 500
    assert response.json()["detail"] == "mem0 unreachable"


# --- DELETE /memories/{memory_id} ---


def test_delete_memory_success(client: TestClient) -> None:
    with patch("gateway.memory.delete_memory", return_value=True) as mock_delete:
        response = client.delete("/memories/mem-1")

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "memory_id": "mem-1"}
    mock_delete.assert_called_once_with("mem-1")


def test_delete_memory_not_found_still_returns_200_with_false(client: TestClient) -> None:
    with patch("gateway.memory.delete_memory", return_value=False):
        response = client.delete("/memories/does-not-exist")

    assert response.status_code == 200
    assert response.json() == {"deleted": False, "memory_id": "does-not-exist"}


def test_delete_memory_backend_error_returns_500(client: TestClient) -> None:
    with patch("gateway.memory.delete_memory", side_effect=MemoryError("mem0 unreachable")):
        response = client.delete("/memories/mem-1")

    assert response.status_code == 500
    assert response.json()["detail"] == "mem0 unreachable"
