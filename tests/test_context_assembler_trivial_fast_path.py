"""Regression tests for the trivial-tier context fast path."""

import pytest

from gateway.context_assembler import _AssemblerDeps, assemble_context
from gateway.context_enrichment import EnrichmentFn
from gateway.memory_graph import Item, Source


class ExplodingGraph:
    """Graph seam that makes any accidental trivial retrieval fail loudly."""

    def __init__(self, adapters):
        self.adapters = adapters

    async def search_all(self, message):
        raise AssertionError(f"trivial context unexpectedly queried memory graph: {message}")


class WorkingGraph:
    """Graph seam proving non-trivial tiers still use retrieval."""

    def __init__(self, adapters):
        self.adapters = adapters
        self.calls = 0

    async def search_all(self, message):
        self.calls += 1
        return type(
            "GraphResult",
            (),
            {
                "results": {
                    "memory": [Item(text="retrieved", source=Source.MEMORY)],
                },
                "errors": [],
            },
        )()


def _enrichment(text: str) -> EnrichmentFn:
    async def fn(_message: str) -> str | None:
        return text

    return fn


@pytest.mark.asyncio
async def test_trivial_tier_bypasses_memory_graph_and_enrichment():
    deps = _AssemblerDeps(
        adapters=[],
        enrichments=(_enrichment("should-not-run"),),
        graph_cls=ExplodingGraph,
    )

    bundle = await assemble_context("hi", deps=deps, tier="trivial")

    assert bundle.system
    assert bundle.memory_items == []
    assert bundle.injected_memory_items == []
    assert bundle.live_blocks == []
    assert bundle.warnings == []
    assert "should-not-run" not in bundle.system


@pytest.mark.asyncio
async def test_standard_tier_still_uses_memory_graph():
    graph_cls = WorkingGraph
    deps = _AssemblerDeps(
        adapters=[],
        enrichments=(),
        graph_cls=graph_cls,
    )

    bundle = await assemble_context("hello", deps=deps, tier="standard")

    assert bundle.memory_items
    assert bundle.memory_items[0].text == "retrieved"
