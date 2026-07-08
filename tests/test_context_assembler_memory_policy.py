"""Tests that context assembly applies memory policy filtering correctly.

Verifies:
- Sensitive support items are excluded from system prompt for neutral query
- Raw memory_items still includes everything for audit/debug
- Filtered results exclude suppressed items
"""

import pytest

pytestmark = pytest.mark.asyncio

from gateway.context_assembler import ContextBundle, _AssemblerDeps, assemble_context
from gateway.memory_graph import Item, Source, StoreAdapter


class _ControlledAdapter(StoreAdapter):
    """An adapter that returns preset items regardless of query."""

    def __init__(self, name: str, items: list[Item]):
        self._name = name
        self._items = items

    @property
    def name(self) -> str:
        return self._name

    async def fetch(self, query: str) -> list[Item]:
        return self._items


SENSITIVE_ITEM = Item(
    text="recovery check-in: feeling better today",
    source=Source.MEMORY,
)
PROJECT_ITEM = Item(
    text="decided to use FastAPI for the gateway",
    source=Source.MEMORY,
)
PREFERENCE_ITEM = Item(
    text="i prefer dark mode in all UIs",
    source=Source.MEMORY,
)
PINNED_SENSITIVE = Item(
    text="recovery plan for March",
    source=Source.MEMORY,
    metadata={"pinned": True},
)
BLOCKED_ITEM = Item(
    text="old embarrassing story",
    source=Source.MEMORY,
    metadata={"blocked": True},
)


@pytest.fixture
def deps():
    adapter = _ControlledAdapter(
        "memory",
        [SENSITIVE_ITEM, PROJECT_ITEM, PREFERENCE_ITEM, PINNED_SENSITIVE, BLOCKED_ITEM],
    )
    return _AssemblerDeps(adapters=[adapter], enrichments=())


class TestAssemblerMemoryPolicy:
    @pytest.mark.asyncio
    async def test_sensitive_suppressed_for_neutral_query(self, deps):
        """Sensitive support items excluded from system prompt for neutral query."""
        bundle = await assemble_context("how is the project going", deps=deps)
        assert bundle.memory_items == [
            SENSITIVE_ITEM, PROJECT_ITEM, PREFERENCE_ITEM, PINNED_SENSITIVE, BLOCKED_ITEM,
        ], "raw items should be preserved"
        assert "recovery check-in" not in bundle.system, \
            "sensitive item should not appear in system prompt"
        assert "FastAPI" in bundle.system, "project item should appear"
        assert "dark mode" in bundle.system, "preference item should appear"

    async def test_pinned_sensitive_surfaces(self, deps):
        """Pinned items surface even when they're sensitive."""
        bundle = await assemble_context("how is the project going", deps=deps)
        assert "recovery plan for March" in bundle.system, \
            "pinned sensitive item should surface"

    async def test_blocked_excluded(self, deps):
        """Blocked items excluded from system prompt."""
        bundle = await assemble_context("tell me a story", deps=deps)
        assert "old embarrassing story" not in bundle.system, \
            "blocked item should not appear"
        assert "old embarrassing story" in [
            i.text for i in bundle.memory_items
        ], "blocked item still in raw items for audit"

    async def test_sensitive_surfaces_on_direct_query(self, deps):
        """Sensitive support surfaces when query directly asks about it."""
        bundle = await assemble_context("how is recovery going", deps=deps)
        assert "recovery check-in" in bundle.system, \
            "sensitive item should surface on direct query"

    async def test_memory_items_preserves_everything(self, deps):
        """Raw memory_items always contains all items for debugging."""
        bundle = await assemble_context("what's new", deps=deps)
        texts = [i.text for i in bundle.memory_items]
        assert SENSITIVE_ITEM.text in texts
        assert PROJECT_ITEM.text in texts
        assert PREFERENCE_ITEM.text in texts
        assert PINNED_SENSITIVE.text in texts
        assert BLOCKED_ITEM.text in texts
