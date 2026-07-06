"""Tests for the predictive context prefetcher."""

import time

import pytest

from gateway import memory_graph, prefetcher

FP = prefetcher.Fingerprint(time_slot="1-2", git_branch="feat/x", recent_files=("a.py", "b.py"))


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Per-test history file + clean cache so tests don't bleed into each other."""
    monkeypatch.setattr(prefetcher, "_HISTORY", tmp_path / "hist.jsonl")
    prefetcher._cache.clear()
    yield
    prefetcher._cache.clear()


def test_fingerprint_capture_shape():
    fp = prefetcher.capture_fingerprint()
    assert isinstance(fp.time_slot, str) and "-" in fp.time_slot
    assert isinstance(fp.recent_files, tuple)


def test_record_then_predict_returns_query():
    prefetcher.record("what's my schedule", FP)
    assert prefetcher.predict(FP) == ["what's my schedule"]


def test_predict_empty_without_history():
    assert prefetcher.predict(FP) == []


def test_predict_ranks_branch_match_first():
    other = prefetcher.Fingerprint(time_slot="9-9", git_branch="main", recent_files=())
    prefetcher.record("weak", other)
    prefetcher.record("strong", FP)
    assert prefetcher.predict(FP)[0] == "strong"


def test_blank_query_is_not_recorded():
    prefetcher.record("   ", FP)
    assert prefetcher.predict(FP) == []


def test_cache_ttl_expiry(monkeypatch):
    prefetcher.put_cached("q", "V")
    assert prefetcher.get_cached("q") == "V"
    future = time.time() + prefetcher._CACHE_TTL_S + 1
    monkeypatch.setattr(prefetcher.time, "time", lambda: future)
    assert prefetcher.get_cached("q") is None


@pytest.mark.asyncio
async def test_warm_populates_cache_and_does_not_record_predictions(monkeypatch):
    monkeypatch.setattr(prefetcher, "capture_fingerprint", lambda: FP)
    prefetcher.record("recall my meds", FP)

    calls = []

    async def fake_unified(query, *, _record=True):
        calls.append((query, _record))
        prefetcher.put_cached(query, f"CTX::{query}")
        return f"CTX::{query}"

    monkeypatch.setattr(memory_graph, "unified_context", fake_unified)

    warmed = await prefetcher.warm()

    assert warmed == 1
    assert calls == [("recall my meds", False)]  # a prediction must not feed itself back
    assert prefetcher.get_cached("recall my meds") == "CTX::recall my meds"


@pytest.mark.asyncio
async def test_unified_context_returns_warm_cache_without_computing(monkeypatch):
    prefetcher.put_cached("hot", "WARM")
    hit_graph = {"called": False}

    class _FakeGraph:
        async def unified_context(self, query):
            hit_graph["called"] = True
            return "COLD"

    monkeypatch.setattr(memory_graph, "_get_graph", lambda: _FakeGraph())

    out = await memory_graph.unified_context("hot")

    assert out == "WARM"
    assert hit_graph["called"] is False
