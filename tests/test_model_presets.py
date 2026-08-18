from __future__ import annotations

import json
from pathlib import Path

from gateway.model_presets import build_model_picker


def _policy() -> dict:
    return {
        "evaluation": {"cost_reduction_required": 0.25},
        "roles": {
            "auto": {
                "kind": "router",
                "public_name": "Daily Kitty",
                "route": "kitty-default",
                "purpose": "route the turn",
                "incumbent": None,
            },
            "code": {
                "kind": "model_role",
                "public_name": "Code",
                "route": "kitty-code",
                "purpose": "implementation",
                "incumbent": {"provider": "openrouter", "model": "vendor/incumbent"},
            },
        },
    }


def _snapshot(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "promotion_performed": False,
                "checked_at": "2026-08-17T00:00:00+00:00",
                "models": [
                    {
                        "id": "vendor/incumbent",
                        "name": "Incumbent",
                        "context_length": 200000,
                        "input_modalities": ["text"],
                        "output_modalities": ["text"],
                        "supported_parameters": ["tools"],
                        "pricing": {"prompt": "0.000001", "completion": "0.000004"},
                        "suggested_roles": ["code"],
                    },
                    {
                        "id": "vendor/cheaper",
                        "name": "Cheaper candidate",
                        "context_length": 100000,
                        "input_modalities": ["text"],
                        "output_modalities": ["text"],
                        "supported_parameters": ["tools"],
                        "pricing": {"prompt": "0.0000005", "completion": "0.000002"},
                        "suggested_roles": ["code"],
                    },
                    {
                        "id": "vendor/bad-price",
                        "name": "Sentinel price",
                        "pricing": {"prompt": "-1", "completion": "0"},
                        "suggested_roles": ["code"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_picker_preserves_configured_roles_and_exact_model_identity(tmp_path: Path) -> None:
    snapshot = tmp_path / "models.json"
    _snapshot(snapshot)
    payload = build_model_picker(snapshot_path=snapshot, policy=_policy())
    code = next(item for item in payload["presets"] if item["role"] == "code")
    assert code["route"] == "kitty-code"
    assert code["provider"] == "openrouter"
    assert code["model"] == "vendor/incumbent"
    assert code["catalogue"]["context_length"] == 200000
    assert code["catalogue"]["pricing"]["input_usd_per_million"] == 1.0
    assert code["catalogue"]["pricing"]["output_usd_per_million"] == 4.0


def test_role_signal_is_explicitly_heuristic_not_a_quality_claim(tmp_path: Path) -> None:
    snapshot = tmp_path / "models.json"
    _snapshot(snapshot)
    payload = build_model_picker(snapshot_path=snapshot, policy=_policy())
    code = next(item for item in payload["presets"] if item["role"] == "code")
    assert "heuristic" in code["catalogue"]["role_signal"]["basis"].lower()
    assert code["catalogue"]["quality"]["state"] == "unknown"
    assert code["catalogue"]["latency"]["state"] == "unknown"


def test_cheaper_candidate_requires_savings_on_both_input_and_output(tmp_path: Path) -> None:
    snapshot = tmp_path / "models.json"
    _snapshot(snapshot)
    payload = build_model_picker(snapshot_path=snapshot, policy=_policy())
    code = next(item for item in payload["presets"] if item["role"] == "code")
    assert [item["model"] for item in code["alternatives"]] == ["vendor/cheaper"]
    assert "quality and latency are unevaluated" in code["alternatives"][0]["reason"]


def test_negative_or_zero_provider_prices_never_create_savings_claims(tmp_path: Path) -> None:
    snapshot = tmp_path / "models.json"
    _snapshot(snapshot)
    payload = build_model_picker(snapshot_path=snapshot, policy=_policy())
    code = next(item for item in payload["presets"] if item["role"] == "code")
    assert all(item["model"] != "vendor/bad-price" for item in code["alternatives"])


def test_missing_discovery_keeps_configured_shortlist_with_explicit_unknown_state(tmp_path: Path) -> None:
    payload = build_model_picker(snapshot_path=tmp_path / "missing.json", policy=_policy())
    code = next(item for item in payload["presets"] if item["role"] == "code")
    assert payload["discovery"]["state"] == "missing"
    assert code["model"] == "vendor/incumbent"
    assert code["catalogue_state"] == "not_observed"
    assert code["alternatives"] == []
