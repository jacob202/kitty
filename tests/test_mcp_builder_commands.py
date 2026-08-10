from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mcp.builder import commands


@pytest.fixture()
def manifest() -> dict:
    return {
        "manifest_version": 1,
        "initiative_id": "mcp-proof-1",
        "title": "MCP proof",
        "description": "Build one proof seam.",
        "packets": [
            {
                "id": "packet-1",
                "title": "Implement seam",
                "objective": "Implement the requested feature",
                "depends_on": [],
                "acceptance_criteria": ["tests pass"],
                "allowed_paths": ["mcp/builder/", "tests/"],
                "policy": {"max_attempts": 2, "priority": 5},
                "validation_commands": [
                    "python3.12 -m pytest tests/test_mcp_builder_commands.py -q"
                ],
            }
        ],
    }


def _patch_prepare_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    base: str,
    digest: str,
) -> None:
    monkeypatch.setattr(commands.repo_tools, "repo_root", lambda: Path("/tmp/kitty"))
    monkeypatch.setattr(commands.repo_tools, "read_tracked_file", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(commands.bi, "resolve_base_sha", lambda *_a, **_k: base)
    monkeypatch.setattr(commands.bi, "validate_manifest", lambda _m: [])
    monkeypatch.setattr(commands.bi, "warn_manifest", lambda _m, repo_root=None: [])
    monkeypatch.setattr(commands.bi, "manifest_sha256", lambda _m: digest)


def test_mission_prepare_binds_artifacts_manifest_and_base_without_applying(
    monkeypatch: pytest.MonkeyPatch, manifest: dict
) -> None:
    base = "b" * 40
    digest = "d" * 64
    _patch_prepare_dependencies(monkeypatch, base=base, digest=digest)
    apply = MagicMock()
    monkeypatch.setattr(commands.bi, "apply_manifest", apply)

    result = commands.mission_prepare(
        manifest,
        design_path="docs/superpowers/specs/design.md",
        design_sha="1" * 40,
        plan_path="docs/superpowers/plans/plan.md",
        plan_sha="2" * 40,
        expected_base_sha=base,
    )

    assert result["ok"] is True
    assert result["state"] == "prepared"
    assert result["manifest_sha256"] == digest
    assert result["expected_base_sha"] == base
    assert result["approval_nonce"]
    marker_payload = result["prepared_manifest"]["description"].split(
        commands.MCP_ARTIFACT_MARKER, 1
    )[1]
    refs = json.loads(marker_payload)
    assert refs["design_path"].endswith("design.md")
    assert refs["design_sha"] == "1" * 40
    assert refs["plan_sha"] == "2" * 40
    apply.assert_not_called()


def test_mission_prepare_refuses_stale_base(monkeypatch: pytest.MonkeyPatch, manifest: dict) -> None:
    _patch_prepare_dependencies(monkeypatch, base="b" * 40, digest="d" * 64)

    result = commands.mission_prepare(
        manifest,
        design_path="docs/superpowers/specs/design.md",
        design_sha="1" * 40,
        plan_path="docs/superpowers/plans/plan.md",
        plan_sha="2" * 40,
        expected_base_sha="a" * 40,
    )

    assert result["ok"] is False
    assert result["error_code"] == "stale_base"


def test_mission_approve_recomputes_binding_and_delegates_to_builder(
    monkeypatch: pytest.MonkeyPatch, manifest: dict
) -> None:
    base = "b" * 40
    digest = "d" * 64
    _patch_prepare_dependencies(monkeypatch, base=base, digest=digest)
    prepared = commands.mission_prepare(
        manifest,
        design_path="docs/superpowers/specs/design.md",
        design_sha="1" * 40,
        plan_path="docs/superpowers/plans/plan.md",
        plan_sha="2" * 40,
        expected_base_sha=base,
    )
    apply = MagicMock(
        return_value={
            "status": "created",
            "initiative_id": "mcp-proof-1",
            "manifest_sha256": digest,
            "packets": [{"packet_id": "packet-1", "task_id": "kb_1"}],
        }
    )
    monkeypatch.setattr(commands.bi, "apply_manifest", apply)

    approved = commands.mission_approve(
        prepared["prepared_manifest"],
        expected_manifest_sha=digest,
        expected_base_sha=base,
        approval_nonce=prepared["approval_nonce"],
    )

    assert approved["ok"] is True
    assert approved["state"] == "accepted"
    assert approved["mission_id"] == "mcp-proof-1"
    assert approved["tasks"] == [{"packet_id": "packet-1", "task_id": "kb_1"}]
    apply.assert_called_once()


def test_mission_approve_replay_is_harmless_idempotent(
    monkeypatch: pytest.MonkeyPatch, manifest: dict
) -> None:
    base = "b" * 40
    digest = "d" * 64
    _patch_prepare_dependencies(monkeypatch, base=base, digest=digest)
    prepared = commands.mission_prepare(
        manifest,
        design_path="docs/superpowers/specs/design.md",
        design_sha="1" * 40,
        plan_path="docs/superpowers/plans/plan.md",
        plan_sha="2" * 40,
        expected_base_sha=base,
    )
    monkeypatch.setattr(
        commands.bi,
        "apply_manifest",
        lambda *_a, **_k: {
            "status": "unchanged",
            "initiative_id": "mcp-proof-1",
            "manifest_sha256": digest,
            "packets": [{"packet_id": "packet-1", "task_id": "kb_1"}],
        },
    )

    approved = commands.mission_approve(
        prepared["prepared_manifest"],
        expected_manifest_sha=digest,
        expected_base_sha=base,
        approval_nonce=prepared["approval_nonce"],
    )

    assert approved["ok"] is True
    assert approved["apply_status"] == "unchanged"
    assert approved["tasks"][0]["task_id"] == "kb_1"


def test_mission_approve_rejects_stale_nonce(monkeypatch: pytest.MonkeyPatch, manifest: dict) -> None:
    base = "b" * 40
    digest = "d" * 64
    _patch_prepare_dependencies(monkeypatch, base=base, digest=digest)

    result = commands.mission_approve(
        manifest,
        expected_manifest_sha=digest,
        expected_base_sha=base,
        approval_nonce="wrong",
    )

    assert result["ok"] is False
    assert result["error_code"] == "approval_mismatch"


def test_pause_resume_cancel_delegate_to_canonical_builder_functions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pause = MagicMock()
    resume = MagicMock()
    cancel = MagicMock(return_value={"id": "kb_1", "state": "cancelled"})
    monkeypatch.setattr(commands.bi, "pause_initiative", pause)
    monkeypatch.setattr(commands.bi, "resume_initiative", resume)
    monkeypatch.setattr(commands.bq, "operator_cancel_task", cancel)

    paused = commands.execution_pause("mission-1", "user asked")
    resumed = commands.execution_resume("mission-1")
    cancelled = commands.execution_cancel("kb_1", "superseded", actor="chatgpt")

    assert paused["ok"] and paused["state"] == "paused"
    assert resumed["ok"] and resumed["state"] == "active"
    assert cancelled["ok"] and cancelled["state"] == "cancelled"
    pause.assert_called_once_with("mission-1", reason="user asked")
    resume.assert_called_once_with("mission-1")
    cancel.assert_called_once_with("kb_1", reason="superseded", actor="chatgpt")


def test_execution_start_does_not_duplicate_existing_live_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        commands,
        "work_status",
        lambda **_: {
            "ok": True,
            "state": "active",
            "work": {
                "initiative_id": "mission-1",
                "state": "active",
                "packets": [
                    {"packet_id": "p1", "task_id": "kb_1", "task_state": "running"}
                ],
            },
        },
    )
    popen = MagicMock()
    monkeypatch.setattr(commands.subprocess, "Popen", popen)

    result = commands.execution_start("mission-1")

    assert result["ok"] is True
    assert result["state"] == "running"
    assert result["existing"] is True
    popen.assert_not_called()


