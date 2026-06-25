"""Tests for mcp.imagen.cache — SHA256 key generation, get/put, determinism."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp.imagen import cache


@pytest.fixture(autouse=True)
def _tmp_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect cache to a temp dir so tests don't touch the real ~/Pictures."""
    monkeypatch.setattr("mcp.imagen.cache.settings.cache_dir", tmp_path / ".cache")


def test_key_for_is_deterministic() -> None:
    """Same inputs → same key."""
    k1 = cache.key_for("a sunset", "nano_banana", {"aspect_ratio": "1:1", "seed": None})
    k2 = cache.key_for("a sunset", "nano_banana", {"aspect_ratio": "1:1", "seed": None})
    assert k1 == k2
    assert len(k1) == 64  # SHA256 hex


def test_different_prompts_give_different_keys() -> None:
    k1 = cache.key_for("a sunset", "nano_banana", {"seed": None})
    k2 = cache.key_for("a sunrise", "nano_banana", {"seed": None})
    assert k1 != k2


def test_different_engines_give_different_keys() -> None:
    k1 = cache.key_for("a sunset", "nano_banana", {"seed": None})
    k2 = cache.key_for("a sunset", "dalle", {"seed": None})
    assert k1 != k2


def test_different_params_give_different_keys() -> None:
    k1 = cache.key_for("a sunset", "nano_banana", {"aspect_ratio": "1:1"})
    k2 = cache.key_for("a sunset", "nano_banana", {"aspect_ratio": "16:9"})
    assert k1 != k2


def test_seed_zero_vs_none_are_different() -> None:
    """seed=0 and seed=None must produce different cache keys (edge case from plan)."""
    k0 = cache.key_for("prompt", "nano_banana", {"seed": 0})
    k_none = cache.key_for("prompt", "nano_banana", {"seed": None})
    assert k0 != k_none


def test_model_name_invalidation() -> None:
    """Different model_name → different key (cache invalidation on version change)."""
    k1 = cache.key_for("prompt", "nano_banana", {"model_name": "gemini-2.5-flash-image"})
    k2 = cache.key_for("prompt", "nano_banana", {"model_name": "gemini-3.1-flash-image"})
    assert k1 != k2


def test_param_order_does_not_matter() -> None:
    """Dict ordering should not affect the key (sorted items)."""
    k1 = cache.key_for("p", "e", {"a": 1, "b": 2})
    k2 = cache.key_for("p", "e", {"b": 2, "a": 1})
    assert k1 == k2


def test_put_then_get_returns_path() -> None:
    """put copies a file into the cache; get finds it."""
    src = Path("/tmp/test_cache_src.png")
    src.write_bytes(b"\x89PNG fake data")

    key = cache.key_for("test", "nano_banana", {"seed": None})
    assert cache.get(key) is None  # not cached yet

    cached = cache.put(key, src)
    assert cached.exists()
    assert cached.read_bytes() == b"\x89PNG fake data"

    hit = cache.get(key)
    assert hit is not None
    assert hit == cached

    src.unlink()


def test_get_returns_none_for_missing() -> None:
    assert cache.get("nonexistent_key_12345") is None


def test_clear_removes_all() -> None:
    src = Path("/tmp/test_cache_clear.png")
    src.write_bytes(b"data")

    for i in range(3):
        key = cache.key_for(f"prompt_{i}", "nano_banana", {"seed": None})
        cache.put(key, src)

    count = cache.clear()
    assert count == 3
    assert cache.get(cache.key_for("prompt_0", "nano_banana", {"seed": None})) is None
    src.unlink()
