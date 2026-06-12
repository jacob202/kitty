"""Tests for the optional MemPalace StoreAdapter and its registration."""
import asyncio

import pytest

from gateway import memory_graph
from gateway.mempalace_adapter import MemPalaceAdapter


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("KITTY_MEMPALACE_ENABLED", raising=False)
    assert MemPalaceAdapter.is_enabled() is False


def test_enabled_via_flag(monkeypatch):
    monkeypatch.setenv("KITTY_MEMPALACE_ENABLED", "1")
    assert MemPalaceAdapter.is_enabled() is True


def test_fetch_empty_when_disabled(monkeypatch):
    monkeypatch.delenv("KITTY_MEMPALACE_ENABLED", raising=False)
    assert asyncio.run(MemPalaceAdapter().fetch("anything")) == []


def test_fetch_empty_when_cli_missing(monkeypatch):
    monkeypatch.setenv("KITTY_MEMPALACE_ENABLED", "1")
    monkeypatch.setattr("gateway.mempalace_adapter.shutil.which", lambda _: None)
    assert asyncio.run(MemPalaceAdapter().fetch("query")) == []


def test_parse_handles_list_and_dict_and_garbage():
    a = MemPalaceAdapter._parse('[{"text": "hello", "related": ["a", "b"]}]')
    assert a == [{"text": "hello", "related": ["a", "b"]}]
    b = MemPalaceAdapter._parse('{"results": [{"content": "hi"}]}')
    assert b == [{"text": "hi", "related": []}]
    assert MemPalaceAdapter._parse("not json") == []
    assert MemPalaceAdapter._parse('[{"related": ["x"]}]') == []  # no text -> dropped


def test_format_and_correlate():
    items = [{"text": "fact one", "related": ["r1"]}, {"text": "fact two", "related": []}]
    out = MemPalaceAdapter().format_items(items)
    assert "## Memory Palace" in out and "- fact one" in out
    assert MemPalaceAdapter().correlate(items, {}) == ["1 typed relationships"]
    assert MemPalaceAdapter().format_items([]) == ""


def test_not_registered_by_default(monkeypatch):
    monkeypatch.delenv("KITTY_MEMPALACE_ENABLED", raising=False)
    names = [a.name for a in memory_graph._default_adapters()]
    assert "memory_palace" not in names
    assert names == ["memory", "knowledge", "journal", "traces", "todos"]


def test_registered_when_enabled(monkeypatch):
    monkeypatch.setenv("KITTY_MEMPALACE_ENABLED", "1")
    names = [a.name for a in memory_graph._default_adapters()]
    assert "memory_palace" in names
