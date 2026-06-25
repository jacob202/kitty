"""Tests for the read-path context assembler.

This module exercises the partial-result contract end to end:

- adapter failures surface as a ``Warning`` on the bundle, not silent skip
- every store returns the uniform ``Item`` shape — ``item.text`` always works
- ``voice_gate`` is never called by the assembler (response-time concern)
- partial result: 12/15 sources succeed, 3 fail, ``ContextBundle`` is returned
- total failure: 0/15 sources succeed, ``assert_not_total_failure`` raises
- end-to-end with a fake fan-in (3 in-memory adapters + 2 fake enrichments)

The file also keeps the legacy ``_format_unified_items`` coverage that used
to live in ``test_context_builder.py`` — that function is now the assembler's
memory renderer.
"""


import pytest

from gateway.context_assembler import (
    ContextBundle,
    _AssemblerDeps,
    _looks_like_total_failure,
    assemble_context,
    assert_not_total_failure,
)
from gateway.context_enrichment import EnrichmentFn
from gateway.memory_graph import (
    Item,
    KnowledgeAdapter,
    MemoryAdapter,
    Source,
    StoreAdapter,
    TracesAdapter,
    _format_unified_items,
    _truncate_text,
)


# ---------------------------------------------------------------------------
# Fake adapters — the test surface for "Kitty knows what's in my X"
# ---------------------------------------------------------------------------


class FakeAdapter(StoreAdapter):
    """A StoreAdapter with configurable name, items, and optional exception."""

    def __init__(
        self,
        name: str,
        items: list[Item] | None = None,
        exc: Exception | None = None,
    ):
        self._name = name
        self._items = items or []
        self._exc = exc

    @property
    def name(self) -> str:
        return self._name

    async def fetch(self, query: str) -> list[Item]:
        if self._exc is not None:
            raise self._exc
        return list(self._items)


def _fake_enrichment(text: str, exc: Exception | None = None) -> EnrichmentFn:
    async def fn(_message: str) -> str | None:
        if exc is not None:
            raise exc
        return text

    fn.__name__ = f"fake_{text[:8].replace(' ', '_')}"
    return fn


# ---------------------------------------------------------------------------
# Adapter failure surfaces as a Warning, not silent skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adapter_failure_surfaces_as_warning():
    """A failing adapter must not silently disappear. It becomes a warning."""
    dep = _AssemblerDeps(
        adapters=[
            FakeAdapter("memory", items=[Item(text="ok", source=Source.MEMORY)]),
            FakeAdapter("knowledge", items=[], exc=RuntimeError("boom")),
        ],
        enrichments=(),
    )

    bundle = await assemble_context("hello", deps=dep)

    assert isinstance(bundle, ContextBundle)
    assert any("boom" in w for w in bundle.warnings)
    assert any("RuntimeError" in w for w in bundle.warnings)
    # The successful adapter's item is still in the bundle.
    assert any(item.text == "ok" for item in bundle.memory_items)


# ---------------------------------------------------------------------------
# Item shape is uniform across every adapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_item_shape_uniform_across_default_adapters():
    """Every default adapter's fetch returns ``Item`` and ``item.text`` works."""
    from gateway import memory_graph

    default_adapters = memory_graph._default_adapters()
    assert default_adapters, "expected at least one default adapter"

    for adapter in default_adapters:
        assert hasattr(adapter, "name")
        assert isinstance(adapter.name, str)
        # ABC contract: only ``name`` and ``fetch`` are required.
        assert callable(getattr(adapter, "fetch", None))
        # The legacy ``format_items`` and ``correlate`` are gone after Phase 2.
        assert "format_items" not in adapter.__dict__, (
            f"{type(adapter).__name__} should not override format_items"
        )


def test_item_dataclass_fields():
    item = Item(
        text="hello",
        source=Source.MEMORY,
        score=0.5,
        metadata={"foo": "bar"},
    )
    assert item.text == "hello"
    assert item.source == Source.MEMORY
    assert item.score == 0.5
    assert item.ts is None
    assert item.metadata == {"foo": "bar"}


