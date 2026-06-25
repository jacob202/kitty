"""Tests for mcp.imagen.tools.batch — parallel generation, partial failure handling."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp.imagen.engines.base import RefusalError
from mcp.imagen.tools.batch import batch_generate


@pytest.fixture(autouse=True)
def _tmp_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect output to tmp so save_image doesn't write to ~/Pictures."""
    monkeypatch.setattr("mcp.imagen.tools.batch.settings.output_dir", tmp_path / "out")


def _fake_engine(prompts_to_fail: set[int] | None = None) -> MagicMock:
    """Build a fake engine whose generate_async returns bytes or raises per index."""
    prompts_to_fail = prompts_to_fail or set()

    async def generate_async(prompt: str, **kwargs: object) -> bytes:
        idx = _fake_engine._counter
        _fake_engine._counter += 1
        if idx in prompts_to_fail:
            raise RefusalError(f"blocked prompt {idx}")
        return f"image_for_{prompt}".encode()

    engine = MagicMock()
    engine.name = "fake"
    engine.model_name = "fake-model"
    _fake_engine._counter = 0
    engine.generate_async = generate_async
    return engine


def test_batch_generate_all_succeed() -> None:
    """All prompts succeed → N images + N path strings returned."""
    fake = _fake_engine()
    with patch("mcp.imagen.tools.batch.engines.get", return_value=fake):
        result = asyncio.run(batch_generate(["a", "b", "c"], engine="fake"))

    # 3 prompts × 2 items (Image + path string) = 6 items
    assert len(result) == 6
    # Every other item is a path string (odd indices)
    for i in range(1, 6, 2):
        assert isinstance(result[i], str)
        assert "Saved:" in result[i]


def test_batch_generate_partial_failure() -> None:
    """Some prompts fail → failures surface as error strings, batch continues."""
    fake = _fake_engine(prompts_to_fail={1})  # second prompt fails
    with patch("mcp.imagen.tools.batch.engines.get", return_value=fake):
        result = asyncio.run(batch_generate(["a", "b", "c"], engine="fake"))

    # 2 successes × 2 items + 1 failure string = 5 items
    assert len(result) == 5
    # One of the items should be a FAILED string
    failed = [r for r in result if isinstance(r, str) and r.startswith("FAILED:")]
    assert len(failed) == 1
    assert "blocked" in failed[0].lower()


def test_batch_generate_empty_prompts() -> None:
    """Empty prompt list → empty result."""
    fake = _fake_engine()
    with patch("mcp.imagen.tools.batch.engines.get", return_value=fake):
        result = asyncio.run(batch_generate([], engine="fake"))
    assert result == []


def test_batch_generate_concurrency_limit() -> None:
    """The semaphore limits concurrent calls — verify it doesn't deadlock."""
    fake = _fake_engine()
    with patch("mcp.imagen.tools.batch.engines.get", return_value=fake):
        result = asyncio.run(
            batch_generate(["a", "b", "c", "d", "d"], engine="fake", concurrency_limit=2)
        )
    # All 5 should succeed regardless of concurrency limit
    successes = [r for r in result if not isinstance(r, str)]
    assert len(successes) == 5


def test_batch_generate_uses_default_engine() -> None:
    """When engine is empty string, the default engine is used."""
    fake = _fake_engine()
    with (
        patch("mcp.imagen.tools.batch.engines.get", return_value=fake) as mock_get,
        patch("mcp.imagen.tools.batch.settings.default_engine", "nano_banana"),
    ):
        asyncio.run(batch_generate(["a"], engine=""))
        mock_get.assert_called_once_with("nano_banana")
