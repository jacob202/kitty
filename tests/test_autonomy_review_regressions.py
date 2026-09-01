from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway import builder_autonomy as aut
from gateway import builder_contract_gate as gate
from gateway import builder_loop as bl
from gateway import builder_supervisor as bs


def test_packet_registry_rejects_explicit_null_packets(tmp_path: Path) -> None:
    root = tmp_path
    slates = root / "docs" / "packets" / "slates"
    slates.mkdir(parents=True)
    (slates / "bad.source.json").write_text(
        json.dumps({"initiative_id": "bad", "packets": None}), encoding="utf-8"
    )
    with pytest.raises(aut.PacketRegistryError, match="packets must be a list"):
        aut.load_packet_registry(root)


def test_repo_root_forbidden_path_overlaps_every_changed_path() -> None:
    assert gate._overlap("gateway/a.py", ".") is True
    assert gate._overlap("README.md", "./") is True


def test_free_adapter_carries_openrouter_auth_and_rejects_model_overlap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sentinel")
    env = bl._sanitize_free_adapter_env(
        {
            "KITTYBUILDER_MODELS": "openrouter/poolside/laguna-xs-2.1:free openrouter/tencent/hy3:free",
            "KITTYBUILDER_REVIEW_MODEL": "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
        }
    )
    assert env["OPENROUTER_API_KEY"] == "sentinel"
    with pytest.raises(bl.LoopError, match="independent"):
        bl._sanitize_free_adapter_env(
            {
                "KITTYBUILDER_MODEL": "openrouter/tencent/hy3:free",
                "KITTYBUILDER_REVIEW_MODEL": "openrouter/tencent/hy3:free",
            }
        )


def test_review_provider_exhaustion_reason_tracks_paid_lane() -> None:
    assert "paid reviewer" in bl._review_provider_exhaustion_reason(
        "cheap", {"KITTYBUILDER_REVIEW_AGENT": "paid-reviewer"}
    )
    assert "free reviewer" in bl._review_provider_exhaustion_reason(
        "free", {"KITTYBUILDER_REVIEW_AGENT": "free-reviewer"}
    )


def test_github_snapshot_rejects_non_array_and_ignores_cross_repository_pr(tmp_path: Path) -> None:
    class Result:
        returncode = 0
        stderr = ""
        def __init__(self, stdout: str): self.stdout = stdout

    bad = bs.github_truth_snapshot(tmp_path, run_cmd=lambda *_a, **_k: Result("{}"))
    assert bad["available"] is False
    assert "array" in bad["error"].lower()

    calls = []
    rows = [{
        "number": 1, "state": "OPEN", "mergedAt": None,
        "headRefName": "kittybuilder/task", "isCrossRepository": True,
    }]
    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return Result(json.dumps(rows))
    truth = bs.github_truth_snapshot(tmp_path, run_cmd=runner)
    assert truth["by_head"] == {}
    assert "isCrossRepository" in calls[0][0][calls[0][0].index("--json") + 1]


def test_github_snapshot_sanitizes_ambient_gh_tokens(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "bad-gh")
    monkeypatch.setenv("GITHUB_TOKEN", "bad-github")
    seen = {}
    class Result:
        returncode = 0
        stdout = "[]"
        stderr = ""
    def runner(_args, **kwargs):
        seen.update(kwargs.get("env") or {})
        return Result()
    bs.github_truth_snapshot(tmp_path, run_cmd=runner)
    assert "GH_TOKEN" not in seen
    assert "GITHUB_TOKEN" not in seen


def test_default_free_dsh_models_are_explicit_and_disjoint() -> None:
    worker = (Path(__file__).parents[1] / "scripts" / "kittybuilder_dsh_worker.sh").read_text()
    reviewer = (Path(__file__).parents[1] / "scripts" / "kittybuilder_dsh_reviewer.sh").read_text()
    assert '"openrouter/free"' not in worker
    assert '"openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"' in reviewer
    assert "laguna-xs-2.1:free" in worker and "hy3:free" in worker


def test_dsh_launcher_uses_ephemeral_home_user_preset_and_secret_free_openrouter_settings() -> None:
    launcher = (Path(__file__).parents[1] / "scripts" / "kittybuilder_dsh.sh").read_text()
    assert '.agent-presets' in launcher
    assert 'includeUserRoot: true' in launcher
    assert 'apiKeyEnv: OPENROUTER_API_KEY' in launcher
    assert 'settings.yaml' in launcher
    assert 'mktemp -d' in launcher


def test_preflight_accepts_requested_route_override(monkeypatch: pytest.MonkeyPatch) -> None:
    import inspect
    assert "requested_route" in inspect.signature(bs.preflight_packet).parameters


def test_reviewer_prompt_is_an_explicit_sandbox_write_path() -> None:
    source = Path(bl.__file__).read_text()
    assert 'f".kittybuilder-review-prompt-{attempt_id}.txt"' in source


def test_worker_prompt_is_trusted_transient_residue() -> None:
    from gateway import builder_scope
    assert builder_scope.is_expected_residue(".kittybuilder-prompt-42.txt")
