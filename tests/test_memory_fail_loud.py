"""TL-05 regressions for observable memory failures and real persistence."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.memory import (
    MemoryError,
    delete_memory,
    get_context_block,
    list_memories,
    search_memory,
)


def _patched_mem(side_effect=None, return_value=None):
    """Return a mock Memory instance with configured search/get/delete behaviour."""
    mem = MagicMock()
    if side_effect is not None:
        mem.search.side_effect = side_effect
        mem.get.side_effect = side_effect
        mem.delete.side_effect = side_effect
    if return_value is not None:
        mem.search.return_value = return_value
        mem.get.return_value = return_value
    return mem


@pytest.fixture(autouse=True)
def reset_memory_state():
    """Keep module-level lazy-init state isolated between regressions."""
    original = {
        "instance": memory._MEMORY_INSTANCE,
        "failed": memory._MEMORY_INIT_FAILED,
        "error": memory._MEMORY_INIT_ERROR,
        "import_ok": memory._MEM0_IMPORT_OK,
        "import_error": memory._MEM0_IMPORT_ERROR,
    }
    yield
    memory._MEMORY_INSTANCE = original["instance"]
    memory._MEMORY_INIT_FAILED = original["failed"]
    memory._MEMORY_INIT_ERROR = original["error"]
    memory._MEM0_IMPORT_OK = original["import_ok"]
    memory._MEM0_IMPORT_ERROR = original["import_error"]


def test_get_memory_surfaces_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    missing = ImportError("No module named 'mem0'")
    monkeypatch.setattr(memory, "_MEM0_IMPORT_OK", False)
    monkeypatch.setattr(memory, "_MEM0_IMPORT_ERROR", missing)

    with pytest.raises(memory.MemoryError, match="mem0ai is not installed") as raised:
        memory._get_memory()

    assert raised.value.details == {
        "operation": "memory initialization",
        "dependency": "mem0ai",
    }
    assert raised.value.__cause__ is missing


def test_get_memory_repeats_cached_initialization_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = MagicMock()
    factory.from_config.side_effect = RuntimeError("chroma startup failed")
    monkeypatch.setattr(memory, "_MEM0_IMPORT_OK", True)
    monkeypatch.setattr(memory, "_MEMORY_INSTANCE", None)
    monkeypatch.setattr(memory, "_MEMORY_INIT_FAILED", False)
    monkeypatch.setattr(memory, "_MEMORY_INIT_ERROR", None)
    monkeypatch.setattr(memory, "_Mem0Memory", factory)
    monkeypatch.setattr(memory, "MEM0_DATA_DIR", tmp_path / "mem0")
    monkeypatch.setattr(memory, "_build_mem0_config", lambda: {})

    with pytest.raises(
        memory.MemoryError,
        match=r"memory initialization failed \(RuntimeError\)",
    ) as first:
        memory._get_memory()
    with pytest.raises(
        memory.MemoryError,
        match=r"memory initialization failed \(RuntimeError\)",
    ) as cached:
        memory._get_memory()

    assert first.value.details["operation"] == "memory initialization"
    assert str(first.value.__cause__) == "chroma startup failed"
    assert cached.value.details["cached_failure"] is True
    assert str(cached.value.__cause__) == "chroma startup failed"
    factory.from_config.assert_called_once_with({})


def test_add_memory_surfaces_write_failure() -> None:
    backend = MagicMock()
    backend.add.side_effect = OSError("vector store is read-only")

    with (
        patch.object(memory, "_get_memory", return_value=backend),
        pytest.raises(
            memory.MemoryError,
            match=r"memory add failed \(OSError\)",
        ) as raised,
    ):
        memory.add_memory("important fact", namespace="facts")

    assert raised.value.details["namespace"] == "facts"
    assert raised.value.details["exception_type"] == "OSError"
    assert str(raised.value.__cause__) == "vector store is read-only"


def test_add_memory_rejects_unconfirmed_success_response() -> None:
    backend = MagicMock()
    backend.add.return_value = None

    with (
        patch.object(memory, "_get_memory", return_value=backend),
        pytest.raises(memory.MemoryError, match="returned NoneType, expected list"),
    ):
        memory.add_memory("important fact")


def test_add_memory_reports_explicit_no_change() -> None:
    backend = MagicMock()
    backend.add.return_value = {"results": []}

    with patch.object(memory, "_get_memory", return_value=backend):
        assert memory.add_memory("already known fact") is False


def test_search_memory_surfaces_backend_failure() -> None:
    backend = MagicMock()
    backend.search.side_effect = ConnectionError("ollama refused connection")

    with (
        patch.object(memory, "_get_memory", return_value=backend),
        pytest.raises(
            memory.MemoryError,
            match=r"memory search failed \(ConnectionError\)",
        ) as raised,
    ):
        memory.search_memory("important query")

    assert str(raised.value.__cause__) == "ollama refused connection"


def test_search_memory_rejects_malformed_success_response() -> None:
    backend = MagicMock()
    backend.search.return_value = {"unexpected": []}

    with (
        patch.object(memory, "_get_memory", return_value=backend),
        pytest.raises(
            memory.MemoryError,
            match="missing 'results'",
        ),
    ):
        memory.search_memory("important query")


def test_search_memory_preserves_real_empty_result() -> None:
    backend = MagicMock()
    backend.search.return_value = {"results": []}

    with patch.object(memory, "_get_memory", return_value=backend):
        assert memory.search_memory("no match") == []


def test_search_memory_rejects_malformed_namespace_metadata() -> None:
    backend = MagicMock()
    backend.search.return_value = {"results": [{"memory": "fact", "metadata": []}]}

    with (
        patch.object(memory, "_get_memory", return_value=backend),
        pytest.raises(memory.MemoryError, match="metadata is list, expected dict"),
    ):
        memory.search_memory("fact", namespace="facts")


def test_search_memory_applies_namespace_before_backend_limit() -> None:
    backend = MagicMock()
    rows = [
        {
            "id": "session-1",
            "memory": "session summary",
            "metadata": {"namespace": "sessions"},
        }
    ]
    backend.search.return_value = {"results": rows}

    with patch.object(memory, "_get_memory", return_value=backend):
        assert memory.search_memory("summary", limit=1, namespace="sessions") == rows

    backend.search.assert_called_once_with(
        "summary",
        filters={"user_id": memory.USER_ID, "namespace": "sessions"},
        limit=1,
    )


def test_search_memory_rejects_backend_namespace_mismatch() -> None:
    backend = MagicMock()
    backend.search.return_value = {
        "results": [
            {
                "id": "fact-1",
                "memory": "unrelated fact",
                "metadata": {"namespace": "facts"},
            }
        ]
    }

    with (
        patch.object(memory, "_get_memory", return_value=backend),
        pytest.raises(memory.MemoryError, match="does not match requested namespace"),
    ):
        memory.search_memory("summary", limit=1, namespace="sessions")


def test_list_memories_surfaces_backend_failure() -> None:
    backend = MagicMock()
    backend.get_all.side_effect = OSError("memory database is locked")

    with (
        patch.object(memory, "_get_memory", return_value=backend),
        pytest.raises(
            memory.MemoryError,
            match=r"memory list failed \(OSError\)",
        ) as raised,
    ):
        memory.list_memories()

    assert str(raised.value.__cause__) == "memory database is locked"


def test_list_memories_rejects_non_list_success_response() -> None:
    backend = MagicMock()
    backend.get_all.return_value = {"results": None}

    with (
        patch.object(memory, "_get_memory", return_value=backend),
        pytest.raises(
            memory.MemoryError,
            match="returned NoneType, expected list",
        ),
    ):
        memory.list_memories()


def test_list_memories_preserves_real_empty_result() -> None:
    backend = MagicMock()
    backend.get_all.return_value = {"results": []}

    with patch.object(memory, "_get_memory", return_value=backend):
        assert memory.list_memories() == []

    backend.get_all.assert_called_once_with(user_id=memory.USER_ID, limit=50)


def test_list_memories_limit_zero_returns_results_instead_of_false_empty() -> None:
    backend = MagicMock()
    rows = [{"id": "one", "memory": "first"}, {"id": "two", "memory": "second"}]
    backend.get_all.return_value = {"results": rows}

    with patch.object(memory, "_get_memory", return_value=backend):
        assert memory.list_memories(limit=0) == rows

    backend.get_all.assert_called_once_with(
        user_id=memory.USER_ID,
        limit=memory.MEMORY_LIST_ALL_LIMIT,
    )


def test_list_memories_applies_namespace_before_backend_limit() -> None:
    backend = MagicMock()
    rows = [
        {
            "id": "session-1",
            "memory": "session summary",
            "metadata": {"namespace": "sessions"},
        }
    ]
    backend.get_all.return_value = {"results": rows}

    with patch.object(memory, "_get_memory", return_value=backend):
        assert memory.list_memories(namespace="sessions", limit=1) == rows

    backend.get_all.assert_called_once_with(
        user_id=memory.USER_ID,
        filters={"namespace": "sessions"},
        limit=1,
    )


def test_list_memories_rejects_backend_namespace_mismatch() -> None:
    backend = MagicMock()
    backend.get_all.return_value = {
        "results": [
            {
                "id": "fact-1",
                "memory": "unrelated fact",
                "metadata": {"namespace": "facts"},
            }
        ]
    }

    with (
        patch.object(memory, "_get_memory", return_value=backend),
        pytest.raises(memory.MemoryError, match="does not match requested namespace"),
    ):
        memory.list_memories(namespace="sessions", limit=1)


def test_delete_memory_surfaces_backend_failure() -> None:
    backend = MagicMock()
    backend.get.return_value = {"id": "memory-123", "memory": "fact"}
    backend.delete.side_effect = OSError("memory database is locked")

    with (
        patch.object(memory, "_get_memory", return_value=backend),
        pytest.raises(
            memory.MemoryError,
            match=r"memory delete failed \(OSError\)",
        ) as raised,
    ):
        memory.delete_memory("memory-123")

    assert raised.value.details["memory_id"] == "memory-123"
    assert str(raised.value.__cause__) == "memory database is locked"


def test_delete_memory_preserves_explicit_not_found_result() -> None:
    backend = MagicMock()
    backend.get.return_value = None

    with patch.object(memory, "_get_memory", return_value=backend):
        assert memory.delete_memory("missing-memory") is False

    backend.delete.assert_not_called()


def test_delete_memory_requires_backend_confirmation() -> None:
    backend = MagicMock()
    backend.get.return_value = {"id": "memory-123", "memory": "fact"}
    backend.delete.return_value = None

    with (
        patch.object(memory, "_get_memory", return_value=backend),
        pytest.raises(memory.MemoryError, match="did not confirm deletion"),
    ):
        memory.delete_memory("memory-123")


def test_delete_memory_rejects_mismatched_lookup_result() -> None:
    backend = MagicMock()
    backend.get.return_value = {"id": "different-memory", "memory": "fact"}

    with (
        patch.object(memory, "_get_memory", return_value=backend),
        pytest.raises(memory.MemoryError, match="mismatched memory id"),
    ):
        memory.delete_memory("memory-123")

    backend.delete.assert_not_called()


def test_delete_memory_returns_true_after_confirmed_delete() -> None:
    backend = MagicMock()
    backend.get.return_value = {"id": "memory-123", "memory": "fact"}
    backend.delete.return_value = {"message": "Memory deleted successfully!"}

    with patch.object(memory, "_get_memory", return_value=backend):
        assert memory.delete_memory("memory-123") is True


def test_get_context_block_marks_backend_failure_as_degraded() -> None:
    with patch.object(
        memory,
        "search_memory",
        side_effect=memory.MemoryError("memory backend down"),
    ):
        block = memory.get_context_block("what does Jacob know?")

    assert block == memory.MEMORY_DEGRADED_CONTEXT
    assert "unavailable" in block


def test_consolidate_session_stores_facts() -> None:
    messages = [
        {"role": "user", "content": "Let's build a CLI tool for backups"},
        {"role": "assistant", "content": "I'll create a backup script."},
        {"role": "user", "content": "Use Python with pathlib"},
        {"role": "assistant", "content": "Done. backup.py created."},
        {"role": "user", "content": "Add cron scheduling too"},
    ]
    stored = {}

    def mock_add(text, namespace="facts", metadata=None):
        stored["text"] = text
        stored["namespace"] = namespace
        stored["metadata"] = metadata
        return True

    with patch.object(memory, "add_memory", side_effect=mock_add):
        result = memory.consolidate_session("test-123", messages)

    assert result is True
    assert stored["namespace"] == "sessions"
    assert "test-123" in stored["text"]
    assert "backup" in stored["text"].lower()
    assert stored["metadata"]["session_id"] == "test-123"
    assert stored["metadata"]["message_count"] == 5
    assert stored["metadata"]["user_message_count"] == 3


def test_consolidate_session_empty_messages() -> None:
    result = memory.consolidate_session("test-empty", [])
    assert result is False


def test_consolidate_session_no_user_messages() -> None:
    messages = [{"role": "assistant", "content": "Hello"}]
    result = memory.consolidate_session("test-no-user", messages)
    assert result is False


def test_consolidate_session_backend_failure() -> None:
    messages = [{"role": "user", "content": "test"}]

    def boom(text, namespace="facts", metadata=None):
        raise RuntimeError("mem0 down")

    with (
        patch.object(memory, "add_memory", side_effect=boom),
        pytest.raises(
            memory.MemoryError,
            match=r"session consolidation failed \(RuntimeError\)",
        ) as raised,
    ):
        memory.consolidate_session("test-fail", messages)

    assert raised.value.details["session_id"] == "test-fail"
    assert str(raised.value.__cause__) == "mem0 down"


def test_consolidate_session_reports_no_persisted_change() -> None:
    messages = [{"role": "user", "content": "already known fact"}]

    with patch.object(memory, "add_memory", return_value=False):
        assert memory.consolidate_session("test-no-change", messages) is False


def test_memories_route_returns_structured_503_on_list_failure() -> None:
    from gateway.app import app

    client = TestClient(app, raise_server_exceptions=False)
    with patch.object(
        memory,
        "list_memories",
        side_effect=memory.MemoryError("chroma unavailable"),
    ):
        response = client.get("/memories")

    assert response.status_code == 503
    assert response.json() == {
        "error": "storage.unavailable",
        "message": "chroma unavailable",
    }


def test_memories_route_returns_404_instead_of_false_delete_success() -> None:
    from gateway.app import app

    client = TestClient(app, raise_server_exceptions=False)
    with patch.object(memory, "delete_memory", return_value=False):
        response = client.delete("/memories/missing-memory")

    assert response.status_code == 404
    assert response.json() == {
        "error": "storage.not_found",
        "message": "memory 'missing-memory' was not found",
        "details": {"memory_id": "missing-memory"},
    }


def test_dream_insights_persist_to_disk(tmp_path: Path) -> None:
    insights_file = tmp_path / "dream_insights.json"
    with patch.object(dream_insights, "DREAM_INSIGHTS_FILE", insights_file):
        dream_insights.save_dream_insights(
            "Consolidated 3 trace clusters into long-term memory\n"
            "Pruned 12 old trace entries (kept last 30d)\n"
            "Weekly mirror refreshed"
        )

    assert insights_file.exists()
    cards = json.loads(insights_file.read_text())
    assert len(cards) == 3
    assert cards[0]["kind"] == "consolidation"
    assert cards[1]["kind"] == "maintenance"
    assert cards[2]["kind"] == "reflection"
    # All have required fields
    for card in cards:
        assert "insight_id" in card
        assert "title" in card
        assert "created_at" in card
        assert card["source"] == "nightly_dream"


def test_dream_insights_load_readable(tmp_path: Path) -> None:
    insights_file = tmp_path / "dream_insights.json"
    cards = [
        {
            "insight_id": "abc12345",
            "kind": "consolidation",
            "title": "Jacob decided to use FastAPI",
            "detail": "Jacob decided to use FastAPI for the gateway",
            "source": "nightly_dream",
            "confidence": 0.9,
            "created_at": "2026-07-12T10:00:00",
            "actions": [],
        }
    ]
    insights_file.write_text(json.dumps(cards))

    with patch.object(dream_insights, "DREAM_INSIGHTS_FILE", insights_file):
        loaded = dream_insights.load_dream_insights(limit=5)

    assert len(loaded) == 1
    assert loaded[0]["title"] == "Jacob decided to use FastAPI"
