from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gateway import image_estimates


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    import gateway.paths as gp

    test_db = tmp_path / "kitty.db"
    original = gp.KITTY_DB_FILE
    gp.KITTY_DB_FILE = test_db
    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    image_estimates._ensure_db(conn)
    conn.commit()
    conn.close()
    yield
    gp.KITTY_DB_FILE = original


def test_local_renderer_cost_is_known_zero_without_history() -> None:
    estimate = image_estimates.estimate("comfyui", model_id="RealCoreXL.safetensors", operation="txt2img")
    assert estimate["cost"] == {
        "state": "known",
        "usd": 0.0,
        "basis": "local renderer; no provider-billed API usage",
        "samples": 0,
    }
    assert estimate["duration"]["state"] == "unknown"


def test_hosted_cost_is_unknown_until_provider_cost_is_observed() -> None:
    estimate = image_estimates.estimate("openrouter", model_id="vendor/image", operation="txt2img")
    assert estimate["cost"]["state"] == "unknown"
    assert estimate["cost"]["usd"] is None


def test_observed_median_drives_cost_and_duration_after_three_samples() -> None:
    for i, (cost, seconds) in enumerate(((0.06, 10), (0.08, 14), (0.07, 12)), start=1):
        image_estimates.record_observation(
            job_id=f"job_{i}", provider="openrouter", model_id="vendor/image",
            operation="txt2img", actual_cost_usd=cost, duration_seconds=seconds,
        )
    estimate = image_estimates.estimate("openrouter", model_id="vendor/image", operation="txt2img")
    assert estimate["cost"]["state"] == "known"
    assert estimate["cost"]["usd"] == pytest.approx(0.07)
    assert estimate["cost"]["samples"] == 3
    assert estimate["duration"]["state"] == "known"
    assert estimate["duration"]["seconds"] == pytest.approx(12.0)
    assert estimate["duration"]["samples"] == 3


def test_duration_stays_unknown_before_three_samples() -> None:
    for i, seconds in enumerate((10, 14), start=1):
        image_estimates.record_observation(
            job_id=f"job_{i}", provider="flux", model_id="flux-dev",
            operation="txt2img", actual_cost_usd=0.04, duration_seconds=seconds,
        )
    estimate = image_estimates.estimate("flux", model_id="flux-dev", operation="txt2img")
    assert estimate["cost"]["state"] == "known"
    assert estimate["duration"]["state"] == "unknown"


@pytest.mark.parametrize("cost", [-0.01, float("inf"), float("nan")])
def test_invalid_provider_cost_is_rejected(cost: float) -> None:
    with pytest.raises(ValueError, match="actual_cost_usd"):
        image_estimates.record_observation(
            job_id="job_bad", provider="openrouter", model_id="vendor/image",
            operation="txt2img", actual_cost_usd=cost, duration_seconds=12,
        )


def test_estimates_are_scoped_to_exact_model_not_vague_family() -> None:
    for i in range(3):
        image_estimates.record_observation(
            job_id=f"job_exact_{i}", provider="openrouter", model_id="vendor/exact-model",
            operation="txt2img", actual_cost_usd=0.05, duration_seconds=11,
        )
    unknown = image_estimates.estimate("openrouter", model_id="vendor/other-model", operation="txt2img")
    assert unknown["cost"]["state"] == "unknown"
    assert unknown["duration"]["state"] == "unknown"
