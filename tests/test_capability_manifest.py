from __future__ import annotations

from datetime import datetime, timezone

import pytest

from gateway import runtime_manifest


def _times() -> tuple[str, str]:
    observed = runtime_manifest._timestamp(datetime(2026, 8, 17, tzinfo=timezone.utc))
    valid = runtime_manifest._timestamp(datetime(2026, 8, 17, 0, 0, 15, tzinfo=timezone.utc))
    return observed, valid


def test_every_runtime_fact_carries_truth_metadata() -> None:
    observed, valid = _times()
    fact = runtime_manifest._fact(
        {"ok": True}, source="test-probe", observed_at=observed, valid_until=valid
    )
    assert fact == {
        "state": "available",
        "value": {"ok": True},
        "source": "test-probe",
        "observed_at": observed,
        "valid_until": valid,
    }


def test_probe_failure_is_unknown_not_unavailable() -> None:
    observed, valid = _times()
    fact = runtime_manifest._unknown(
        source="provider-probe", observed_at=observed, valid_until=valid, reason="timeout"
    )
    assert fact["state"] == "unknown"
    assert fact["value"] is None
    assert fact["reason"] == "timeout"


def test_provider_configuration_does_not_claim_live_health(monkeypatch: pytest.MonkeyPatch) -> None:
    observed, valid = _times()
    provider_id, config = next(
        (provider_id, config)
        for provider_id, config in runtime_manifest.PROVIDERS.items()
        if config.api_key_env
    )
    for key in config.api_key_env:
        monkeypatch.delenv(key, raising=False)
    facts = runtime_manifest._provider_facts(observed_at=observed, valid_until=valid)
    fact = next(item for item in facts if item["id"] == provider_id)
    assert fact["configuration"] == "unconfigured"
    assert fact["state"] == "unavailable"

    monkeypatch.setenv(config.api_key_env[0], "configured-for-test")
    facts = runtime_manifest._provider_facts(observed_at=observed, valid_until=valid)
    fact = next(item for item in facts if item["id"] == provider_id)
    assert fact["configuration"] == "configured"
    assert fact["state"] == "unknown"
    assert "live provider health is not probed" in fact["reason"]


def test_manifest_owns_runtime_capabilities_not_domain_dashboard_data() -> None:
    source = (runtime_manifest.ROOT / "gateway" / "runtime_manifest.py").read_text(encoding="utf-8")
    for forbidden in ('"todos"', '"deadlines"', '"repairs"', '"weather"'):
        assert forbidden not in source, f"runtime manifest must not become a duplicate domain database: {forbidden}"


def test_manifest_exposes_runtime_areas_used_by_the_product_shell() -> None:
    source = (runtime_manifest.ROOT / "gateway" / "runtime_manifest.py").read_text(encoding="utf-8")
    for required in ('"execution"', '"builder"', '"inference"', '"available_models"', '"tools"', '"connections"', '"approvals"'):
        assert required in source
