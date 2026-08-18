from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from gateway import image_batches


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    import gateway.paths as gp

    test_db = tmp_path / "kitty.db"
    original = gp.KITTY_DB_FILE
    gp.KITTY_DB_FILE = test_db
    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    image_batches._ensure_db(conn)
    conn.commit()
    conn.close()
    yield
    gp.KITTY_DB_FILE = original


def _estimate(cost: float | None = 0.08, seconds: float | None = 12.0) -> dict:
    return {
        "cost": {
            "state": "known" if cost is not None else "unknown",
            "usd": cost,
            "basis": "observed median" if cost is not None else "unknown",
            "samples": 4 if cost is not None else 0,
        },
        "duration": {
            "state": "known" if seconds is not None else "unknown",
            "seconds": seconds,
            "basis": "observed median" if seconds is not None else "unknown",
            "samples": 4 if seconds is not None else 0,
        },
    }


def test_four_image_batch_scales_estimate_and_creates_four_queued_children() -> None:
    batch = image_batches.create_batch(
        {"prompt": "four cats", "session_id": "imgses_1"}, count=4, per_image_estimate=_estimate()
    )
    assert batch["count"] == 4
    assert batch["status"] == "queued"
    assert batch["estimate"]["cost"]["usd"] == pytest.approx(0.32)
    assert batch["estimate"]["duration"]["seconds"] == pytest.approx(48.0)
    assert [item["status"] for item in batch["items"]] == ["queued"] * 4


@pytest.mark.parametrize("count", [0, 3, 5])
def test_only_product_batch_sizes_are_accepted(count: int) -> None:
    with pytest.raises(ValueError, match="1, 2, or 4"):
        image_batches.create_batch({"prompt": "cats"}, count=count, per_image_estimate=_estimate())


@pytest.mark.asyncio
async def test_worker_claims_one_child_and_persists_provider_result() -> None:
    batch = image_batches.create_batch({"prompt": "cats"}, count=2, per_image_estimate=_estimate())

    async def execute(request: dict) -> dict:
        assert request["prompt"] == "cats"
        return {"job_id": "job_1", "filename": "/tmp/cat.png"}

    assert await image_batches.process_next(execute) is True
    refreshed = image_batches.get_batch(batch["batch_id"])
    assert refreshed["items"][0]["status"] == "succeeded"
    assert refreshed["items"][0]["job_id"] == "job_1"
    assert refreshed["items"][1]["status"] == "queued"


def test_cancel_only_stops_queued_children_not_running_provider_work() -> None:
    batch = image_batches.create_batch({"prompt": "cats"}, count=2, per_image_estimate=_estimate())
    claimed = image_batches.claim_next_item()
    assert claimed is not None

    canceled = image_batches.cancel_batch(batch["batch_id"])
    assert [item["status"] for item in canceled["items"]] == ["running", "canceled"]
    assert canceled["status"] == "running"


def test_restart_marks_interrupted_child_unknown_and_preserves_queued_work() -> None:
    batch = image_batches.create_batch({"prompt": "cats"}, count=4, per_image_estimate=_estimate())
    assert image_batches.claim_next_item() is not None

    assert image_batches.reconcile_inflight() == 1
    refreshed = image_batches.get_batch(batch["batch_id"])
    states = [item["status"] for item in refreshed["items"]]
    assert states.count("unknown") == 1
    assert states.count("queued") == 3
    assert refreshed["status"] == "queued"


@pytest.mark.asyncio
async def test_worker_cancellation_marks_inflight_provider_outcome_unknown() -> None:
    batch = image_batches.create_batch({"prompt": "cats"}, count=1, per_image_estimate=_estimate())

    async def execute(_request: dict) -> dict:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await image_batches.process_next(execute)

    refreshed = image_batches.get_batch(batch["batch_id"])
    assert refreshed["items"][0]["status"] == "unknown"
    assert "provider outcome is unknown" in refreshed["items"][0]["error"]
    assert refreshed["status"] == "unknown"
