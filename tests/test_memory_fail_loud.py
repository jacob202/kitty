"""TL-05 regression tests: memory paths raise MemoryError instead of silently returning []."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gateway.memory import MemoryError, delete_memory, get_context_block, list_memories, search_memory


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
    """Reset module-level init cache between tests."""
    import gateway.memory as mod
    orig_instance = mod._MEMORY_INSTANCE
    orig_failed = mod._MEMORY_INIT_FAILED
    yield
    mod._MEMORY_INSTANCE = orig_instance
    mod._MEMORY_INIT_FAILED = orig_failed


class TestSearchMemory:
    def test_raises_memory_error_on_backend_failure(self):
        mem = _patched_mem(side_effect=RuntimeError("chroma down"))
        with patch("gateway.memory._get_memory", return_value=mem):
            with pytest.raises(MemoryError, match="memory search failed"):
                search_memory("test query")

    def test_returns_empty_when_mem0_unavailable(self):
        with patch("gateway.memory._get_memory", return_value=None):
            assert search_memory("test") == []


class TestListMemories:
    def test_raises_memory_error_on_backend_failure(self):
        mem = _patched_mem(side_effect=OSError("store locked"))
        with patch("gateway.memory._get_memory", return_value=mem):
            with pytest.raises(MemoryError, match="memory list failed"):
                list_memories()

    def test_returns_empty_when_mem0_unavailable(self):
        with patch("gateway.memory._get_memory", return_value=None):
            assert list_memories() == []


class TestDeleteMemory:
    def test_raises_memory_error_on_backend_failure(self):
        mem = _patched_mem(side_effect=ValueError("invalid id"))
        with patch("gateway.memory._get_memory", return_value=mem):
            with pytest.raises(MemoryError, match="memory delete failed"):
                delete_memory("abc-123")

    def test_returns_false_when_mem0_unavailable(self):
        with patch("gateway.memory._get_memory", return_value=None):
            assert delete_memory("abc-123") is False


class TestGetContextBlock:
    def test_returns_empty_string_on_memory_error(self):
        """Prompt injection must never raise — MemoryError is caught and "" returned."""
        with patch("gateway.memory.search_memory", side_effect=MemoryError("backend down")):
            result = get_context_block("what does jacob like")
        assert result == ""

    def test_returns_formatted_block_on_success(self):
        memories = [{"memory": "Jacob prefers dark mode", "score": 0.9}]
        with patch("gateway.memory.search_memory", return_value=memories):
            result = get_context_block("preferences")
        assert "Jacob prefers dark mode" in result
        assert result.startswith("## What Kitty knows")
