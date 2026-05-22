"""Tests for context_builder — unified context via memory_graph, assembly."""

import pytest
from unittest.mock import patch, AsyncMock

from gateway import context_enrichment
from gateway.context_builder import (
    _assemble,
    get_system_prompt,
    build_worker_context,
)

# ---------------------------------------------------------------------------
# Unit tests — pure functions
# ---------------------------------------------------------------------------


def test_assemble_appends_dynamic_to_base():
    result = _assemble("BASE", "DYNAMIC")
    assert result == "BASE\n\nDYNAMIC"


def test_assemble_empty_dynamic_returns_base():
    assert _assemble("BASE", "") == "BASE"


def test_build_worker_context_researcher():
    result = build_worker_context(
        "researcher", topic="Kitty routing", chunks="Some notes"
    )
    assert "Research topic: Kitty routing" in result
    assert "Some notes" in result


def test_build_worker_context_unknown_returns_empty():
    assert build_worker_context("brief", top_task="ignored") == ""


# ---------------------------------------------------------------------------
# Async integration tests — unified context via memory_graph
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_system_prompt_calls_enrichment():
    unified_mock = AsyncMock(return_value="UNIFIED")
    enrich_mock = AsyncMock(return_value="UNIFIED\n\nENRICHED")

    with patch(
        "gateway.context_builder.memory_graph.unified_context", unified_mock
    ), patch("gateway.context_builder.enrich_dynamic_context", enrich_mock), patch(
        "gateway.context_builder.prompt_loader.load_prompt", return_value="BASE"
    ), patch(
        "gateway.context_builder.journal.is_journal_trigger", return_value=False
    ), patch(
        "gateway.context_builder.parts.should_surface_parts", return_value=False
    ):
        result = await get_system_prompt("hello")

    unified_mock.assert_awaited_once_with("hello")
    enrich_mock.assert_awaited_once_with("UNIFIED", "hello")
    assert result == "BASE\n\nUNIFIED\n\nENRICHED"


@pytest.mark.asyncio
async def test_enrich_dynamic_context_appends_block():
    async def fake_block(_message: str) -> str:
        return "[TestBlock] hello"

    with patch.object(context_enrichment, "_ENRICHMENTS", (fake_block,)), patch(
        "gateway.voice_gate.get_drift_nudge", return_value=""
    ):
        result = await context_enrichment.enrich_dynamic_context("BASE", "msg")

    assert result == "BASE\n\n[TestBlock] hello"


# ---------------------------------------------------------------------------
# Unified memory_graph unit tests
# ---------------------------------------------------------------------------

from gateway.memory_graph import _format_unified, _truncate


def test_truncate_short_text_unchanged():
    text = "hello world"
    assert _truncate(text, 500) == text


def test_truncate_long_text_ends_with_ellipsis():
    long_text = "x" * 10000
    result = _truncate(long_text, 100)
    assert result.endswith("…")
    assert len(result) < len(long_text)


def test_format_unified_empty_results_returns_empty():
    assert _format_unified({}) == ""


def test_format_unified_memory_only():
    results = {"memory": [{"memory": "Jacob owns a 2010 Honda"}]}
    formatted = _format_unified(results)
    assert "## Memory" in formatted
    assert "2010 Honda" in formatted


def test_format_unified_all_sections():
    results = {
        "memory": [{"memory": "test memory"}],
        "knowledge": [
            {"text": "test knowledge", "source": "test.txt", "doc_type": "general"}
        ],
        "journal": [{"entry": "test journal entry"}],
        "traces": [{"user_request": "test request", "domain_classified": "soul"}],
    }
    formatted = _format_unified(results)
    assert "## Memory" in formatted
    assert "## Knowledge" in formatted
    assert "## Recent Journal" in formatted
    assert "## Recent Activity" in formatted


def test_format_unified_respects_token_cap():
    results = {"memory": [{"memory": "x" * 10000}]}
    formatted = _format_unified(results)
    assert len(formatted) < 10000
