"""Eval: does memory recall return expected Jacob facts?"""
from unittest.mock import MagicMock, patch

import gateway.memory as mem_module


def _mock_search(memories: list[dict]):
    mock = MagicMock(return_value=memories)
    return patch.object(mem_module, "search_memory", mock)


def test_name_recalled():
    fake = [{"memory": "Jacob's full name is Jacob Brizinski", "score": 0.95}]
    with _mock_search(fake):
        results = mem_module.search_memory("What is my name")
    assert any("Jacob" in row.get("memory", "") for row in results)


def test_location_recalled():
    fake = [{"memory": "Jacob lives in Regina, Saskatchewan, Canada", "score": 0.92}]
    with _mock_search(fake):
        results = mem_module.search_memory("Where do I live")
    assert any(
        "Regina" in row.get("memory", "") or "Saskatchewan" in row.get("memory", "")
        for row in results
    )


def test_interest_recalled():
    fake = [
        {
            "memory": "Jacob is passionate about audiophile music and high-end audio equipment",
            "score": 0.88,
        }
    ]
    with _mock_search(fake):
        results = mem_module.search_memory("What are my interests")
    assert any("audio" in row.get("memory", "").lower() for row in results)


def test_context_block_format():
    fake = [{"memory": "Jacob uses Claude Code daily", "score": 0.9}]
    with _mock_search(fake):
        block = mem_module.get_context_block("coding tools")
    assert "## What Kitty knows about Jacob" in block
    assert "Jacob uses Claude Code daily" in block


def test_empty_search_returns_empty_block():
    with _mock_search([]):
        block = mem_module.get_context_block("anything")
    assert block == ""
