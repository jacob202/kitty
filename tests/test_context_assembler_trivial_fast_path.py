"""Regression tests for the trivial-tier context fast path."""

import pytest

from gateway.context_assembler import _AssemblerDeps, assemble_context
from gateway.context_enrichment import EnrichmentFn
from gateway.memory_graph import GraphResult, Item, Source


def _enrichment(text: str) -> EnrichmentFn:
    async def fn(_message: str) -> str | None:
        return text

    return fn


@pytest.mark.asyncio
async def test_trivial_tier_bypasses_memory_graph_and_enrichment(monkeypatch):
    async def exploding_search_all(message, *, adapters=None):
        raise AssertionError(f"trivial context unexpectedly queried memory graph: {message}")

    monkeypatch.setattr("gateway.context_assembler.search_all", exploding_search_all)

    deps = _AssemblerDeps(
        adapters=[],
        enrichments=(_enrichment("should-not-run"),),
    )

    bundle = await assemble_context("hi", deps=deps, tier="trivial")

    assert bundle.system
    assert bundle.memory_items == []
    assert bundle.injected_memory_items == []
    assert bundle.live_blocks == []
    assert bundle.warnings
    assert all(w.startswith("context_budget:") for w in bundle.warnings)
    assert bundle.context_budget["truncations"] == bundle.warnings
    assert "should-not-run" not in bundle.system


@pytest.mark.asyncio
async def test_standard_tier_still_uses_memory_graph(monkeypatch):
    calls = []

    async def fake_search_all(message, *, adapters=None):
        calls.append(message)
        return GraphResult(
            results={"memory": [Item(text="retrieved", source=Source.MEMORY)]},
            errors=[],
        )

    monkeypatch.setattr("gateway.context_assembler.search_all", fake_search_all)

    deps = _AssemblerDeps(adapters=[], enrichments=())

    bundle = await assemble_context("hello", deps=deps, tier="standard")

    assert calls == ["hello"]
    assert bundle.memory_items
    assert bundle.memory_items[0].text == "retrieved"