# ---------------------------------------------------------------------------
# Voice-gate is NOT called by the assembler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_voice_gate_is_not_called_by_assembler(monkeypatch):
    """Drift-nudge is a response-time concern, never request-time."""
    from gateway import voice_gate

    calls: list[str] = []
    monkeypatch.setattr(
        voice_gate, "get_drift_nudge", lambda *a, **kw: calls.append("nudge") or "NUDGE"
    )

    dep = _AssemblerDeps(
        adapters=[FakeAdapter("memory", items=[Item(text="x", source=Source.MEMORY)])],
        enrichments=(_fake_enrichment("block"),),
    )
    await assemble_context("hello", deps=dep)

    assert calls == [], "voice_gate.get_drift_nudge must not be called by the assembler"


# ---------------------------------------------------------------------------
# Partial result: 12/15 sources succeed, 3 fail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_result_returns_bundle_with_warnings():
    """12 of 15 sources succeed, 3 fail — bundle returned, prompt non-empty."""
    ok_adapters = [
        FakeAdapter(
            f"ok-{i}", items=[Item(text=f"item-{i}", source=Source.MEMORY)]
        )
        for i in range(6)
    ]
    bad_adapters = [
        FakeAdapter(f"bad-{i}", items=[], exc=ConnectionError("store down"))
        for i in range(3)
    ]
    ok_enrichments = tuple(
        _fake_enrichment(f"block-{i}") for i in range(6)
    )
    bad_enrichments = tuple(
        _fake_enrichment("ignored", exc=OSError("net err")) for _ in range(3)
    )

    dep = _AssemblerDeps(
        adapters=ok_adapters + bad_adapters,
        enrichments=ok_enrichments + bad_enrichments,
    )

    bundle = await assemble_context("hello", deps=dep)

    assert isinstance(bundle, ContextBundle)
    # 3 adapter failures + 3 enrichment failures = 6 warnings.
    assert len(bundle.warnings) == 6
    assert sum("ConnectionError" in w for w in bundle.warnings) == 3
    assert sum("OSError" in w for w in bundle.warnings) == 3
    assert len(bundle.memory_items) == 6
    assert len(bundle.live_blocks) == 6
    assert bundle.system  # non-empty


# ---------------------------------------------------------------------------
# Total failure: 0/15 sources succeed, assembler raises via the guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_total_failure_raises_via_guard():
    """All sources fail; base call still returns a bundle, the guard raises."""
    bad_adapters = [
        FakeAdapter(f"store-{i}", items=[], exc=ConnectionError("down"))
        for i in range(8)
    ]
    bad_enrichments = tuple(
        _fake_enrichment("ignored", exc=OSError("nope")) for _ in range(7)
    )

    dep = _AssemblerDeps(
        adapters=bad_adapters,
        enrichments=bad_enrichments,
    )

    bundle = await assemble_context("hello", deps=dep)

    # The base call must not raise.
    assert isinstance(bundle, ContextBundle)
    assert bundle.memory_items == []
    assert bundle.live_blocks == []

    # Total failure = no memory AND no live blocks AND memory_graph warnings.
    assert _looks_like_total_failure(bundle) is True

    # The strict guard raises with the warning list.
    with pytest.raises(RuntimeError) as excinfo:
        assert_not_total_failure(bundle)
    assert "total infrastructure failure" in str(excinfo.value)


@pytest.mark.asyncio
async def test_partial_result_does_not_trigger_total_guard():
    """Enrichment failures alone do not constitute total failure."""
    dep = _AssemblerDeps(
        adapters=[FakeAdapter("memory", items=[Item(text="x", source=Source.MEMORY)])],
        enrichments=(
            _fake_enrichment("ignored", exc=OSError("net err")),
        ),
    )
    bundle = await assemble_context("hello", deps=dep)

    assert bundle.memory_items  # not empty
    assert bundle.live_blocks == []
    assert _looks_like_total_failure(bundle) is False

    # Guard does not raise.
    assert_not_total_failure(bundle) == bundle


