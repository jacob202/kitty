from __future__ import annotations

from pathlib import Path

import pytest

from mcp.builder import commands


def _manifest() -> dict:
    return {
        "manifest_version": 1,
        "initiative_id": "lineage-proof",
        "title": "Lineage proof",
        "description": "Bind planning artifacts.",
        "packets": [
            {
                "id": "p1",
                "title": "Implement",
                "objective": "Implement approved plan",
                "depends_on": [],
                "acceptance_criteria": ["tests pass"],
                "allowed_paths": ["mcp/builder/"],
                "validation_commands": [],
            }
        ],
    }


def _patch_common(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commands.repo_tools, "repo_root", lambda: Path("/tmp/kitty"))
    monkeypatch.setattr(commands.repo_tools, "read_tracked_file", lambda *a, **k: {})
    monkeypatch.setattr(commands.bi, "resolve_base_sha", lambda *_a, **_k: "b" * 40)
    monkeypatch.setattr(commands.bi, "validate_manifest", lambda _m: [])
    monkeypatch.setattr(commands.bi, "warn_manifest", lambda _m, repo_root=None: [])
    monkeypatch.setattr(commands.bi, "manifest_sha256", lambda _m: "d" * 64)


def test_mission_prepare_requires_base_to_design_to_plan_ancestry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_common(monkeypatch)
    seen: list[tuple[str, str]] = []

    def ancestor(left: str, right: str) -> bool:
        seen.append((left, right))
        return True

    monkeypatch.setattr(commands.repo_tools, "commit_is_ancestor", ancestor)

    result = commands.mission_prepare(
        _manifest(),
        design_path="docs/superpowers/specs/design.md",
        design_sha="1" * 40,
        plan_path="docs/superpowers/plans/plan.md",
        plan_sha="2" * 40,
        expected_base_sha="b" * 40,
    )

    assert result["ok"] is True
    assert seen == [("b" * 40, "1" * 40), ("1" * 40, "2" * 40)]


def test_mission_prepare_rejects_unrelated_planning_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_common(monkeypatch)
    monkeypatch.setattr(
        commands.repo_tools,
        "commit_is_ancestor",
        lambda left, right: not (left == "1" * 40 and right == "2" * 40),
    )

    result = commands.mission_prepare(
        _manifest(),
        design_path="docs/superpowers/specs/design.md",
        design_sha="1" * 40,
        plan_path="docs/superpowers/plans/plan.md",
        plan_sha="2" * 40,
        expected_base_sha="b" * 40,
    )

    assert result["ok"] is False
    assert result["error_code"] == "prepare_failed"
    assert "lineage" in result["error"].lower()
