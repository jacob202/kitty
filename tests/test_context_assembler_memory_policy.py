"""Tests that context assembly applies memory policy filtering correctly.

Verifies:
- Sensitive support items are excluded from system prompt for neutral query
- Raw memory_items still includes everything for audit/debug
- Filtered results exclude suppressed items
"""

import pytest

from gateway.context_assembler import _AssemblerDeps, assemble_context
from gateway.memory_graph import Item, Source, StoreAdapter

pytestmark = pytest.mark.asyncio


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
# Passes memory policy (pinned) but is dropped by the render-time privacy
# gate (health tag, neutral query) — the case where "post-policy" and
# "actually rendered" diverge.
PINNED_TAGGED_HEALTH = Item(
    text="blood pressure log for March",
    source=Source.MEMORY,
    metadata={"pinned": True, "tags": ["health"]},
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


class TestInjectedMemoryEvidence:
    """CR-04: bundle.injected_memory_items is the truthful record of what
    actually entered the prompt — post-policy, post-privacy-gate, post-budget."""

    async def test_injected_items_match_prompt_exactly(self, deps):
        """Evidence lists exactly the surfaced items, in prompt order."""
        bundle = await assemble_context("how is the project going", deps=deps)
        assert bundle.injected_memory_items == [
            PROJECT_ITEM.text,
            PREFERENCE_ITEM.text,
            PINNED_SENSITIVE.text,
        ]
        for text in bundle.injected_memory_items:
            assert f"- {text}" in bundle.system

    async def test_suppressed_items_absent_from_evidence(self, deps):
        """Policy-suppressed items appear in neither prompt nor evidence."""
        bundle = await assemble_context("how is the project going", deps=deps)
        assert SENSITIVE_ITEM.text not in bundle.injected_memory_items
        assert BLOCKED_ITEM.text not in bundle.injected_memory_items

    async def test_privacy_gated_item_absent_from_evidence(self):
        """An item that passes memory policy but is dropped by the render-time
        privacy gate must be absent from both the prompt and the evidence —
        otherwise the trailer would leak what the gate deliberately withheld."""
        adapter = _ControlledAdapter(
            "memory", [PROJECT_ITEM, PINNED_TAGGED_HEALTH]
        )
        deps = _AssemblerDeps(adapters=[adapter], enrichments=())
        bundle = await assemble_context("how is the project going", deps=deps)
        assert PINNED_TAGGED_HEALTH.text not in bundle.system
        assert PINNED_TAGGED_HEALTH.text not in bundle.injected_memory_items
        assert bundle.injected_memory_items == [PROJECT_ITEM.text]

    async def test_policy_filter_runs_exactly_once_per_item(self, deps, monkeypatch):
        """should_surface is consulted once per retrieved item — no re-filtering
        anywhere downstream."""
        from gateway import context_assembler
        from gateway.memory_policy import should_surface as real_should_surface

        calls: list[str] = []

        def counting_should_surface(item, query=""):
            calls.append(item.text)
            return real_should_surface(item, query=query)

        monkeypatch.setattr(
            context_assembler, "should_surface", counting_should_surface
        )
        await assemble_context("how is the project going", deps=deps)
        assert sorted(calls) == sorted(
            [
                SENSITIVE_ITEM.text,
                PROJECT_ITEM.text,
                PREFERENCE_ITEM.text,
                PINNED_SENSITIVE.text,
                BLOCKED_ITEM.text,
            ]
        )

    async def test_no_memories_yields_empty_evidence(self):
        adapter = _ControlledAdapter("memory", [])
        deps = _AssemblerDeps(adapters=[adapter], enrichments=())
        bundle = await assemble_context("hello", deps=deps)
        assert bundle.injected_memory_items == []
