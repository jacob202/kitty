"""Tests for the optional MemPalace StoreAdapter and its registration."""

import asyncio

from gateway import memory_graph
from gateway.memory_graph import Source
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
    assert len(a) == 1
    assert a[0].text == "hello"
    assert a[0].source == Source.MEMORY_PALACE
    assert a[0].metadata == {"related": ["a", "b"]}
    b = MemPalaceAdapter._parse('{"results": [{"content": "hi"}]}')
    assert len(b) == 1
    assert b[0].text == "hi"
    assert MemPalaceAdapter._parse("not json") == []
    assert MemPalaceAdapter._parse('[{"related": ["x"]}]') == []  # no text -> dropped


def test_not_registered_by_default(monkeypatch):
    monkeypatch.delenv("KITTY_MEMPALACE_ENABLED", raising=False)
    names = [a.name for a in memory_graph._default_adapters()]
    assert "memory_palace" not in names
    assert names == ["memory", "knowledge", "journal", "traces", "todos", "inbox", "signals"]


def test_registered_when_enabled(monkeypatch):
    monkeypatch.setenv("KITTY_MEMPALACE_ENABLED", "1")
    names = [a.name for a in memory_graph._default_adapters()]
    assert "memory_palace" in names
