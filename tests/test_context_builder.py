"""Tests for context_builder — tuple return, partial failures, section headers."""
import asyncio
import pytest
from unittest.mock import patch

from gateway.context_builder import (
    MEMORY_TOKEN_CAP,
    KNOWLEDGE_TOKEN_CAP,
    MEMORY_SIMILARITY_THRESHOLD,
    _build_dynamic,
    _truncate,
    assemble_system_prompt,
    build_user_context,
)


# ---------------------------------------------------------------------------
# Unit tests — pure functions
# ---------------------------------------------------------------------------

def test_build_dynamic_both_present():
    result = _build_dynamic("mem stuff", "know stuff")
    assert "[MEMORY]\nmem stuff" in result
    assert "[KNOWLEDGE]\nknow stuff" in result


def test_build_dynamic_omits_empty_memory():
    result = _build_dynamic("", "know stuff")
    assert "[MEMORY]" not in result
    assert "[KNOWLEDGE]\nknow stuff" in result


def test_build_dynamic_omits_empty_knowledge():
    result = _build_dynamic("mem stuff", "")
    assert "[KNOWLEDGE]" not in result
    assert "[MEMORY]\nmem stuff" in result


def test_build_dynamic_both_empty_returns_empty():
    assert _build_dynamic("", "") == ""


def test_truncate_short_text_unchanged():
    text = "hello world"
    assert _truncate(text, 500) == text


def test_truncate_long_text_ends_with_ellipsis():
    long_text = "x" * 10000
    result = _truncate(long_text, 100)
    assert result.endswith("…")
    assert len(result) < len(long_text)


def test_assemble_system_prompt_with_dynamic():
    result = assemble_system_prompt("SOUL", "DYNAMIC")
    assert "SOUL" in result
    assert "DYNAMIC" in result
    assert result.index("SOUL") < result.index("DYNAMIC")


def test_assemble_system_prompt_empty_dynamic_returns_soul():
    assert assemble_system_prompt("SOUL", "") == "SOUL"


def test_constants_exist_and_sane():
    assert 0 < MEMORY_SIMILARITY_THRESHOLD <= 1.0
    assert MEMORY_TOKEN_CAP > 0
    assert KNOWLEDGE_TOKEN_CAP > 0


# ---------------------------------------------------------------------------
# Async integration tests — both-fetches patterns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_user_context_returns_tuple():
    with patch("gateway.context_builder._fetch_memory", return_value="mem"), \
         patch("gateway.context_builder._fetch_knowledge", return_value="know"):
        soul, dynamic = await build_user_context("test query", "SOUL")
    assert soul == "SOUL"
    assert "[MEMORY]" in dynamic
    assert "[KNOWLEDGE]" in dynamic


@pytest.mark.asyncio
async def test_build_user_context_soul_unchanged_on_both_fail():
    with patch("gateway.context_builder._fetch_memory", return_value=""), \
         patch("gateway.context_builder._fetch_knowledge", return_value=""):
        soul, dynamic = await build_user_context("test query", "SOUL")
    assert soul == "SOUL"
    assert dynamic == ""


@pytest.mark.asyncio
async def test_build_user_context_partial_failure_memory():
    with patch("gateway.context_builder._fetch_memory", return_value=""), \
         patch("gateway.context_builder._fetch_knowledge", return_value="know"):
        soul, dynamic = await build_user_context("test query", "SOUL")
    assert "[MEMORY]" not in dynamic
    assert "[KNOWLEDGE]\nknow" in dynamic


@pytest.mark.asyncio
async def test_build_user_context_exception_does_not_raise():
    def _raise(_q):
        raise RuntimeError("db down")

    with patch("gateway.context_builder._fetch_memory", side_effect=_raise), \
         patch("gateway.context_builder._fetch_knowledge", return_value="know"):
        soul, dynamic = await build_user_context("test query", "SOUL")
    assert soul == "SOUL"
