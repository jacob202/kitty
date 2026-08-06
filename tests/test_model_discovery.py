from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from gateway.model_discovery import (
    ModelDiscoveryError,
    discover_openrouter,
    discovery_due,
    load_snapshot,
)
from scripts import model_discovery as discovery_cli

NOW = datetime(2026, 8, 3, 14, 0, tzinfo=timezone.utc)


def _row(
    model_id: str,
    *,
    name: str | None = None,
    modalities: list[str] | None = None,
    description: str = "",
) -> dict:
    return {
        "id": model_id,
        "name": name or model_id,
        "description": description,
        "created": 1785765600,
        "context_length": 131072,
        "architecture": {
            "input_modalities": modalities or ["text"],
            "output_modalities": ["text"],
        },
        "supported_parameters": ["tools", "temperature"],
        "pricing": {"prompt": "0.000001", "completion": "0.000002"},
    }


def test_first_discovery_records_every_model_as_unevaluated_candidate(tmp_path):
    snapshot = tmp_path / "openrouter.json"
    result = discover_openrouter(
        snapshot_path=snapshot,
        now=NOW,
        fetcher=lambda: {
            "data": [
                _row("vendor/new-coder", description="coding model"),
                _row("vendor/new-vision", modalities=["text", "image"]),
            ]
        },
        include_existing=True,
    )

    assert result.total_models == 2
    assert [item["id"] for item in result.new_models] == [
        "vendor/new-coder",
        "vendor/new-vision",
    ]
    assert result.promotion_performed is False
    saved = load_snapshot(snapshot)
    assert saved is not None
    assert saved["promotion_performed"] is False
    by_id = {item["id"]: item for item in saved["models"]}
    assert by_id["vendor/new-coder"]["suggested_roles"] == ["code"]
    assert by_id["vendor/new-vision"]["suggested_roles"] == ["vision"]
    assert all(
        item["evaluation_status"] == "not_evaluated"
        for item in saved["models"]
    )
    assert snapshot.stat().st_mode & 0o777 == 0o600
    assert snapshot.parent.stat().st_mode & 0o777 == 0o700


def test_second_discovery_reports_only_real_catalogue_changes(tmp_path):
    snapshot = tmp_path / "openrouter.json"
    discover_openrouter(
        snapshot_path=snapshot,
        now=NOW,
        fetcher=lambda: {
            "data": [_row("vendor/old"), _row("vendor/stays")]
        },
    )

    result = discover_openrouter(
        snapshot_path=snapshot,
        now=NOW + timedelta(days=7),
        fetcher=lambda: {
            "data": [
                _row("vendor/stays"),
                _row(
                    "vendor/new-reasoning",
                    description="reasoning model",
                ),
            ]
        },
    )

    assert [item["id"] for item in result.new_models] == [
        "vendor/new-reasoning"
    ]
    assert result.new_models[0]["suggested_roles"] == ["think"]
    assert result.removed_model_ids == ("vendor/old",)


def test_discovery_rejects_duplicate_provider_ids(tmp_path):
    with pytest.raises(ModelDiscoveryError, match="repeats model id"):
        discover_openrouter(
            snapshot_path=tmp_path / "openrouter.json",
            now=NOW,
            fetcher=lambda: {
                "data": [_row("same/model"), _row("same/model")]
            },
        )


def test_discovery_cadence_comes_from_the_model_policy(tmp_path):
    snapshot = tmp_path / "openrouter.json"
    discover_openrouter(
        snapshot_path=snapshot,
        now=NOW,
        fetcher=lambda: {"data": [_row("vendor/model")]},
    )
    policy = {"discovery": {"cadence_days": 7}}

    assert (
        discovery_due(
            snapshot_path=snapshot,
            now=NOW + timedelta(days=6, hours=23),
            policy=policy,
        )
        is False
    )
    assert (
        discovery_due(
            snapshot_path=snapshot,
            now=NOW + timedelta(days=7),
            policy=policy,
        )
        is True
    )


def test_snapshot_cannot_claim_that_discovery_promoted_a_model(tmp_path):
    snapshot = tmp_path / "openrouter.json"
    snapshot.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "checked_at": NOW.isoformat(),
                "models": [],
                "promotion_performed": True,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ModelDiscoveryError, match="may not claim or perform"):
        load_snapshot(snapshot)


def test_launch_agent_is_weekly_local_and_has_no_provider_credentials(tmp_path):
    python = tmp_path / "venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")

    plist = discovery_cli.launch_agent_plist(python=python)

    assert plist["RunAtLoad"] is True
    assert plist["StartInterval"] == 7 * 24 * 60 * 60
    assert plist["ProgramArguments"][-1] == "check"
    assert plist["WorkingDirectory"] == str(discovery_cli.ROOT)
    env = plist["EnvironmentVariables"]
    assert "OPENROUTER_API_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    assert "GITHUB_TOKEN" not in env


def test_missing_repository_python_refuses_autostart_definition(tmp_path):
    with pytest.raises(ModelDiscoveryError, match="Python is missing"):
        discovery_cli.launch_agent_plist(
            python=tmp_path / "missing-python"
        )