def test_execution_start_launches_fixed_free_builder_argv_and_returns_promptly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(commands.repo_tools, "repo_root", lambda: tmp_path)
    (tmp_path / "kitty").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(
        commands,
        "work_status",
        lambda **_: {
            "ok": True,
            "state": "active",
            "work": {
                "initiative_id": "mission-1",
                "state": "active",
                "packets": [
                    {"packet_id": "p1", "task_id": "kb_1", "task_state": "queued"}
                ],
            },
        },
    )
    proc = MagicMock(pid=4321)
    popen = MagicMock(return_value=proc)
    monkeypatch.setattr(commands.subprocess, "Popen", popen)

    result = commands.execution_start("mission-1", free=True)

    assert result["ok"] is True
    assert result["state"] == "launched"
    assert result["launcher_pid"] == 4321
    argv = popen.call_args.args[0]
    assert argv[:5] == [str(tmp_path / "kitty"), "builder", "initiative", "run", "mission-1"]
    assert "--free" in argv
    assert "--publish" not in argv
    assert popen.call_args.kwargs["shell"] is False
    assert popen.call_args.kwargs["start_new_session"] is True


def test_execution_start_paid_route_requires_explicit_spend_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        commands,
        "work_status",
        lambda **_: {"ok": True, "state": "active", "work": {"packets": []}},
    )

    result = commands.execution_start("mission-1", free=False, spend_authorized=False)

    assert result["ok"] is False
    assert result["error_code"] == "spend_not_authorized"


def test_publication_prepare_requires_explicit_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    publish = MagicMock()
    monkeypatch.setattr(commands, "command_publish", publish)

    refused = commands.publication_prepare("kb_1", confirmed=False)
    assert refused["ok"] is False
    assert refused["error_code"] == "approval_required"
    publish.assert_not_called()

    publish.return_value = MagicMock(
        ok=True,
        action="publish",
        task_id="kb_1",
        error=None,
        detail="published",
        evidence={"pr_number": 451},
    )
    accepted = commands.publication_prepare("kb_1", confirmed=True, actor="jacob")
    assert accepted["ok"] is True
    assert accepted["pr"]["pr_number"] == 451
