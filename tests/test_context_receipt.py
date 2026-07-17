"""Contract tests for deterministic repository context and freshness checks."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gateway import builder_initiative as bi
from gateway import builder_queue as bq
from gateway.context_receipt import build_context_receipt, run_continuity_checks

NOW = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _mission_metadata(base_sha: str, *, status: str = "running") -> str:
    payload = {
        "schema_version": 1,
        "mission_id": "TEST-001",
        "status": status,
        "approved_at": "2026-07-17T10:00:00Z",
        "approved_by": "Jacob",
        "base_sha": base_sha,
        "authority": "docs/ACTIVE_MISSION.md",
    }
    return "# Active Mission\n\n<!-- kitty-mission\n" + json.dumps(payload, indent=2) + "\n-->\n"


def _checkpoint_metadata(
    head_sha: str,
    *,
    marker: str,
    status: str,
    branch: str = "main",
    worktree: str = ".",
    next_action: str = "implement the context receipt",
    completed_items: list[str] | None = None,
    pull_request: dict | None = None,
    updated_at: str = "2026-07-17T11:00:00Z",
) -> str:
    payload = {
        "schema_version": 1,
        "updated_at": updated_at,
        "head_sha": head_sha,
        "branch": branch,
        "worktree": worktree,
        "status": status,
        "completed_items": completed_items or ["audit repository truth"],
        "blockers": [],
        "next_action": next_action,
        "invalidation_conditions": [
            "HEAD changes outside a checkpoint commit",
            "branch or worktree changes",
            "active mission changes",
            "pull request state changes",
        ],
        "active_mission": "docs/ACTIVE_MISSION.md",
        "pull_request": pull_request,
    }
    return f"# Checkpoint\n\n<!-- {marker}\n" + json.dumps(payload, indent=2) + "\n-->\n"


def _write_checkpoint_pair(repo: Path, head_sha: str, **overrides) -> None:
    _write(
        repo / ".claude/STATE.md",
        _checkpoint_metadata(head_sha, marker="kitty-state", status="in_progress", **overrides),
    )
    _write(
        repo / ".claude/HANDOFF.md",
        _checkpoint_metadata(head_sha, marker="kitty-handoff", status="valid", **overrides),
    )


def _authority_map() -> str:
    rows = [
        ("product_purpose", "docs/NORTH_STAR.md"),
        ("engineering_doctrine", "AGENTS.md"),
        ("architecture", "docs/ARCHITECTURE.md"),
        ("decisions", "docs/DECISIONS.md"),
        ("live_status", "docs/PROJECT_STATUS.md"),
        ("active_mission", "docs/ACTIVE_MISSION.md"),
        ("session_checkpoint", ".claude/STATE.md"),
        ("continuation", ".claude/HANDOFF.md"),
        ("builder_state", "data/kittybuilder/builder_queue.db"),
        ("builder_interfaces", "docs/KITTYBUILDER_QUICKSTART.md"),
        ("historical_records", "Git history"),
        ("historical_docs", "docs/archive/README.md"),
    ]
    table = "\n".join(f"| `{concern}` | `{authority}` | owns | does not own |" for concern, authority in rows)
    return (
        "# Authority Map\n\n"
        "| Concern ID | Authority | Owns | Does not own |\n"
        "|---|---|---|---|\n"
        f"{table}\n"
    )


def _start_here() -> str:
    paths = [
        "docs/AUTHORITY_MAP.md",
        "docs/NORTH_STAR.md",
        "AGENTS.md",
        "docs/ARCHITECTURE.md",
        "docs/DECISIONS.md",
        "docs/PROJECT_STATUS.md",
        "docs/ACTIVE_MISSION.md",
        ".claude/STATE.md",
        ".claude/HANDOFF.md",
    ]
    links = "\n".join(f"{index}. [{path}]({path})" for index, path in enumerate(paths, 1))
    return (
        "# Start Here\n\n<!-- kitty-reading-order:start -->\n"
        f"{links}\n"
        "<!-- kitty-reading-order:end -->\n"
    )


def _repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "kitty"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Context Receipt Tests")

    _write(repo / "AGENTS.md", "# Engineering doctrine\n")
    _write(repo / "CLAUDE.md", "# Claude bootloader\n")
    _write(repo / "START_HERE.md", _start_here())
    _write(repo / "docs/AUTHORITY_MAP.md", _authority_map())
    _write(repo / "docs/NORTH_STAR.md", "# Purpose\n")
    _write(repo / "docs/ARCHITECTURE.md", "# Architecture\n")
    _write(repo / "docs/DECISIONS.md", "# Decisions\n")
    _write(repo / "docs/PROJECT_STATUS.md", "# Project Status\n")
    _write(repo / "docs/KITTYBUILDER_QUICKSTART.md", "# Builder interfaces\n")
    _write(repo / "docs/archive/README.md", "# Archive\n")
    _write(repo / "docs/ACTIVE_MISSION.md", _mission_metadata("0" * 40))
    _write_checkpoint_pair(repo, "0" * 40)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "test: initialize continuity repository")
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/main", head)
    _write(repo / "docs/ACTIVE_MISSION.md", _mission_metadata(head))
    _write_checkpoint_pair(repo, head)
    return repo, head


def _levels(repo: Path, **kwargs) -> dict[str, str]:
    checks = run_continuity_checks(repo, expected_canonical=repo, now=NOW, **kwargs)
    return {check.name: check.level for check in checks}


def test_receipt_is_deterministic_and_reports_explicit_unknowns(tmp_path: Path):
    repo, head = _repo(tmp_path)

    first = build_context_receipt(repo, expected_canonical=repo, now=NOW)
    second = build_context_receipt(repo, expected_canonical=repo, now=NOW)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["ok"] is True
    assert first["git"]["head"] == head
    assert first["git"]["origin_main"]["ahead"] == 0
    assert first["git"]["origin_main"]["behind"] == 0
    assert first["builder"]["state"] == "unavailable"
    assert {item["field"] for item in first["unknowns"]} == {
        "builder",
        "git.origin_main.remote_freshness",
    }


def test_receipt_reads_builder_through_read_only_summary(tmp_path: Path):
    repo, _head = _repo(tmp_path)
    db_path = repo / "data/kittybuilder/builder_queue.db"
    bq.init_db(db_path)
    bi.init_db(db_path)

    receipt = build_context_receipt(repo, expected_canonical=repo, now=NOW)

    assert receipt["builder"]["state"] == "available", receipt["builder"]
    assert receipt["builder"]["queue"]["total"] == 0
    assert receipt["builder"]["initiatives"] == []


def test_mismatched_head_fails_when_new_commit_changes_non_checkpoint_file(tmp_path: Path):
    repo, _head = _repo(tmp_path)
    _write(repo / "AGENTS.md", "# changed doctrine\n")
    _git(repo, "add", "AGENTS.md")
    _git(repo, "commit", "-m", "test: advance implementation")

    levels = _levels(repo)

    assert levels["state:head"] == "FAIL"
    assert levels["handoff:head"] == "FAIL"


def test_checkpoint_only_commit_is_a_valid_self_referential_checkpoint(tmp_path: Path):
    repo, _head = _repo(tmp_path)
    _git(repo, "add", ".claude/STATE.md", ".claude/HANDOFF.md")
    _git(repo, "commit", "-m", "docs(state): record current checkpoint")

    levels = _levels(repo)

    assert levels["state:head"] == "PASS"
    assert levels["handoff:head"] == "PASS"


def test_missing_origin_main_is_explicitly_unknown_and_fails_freshness(tmp_path: Path):
    repo, _head = _repo(tmp_path)
    _git(repo, "update-ref", "-d", "refs/remotes/origin/main")

    receipt = build_context_receipt(repo, expected_canonical=repo, now=NOW)

    assert receipt["ok"] is False
    assert receipt["git"]["origin_main"]["state"] == "unknown"
    assert "git.origin_main" in {item["field"] for item in receipt["unknowns"]}


def test_stale_pr_claim_fails_against_live_github_state(tmp_path: Path):
    repo, head = _repo(tmp_path)
    _write_checkpoint_pair(
        repo,
        head,
        pull_request={"number": 183, "state": "OPEN", "head_sha": head},
    )

    levels = _levels(
        repo,
        github_lookup=lambda _number: {"state": "MERGED", "headRefOid": head},
    )

    assert levels["state:pull_request"] == "FAIL"
    assert levels["handoff:pull_request"] == "FAIL"


def test_invalid_branch_and_worktree_fail(tmp_path: Path):
    repo, head = _repo(tmp_path)
    _write_checkpoint_pair(repo, head, branch="old-branch", worktree="/tmp/old-kitty")

    levels = _levels(repo)

    assert levels["state:branch"] == "FAIL"
    assert levels["state:worktree"] == "FAIL"
    assert levels["handoff:branch"] == "FAIL"
    assert levels["handoff:worktree"] == "FAIL"


def test_broken_front_door_link_fails(tmp_path: Path):
    repo, _head = _repo(tmp_path)
    _write(
        repo / "START_HERE.md",
        _start_here().replace("docs/NORTH_STAR.md", "docs/MISSING.md"),
    )

    levels = _levels(repo)

    assert levels["docs:front_door_links"] == "FAIL"


def test_duplicate_authority_declaration_fails(tmp_path: Path):
    repo, _head = _repo(tmp_path)
    _write(repo / "CLAUDE.md", "# Claude\n\n## Current Sources Of Truth\n")

    levels = _levels(repo)

    assert levels["docs:duplicate_authority_claims"] == "FAIL"


def test_duplicate_authority_map_row_fails(tmp_path: Path):
    repo, _head = _repo(tmp_path)
    path = repo / "docs/AUTHORITY_MAP.md"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "| `product_purpose` | `docs/OTHER.md` | duplicate | duplicate |\n",
        encoding="utf-8",
    )

    levels = _levels(repo)

    assert levels["docs:authority_map"] == "FAIL"


def test_outdated_builder_description_fails(tmp_path: Path):
    repo, _head = _repo(tmp_path)
    _write(repo / "AGENTS.md", "# Builder\n\nLayer 1A — coordination only\n")

    levels = _levels(repo)

    assert levels["docs:builder_descriptions"] == "FAIL"


def test_completed_action_cannot_remain_next(tmp_path: Path):
    repo, head = _repo(tmp_path)
    action = "implement the context receipt"
    _write_checkpoint_pair(repo, head, next_action=action, completed_items=[action])

    levels = _levels(repo)

    assert levels["state:active_action"] == "FAIL"
    assert levels["handoff:active_action"] == "FAIL"


def test_completed_mission_cannot_keep_active_session(tmp_path: Path):
    repo, head = _repo(tmp_path)
    _write(repo / "docs/ACTIVE_MISSION.md", _mission_metadata(head, status="succeeded"))

    levels = _levels(repo)

    assert levels["mission:active_state"] == "FAIL"


def test_checkpoint_age_limit_is_enforced(tmp_path: Path):
    repo, _head = _repo(tmp_path)

    levels = _levels(repo, max_age=timedelta(minutes=30))

    assert levels["state:age"] == "FAIL"
    assert levels["handoff:age"] == "FAIL"
