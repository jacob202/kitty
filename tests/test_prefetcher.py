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


def test_put_cached_with_current_generation_writes():
    generation = prefetcher.current_generation()
    prefetcher.put_cached("q", "V", generation=generation)
    assert prefetcher.get_cached("q") == "V"


def test_put_cached_with_stale_generation_is_dropped():
    """A write computed before an invalidation must not publish after it —
    otherwise a slow query racing a correction resurrects the pre-correction
    answer for the rest of the TTL (found by review on #629)."""
    generation = prefetcher.current_generation()
    prefetcher.invalidate_all()  # a correction lands mid-compute

    prefetcher.put_cached("q", "STALE", generation=generation)

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


def test_explicit_memory_correction_invalidates_prefetch_cache(tmp_path, monkeypatch):
    """C4-03 / ACC-010 / FI-012: a stale cached context must not outlive an
    explicit correction just because its 300s TTL hasn't expired yet."""
    from gateway import explicit_memory

    monkeypatch.setattr(explicit_memory, "DB_FILE", tmp_path / "kitty.db")

    old = explicit_memory.remember("I prefer dark mode", memory_key="ui.theme")
    prefetcher.put_cached("theme", f"CACHED::{old['text']}")
    assert prefetcher.get_cached("theme") is not None

    explicit_memory.remember("Use light mode now", memory_key="ui.theme")

    assert prefetcher.get_cached("theme") is None


def test_explicit_memory_forget_invalidates_prefetch_cache(tmp_path, monkeypatch):
    from gateway import explicit_memory

    monkeypatch.setattr(explicit_memory, "DB_FILE", tmp_path / "kitty.db")

    row = explicit_memory.remember("My favorite editor is Zed", memory_key="editor")
    prefetcher.put_cached("editor", "CACHED::Zed")
    assert prefetcher.get_cached("editor") is not None

    explicit_memory.forget(row["id"])

    assert prefetcher.get_cached("editor") is None


def test_forget_of_missing_memory_does_not_invalidate_cache(tmp_path, monkeypatch):
    """A no-op forget (unknown/already-inactive id) must not pay for a cache
    wipe it didn't cause — only an actual state change invalidates."""
    from gateway import explicit_memory

    monkeypatch.setattr(explicit_memory, "DB_FILE", tmp_path / "kitty.db")

    prefetcher.put_cached("q", "V")
    assert explicit_memory.forget("exp_does_not_exist") is False
    assert prefetcher.get_cached("q") == "V"


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


def test_history_reader_is_bounded_to_recent_tail(monkeypatch):
    rows = []
    for index in range(1200):
        fp = FP.to_dict()
        rows.append(__import__("json").dumps({"ts": index, "query": f"q-{index}", "fp": fp}))
    prefetcher._HISTORY.write_text("\n".join(rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(prefetcher, "_HISTORY_SCAN", 5)

    loaded = prefetcher._load_history()

    assert [row["query"] for row in loaded] == [f"q-{i}" for i in range(1195, 1200)]


def test_history_hot_path_does_not_use_path_read_text(monkeypatch):
    prefetcher.record("tail only", FP)

    def explode(*_args, **_kwargs):
        raise AssertionError("full-file read_text must not be used")

    monkeypatch.setattr(type(prefetcher._HISTORY), "read_text", explode)
    assert prefetcher._load_history()[-1]["query"] == "tail only"
