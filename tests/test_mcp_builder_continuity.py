from __future__ import annotations

import json

import pytest

from mcp.builder import context


def test_resume_context_reconstructs_work_without_conversation_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refs = {
        "design_path": "docs/superpowers/specs/2026-08-09-feature-design.md",
        "design_sha": "d" * 40,
        "plan_path": "docs/superpowers/plans/2026-08-09-feature.md",
        "plan_sha": "p" * 40,
        "base_sha": "b" * 40,
    }
    initiative = {
        "id": "mission-1",
        "manifest_sha256": "m" * 64,
        "manifest": {
            "manifest_version": 1,
            "initiative_id": "mission-1",
            "title": "Feature mission",
            "description": "Approved feature mission\n"
            + context.MCP_ARTIFACT_MARKER
            + json.dumps(refs, sort_keys=True),
            "packets": [
                {
                    "id": "packet-1",
                    "title": "Build it",
                    "objective": "Make the real feature work",
                    "depends_on": [],
                    "acceptance_criteria": ["tests pass"],
                    "allowed_paths": ["gateway/"],
                }
            ],
        },
    }
    status = {
        "ok": True,
        "operation": "work_status",
        "state": "blocked",
        "work": {
            "initiative_id": "mission-1",
            "title": "Feature mission",
            "state": "blocked",
            "next_packet": "packet-1",
            "packets": [
                {
                    "initiative_id": "mission-1",
                    "packet_id": "packet-1",
                    "objective": "Make the real feature work",
                    "task_id": "kb_1",
                    "task_state": "blocked",
                    "blocked_reason": "provider exhausted",
                    "base_sha": "b" * 40,
                    "attempt_history": [
                        {
                            "id": 4,
                            "validation": {
                                "status": "passed",
                                "summary": "5 validation commands passed.",
                            },
                            "review": {
                                "verdict": "approved",
                                "summary": "Independent review approved.",
                            },
                        }
                    ],
                    "publication": {
                        "pr_number": 451,
                        "pr_url": "https://github.com/jacob202/kitty/pull/451",
                        "checks_state": "success",
                        "review_state": "approved",
                        "head_sha": "h" * 40,
                        "merged": False,
                    },
                    "projection": {"next_action": "recover"},
                }
            ],
        },
    }
    kitty = {
        "ok": True,
        "operation": "kitty_context",
        "context": {
            "git": {"head": "c" * 40, "branch": "main"},
            "continuity": {"active_mission": {"mission_id": "KPROOF-001"}},
            "evidence": {"receipt_source": "gateway.context_receipt"},
            "unknowns": [],
        },
    }

    monkeypatch.setattr(context, "kitty_context", lambda: kitty)
    monkeypatch.setattr(context, "work_status", lambda **_: status)
    monkeypatch.setattr(context, "get_initiative", lambda *_args, **_kwargs: initiative)

    resumed = context.resume_context(mission_id="mission-1")

    assert resumed["ok"] is True
    assert resumed["objective"] == "Make the real feature work"
    assert resumed["artifacts"]["design"] == {
        "path": refs["design_path"],
        "sha": refs["design_sha"],
    }
    assert resumed["artifacts"]["plan"] == {
        "path": refs["plan_path"],
        "sha": refs["plan_sha"],
    }
    assert resumed["repository"]["base_sha"] == refs["base_sha"]
    assert resumed["repository"]["current_sha"] == "c" * 40
    assert resumed["execution_owner"] == "builder"
    assert resumed["current_work"]["task_id"] == "kb_1"
    assert resumed["evidence"]["validation"]["status"] == "passed"
    assert resumed["evidence"]["review"]["verdict"] == "approved"
    assert resumed["pr"]["number"] == 451
    assert resumed["blocker"] == "provider exhausted"
    assert resumed["next_action"] == "recover"
    assert isinstance(resumed["next_action"], str)
    assert resumed["sources"]["builder"] == "gateway.builder_status.build_status_snapshot"
    assert "conversation" not in resumed


def test_resume_context_reports_missing_artifact_linkage_as_unknown_not_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        context,
        "kitty_context",
        lambda: {
            "ok": True,
            "operation": "kitty_context",
            "context": {"git": {"head": "c" * 40}, "unknowns": []},
        },
    )
    monkeypatch.setattr(
        context,
        "work_status",
        lambda **_: {
            "ok": True,
            "operation": "work_status",
            "state": "queued",
            "work": {
                "initiative_id": "mission-1",
                "state": "queued",
                "packets": [
                    {
                        "packet_id": "p1",
                        "objective": "Do work",
                        "task_id": "kb_1",
                        "task_state": "queued",
                        "attempt_history": [],
                        "publication": None,
                        "projection": {"next_action": "claim"},
                    }
                ],
            },
        },
    )
    monkeypatch.setattr(
        context,
        "get_initiative",
        lambda *_args, **_kwargs: {
            "id": "mission-1",
            "manifest": {
                "initiative_id": "mission-1",
                "title": "No linkage",
                "description": "ordinary initiative",
                "packets": [],
            },
        },
    )

    resumed = context.resume_context(mission_id="mission-1")

    assert resumed["ok"] is True
    assert resumed["artifacts"]["design"] is None
    assert resumed["artifacts"]["plan"] is None
    fields = {item["field"] for item in resumed["unknowns"]}
    assert "artifacts.design" in fields
    assert "artifacts.plan" in fields
