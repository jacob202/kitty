"""Focused tests for the authenticated RunPod worker smoke script."""

from __future__ import annotations

import argparse
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

from gateway.runpod_control import PodInfo


def _load_script() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "runpod_worker_smoke_test.py"
    spec = importlib.util.spec_from_file_location("runpod_worker_smoke_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke = _load_script()


def _args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "prompt": "a brass robot",
        "output_dir": str(tmp_path),
        "seed": 42,
        "existing_pod_id": None,
        "cloud_type": "COMMUNITY",
        "container_disk_gb": 30,
        "volume_gb": 20,
        "dry_run": False,
        "accept_charges": False,
        "keep_pod": False,
        "accept_continuing_charges": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _pod(
    pod_id: str,
    name: str,
    *,
    managed: bool,
) -> PodInfo:
    env = {
        "KITTY_MANAGED": "1" if managed else "0",
        "KITTY_SESSION_EXPIRES_AT": datetime.now(timezone.utc).isoformat(),
    }
    return PodInfo.from_payload(
        {
            "id": pod_id,
            "name": name,
            "desiredStatus": "RUNNING",
            "costPerHr": 0.2,
            "env": env,
        }
    )


def test_paid_pod_creation_requires_explicit_acknowledgement(tmp_path):
    with pytest.raises(smoke.WorkerSmokeError, match="accept-charges"):
        smoke._validate_acknowledgements(
            _args(tmp_path),
            creating_pod=True,
        )


def test_existing_pod_requires_continuing_charge_acknowledgement(tmp_path):
    with pytest.raises(smoke.WorkerSmokeError, match="continuing-charges"):
        smoke._validate_acknowledgements(
            _args(tmp_path, existing_pod_id="pod-1"),
            creating_pod=False,
        )


def test_dry_run_does_not_require_secrets(monkeypatch, tmp_path):
    for name in (
        "RUNPOD_API_KEY",
        "RUNPOD_TEMPLATE_ID",
        "KITTY_WORKER_BEARER_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)

    first = smoke.run_smoke(_args(tmp_path, dry_run=True))
    second = smoke.run_smoke(_args(tmp_path, dry_run=True))
    first_path = __import__("asyncio").run(first)
    second_path = __import__("asyncio").run(second)

    assert first_path.exists()
    assert second_path.exists()
    assert first_path != second_path
    assert "RUNPOD_API_KEY" not in first_path.read_text(encoding="utf-8")


def test_config_rejects_nonfinite_cost_ceiling(monkeypatch):
    monkeypatch.setenv("RUNPOD_MAX_HOURLY_RATE", "nan")
    with pytest.raises(Exception, match="positive and finite"):
        smoke.Config.from_env(
            require_live_secrets=False,
            require_template=False,
        )


@pytest.mark.asyncio
async def test_ambiguous_reconciliation_deletes_only_exact_managed_name():
    exact_name = "kitty-image-run-123"

    class Client:
        def __init__(self) -> None:
            self.deleted: list[str] = []

        async def list_pods(self):
            return [
                _pod("exact", exact_name, managed=True),
                _pod("wrong-name", "kitty-image-other", managed=True),
                _pod("unmanaged", exact_name, managed=False),
            ]

        async def delete_pod(self, pod_id: str):
            self.deleted.append(pod_id)

    client = Client()
    deleted = await smoke.reconcile_ambiguous_creation(client, exact_name)

    assert deleted == ["exact"]
    assert client.deleted == ["exact"]


def test_estimated_cost_uses_seconds():
    assert smoke.estimated_compute_cost(0.36, 600) == pytest.approx(0.06)