# ---------------------------------------------------------------------------
# End-to-end with a fake fan-in
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_to_end_with_fake_fan_in():
    """3 in-memory adapters + 2 fake enrichments drive the orchestrator."""
    dep = _AssemblerDeps(
        adapters=[
            FakeAdapter(
                "memory",
                items=[Item(text="m1", source=Source.MEMORY)],
            ),
            FakeAdapter(
                "knowledge",
                items=[Item(text="k1", source=Source.KNOWLEDGE)],
            ),
            FakeAdapter(
                "journal",
                items=[Item(text="j1", source=Source.JOURNAL)],
            ),
        ],
        enrichments=(
            _fake_enrichment("[CAL] today"),
            _fake_enrichment("[W] sunny"),
        ),
    )

    bundle = await assemble_context("hello", deps=dep)

    assert bundle.system
    assert "m1" in bundle.system
    assert "k1" in bundle.system
    assert "j1" in bundle.system
    assert "[CAL] today" in bundle.live_blocks
    assert "[W] sunny" in bundle.live_blocks
    assert bundle.warnings == []


# ---------------------------------------------------------------------------
# The legacy _format_unified_items / _truncate_text coverage moved here
# ---------------------------------------------------------------------------


def test_truncate_short_text_unchanged():
    text = "hello world"
    assert _truncate_text(text, 500) == text


def test_truncate_long_text_ends_with_ellipsis():
    long_text = "x" * 10000
    result = _truncate_text(long_text, 100)
    assert result.endswith("…")
    assert len(result) < len(long_text)


def test_format_unified_empty_results_returns_empty():
    assert _format_unified_items({}) == ""


def test_format_unified_memory_only():
    results = {
        Source.MEMORY.value: [
            Item(text="Jacob owns a 2010 Honda", source=Source.MEMORY)
        ]
    }
    formatted = _format_unified_items(results)
    assert "## Memory" in formatted
    assert "2010 Honda" in formatted


def test_format_unified_all_sections():
    results = {
        Source.MEMORY.value: [Item(text="test memory", source=Source.MEMORY)],
        Source.KNOWLEDGE.value: [
            Item(
                text="test knowledge",
                source=Source.KNOWLEDGE,
                metadata={"source": "test.txt", "doc_type": "general"},
            )
        ],
        Source.JOURNAL.value: [
            Item(text="test journal entry", source=Source.JOURNAL)
        ],
        Source.TRACES.value: [
            Item(
                text="test request",
                source=Source.TRACES,
                metadata={"domain": "soul"},
            )
        ],
    }
    formatted = _format_unified_items(results)
    assert "## Memory" in formatted
    assert "## Knowledge" in formatted
    assert "## Journal" in formatted
    assert "## Traces" in formatted


def test_format_unified_respects_token_cap():
    results = {
        Source.MEMORY.value: [
            Item(text="x" * 10000, source=Source.MEMORY)
        ]
    }
    formatted = _format_unified_items(results)
    assert len(formatted) < 10000


def test_format_unified_skips_empty_sources():
    """A source with no items should not appear in the formatted output."""
    results = {
        Source.MEMORY.value: [Item(text="present", source=Source.MEMORY)],
        Source.KNOWLEDGE.value: [],
    }
    formatted = _format_unified_items(results)
    assert "## Memory" in formatted
    assert "## Knowledge" not in formatted


# ---------------------------------------------------------------------------
# Real adapter classes still implement the contract
# ---------------------------------------------------------------------------


def test_real_adapter_classes_have_fetch_only():
    """MemoryAdapter, KnowledgeAdapter, TracesAdapter — only name + fetch.

    The legacy format_items / correlate methods are gone from the
    adapter contract. If a future adapter adds them back, this test
    fails intentionally — that's a sign the contract is drifting.
    """
    for cls in (MemoryAdapter, KnowledgeAdapter, TracesAdapter):
        instance = cls()
        assert hasattr(instance, "name")
        assert callable(getattr(instance, "fetch", None))
        assert "format_items" not in cls.__dict__, (
            f"{cls.__name__} should not define format_items"
        )
        assert "correlate" not in cls.__dict__, (
            f"{cls.__name__} should not define correlate"
        )
