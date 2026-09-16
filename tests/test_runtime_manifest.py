from __future__ import annotations

from pathlib import Path

import pytest

from gateway import runtime_manifest


@pytest.mark.asyncio
async def test_manifest_exposes_server_owned_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "isolated-data"
    monkeypatch.setattr(runtime_manifest, "DATA_DIR", data_root)
    monkeypatch.setattr(
        runtime_manifest,
        "_git_snapshot",
        lambda: {
            "root": str(tmp_path),
            "branch": "candidate",
            "commit": "a" * 40,
            "dirty": False,
            "changed_paths": 0,
        },
    )

    async def fake_models(**kwargs):
        observed_at = kwargs["observed_at"]
        valid_until = kwargs["valid_until"]
        return (
            runtime_manifest._fact(
                ["local/test"],
                source="test",
                observed_at=observed_at,
                valid_until=valid_until,
            ),
            runtime_manifest._fact(
                {"endpoint": "test", "model_count": 1},
                source="test",
                observed_at=observed_at,
                valid_until=valid_until,
            ),
        )

    monkeypatch.setattr(runtime_manifest, "_litellm_models", fake_models)
    monkeypatch.setattr(
        runtime_manifest,
        "_project_fact",
        lambda *args, **kwargs: {"state": "unavailable", "value": None},
    )
    monkeypatch.setattr(
        runtime_manifest,
        "_builder_fact",
        lambda **kwargs: {"state": "unavailable", "value": None},
    )
    monkeypatch.setattr(runtime_manifest, "_provider_facts", lambda **kwargs: [])
    monkeypatch.setattr(
        runtime_manifest,
        "_tool_fact",
        lambda **kwargs: {"state": "available", "value": []},
    )
    monkeypatch.setattr(
        runtime_manifest,
        "_approval_fact",
        lambda **kwargs: {"state": "available", "value": {}},
    )

    manifest = await runtime_manifest.compose_manifest(project_id=1)

    fact = manifest["storage"]["data_root"]
    assert fact["state"] == "available"
    assert fact["value"] == str(data_root.resolve())
    assert fact["source"] == "gateway.paths.DATA_DIR"
