from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from scripts.prompt_experiment import PromptExperimentError, compile_receipt


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()

@pytest.fixture()
def prompt_repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    prompt = repo / "prompt.md"
    prompt.write_text("Be concise.\nCite evidence.\n", encoding="utf-8")
    _git(repo, "add", "prompt.md")
    _git(repo, "commit", "-m", "baseline")
    baseline = _git(repo, "rev-parse", "HEAD")
    prompt.write_text(
        "Be concise.\nCite evidence.\nState uncertainty explicitly.\n", encoding="utf-8"
    )
    _git(repo, "commit", "-am", "candidate")
    return repo, baseline, _git(repo, "rev-parse", "HEAD")

def _receipt(repo: Path, baseline: str, candidate: str):
    return compile_receipt(
        repo=repo,
        path="prompt.md",
        baseline_ref=baseline,
        candidate_ref=candidate,
        baseline_scores={"a": 0.5, "b": 0.7},
        candidate_scores={"a": 0.8, "b": 0.9},
        minimum_lift=0.1,
        context={"model": "m", "workspace": "w", "scorer": "s"},
    )

def test_receipt_binds_exact_git_content_and_rollback(
    prompt_repo: tuple[Path, str, str],
) -> None:
    repo, baseline, candidate = prompt_repo
    receipt = _receipt(repo, baseline, candidate)
    baseline_bytes = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{baseline}:prompt.md"]
    )
    candidate_bytes = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{candidate}:prompt.md"]
    )
    assert receipt["baseline"]["commit_sha"] == baseline
    assert receipt["candidate"]["commit_sha"] == candidate
    assert receipt["baseline"]["content_sha256"] == hashlib.sha256(baseline_bytes).hexdigest()
    assert receipt["candidate"]["content_sha256"] == hashlib.sha256(candidate_bytes).hexdigest()
    assert receipt["rollback"] == {"commit_sha": baseline, "prompt_path": "prompt.md"}
    assert receipt["activation"]["authorized"] is False
    assert "State uncertainty explicitly." in receipt["diff"]
    assert receipt["promotion_evidence"] == "supported"
    assert receipt["evaluation"]["pair_count"] == 2

def test_dirty_worktree_cannot_change_ref_bound_receipt(
    prompt_repo: tuple[Path, str, str],
) -> None:
    repo, baseline, candidate = prompt_repo
    before = _receipt(repo, baseline, candidate)
    (repo / "prompt.md").write_text("UNCOMMITTED DRIFT\n", encoding="utf-8")
    after = _receipt(repo, baseline, candidate)
    assert after == before
    assert "UNCOMMITTED DRIFT" not in after["diff"]

def test_unmatched_tasks_fail_closed(prompt_repo: tuple[Path, str, str]) -> None:
    repo, baseline, candidate = prompt_repo
    with pytest.raises(PromptExperimentError, match="identical task keys"):
        compile_receipt(
            repo=repo,
            path="prompt.md",
            baseline_ref=baseline,
            candidate_ref=candidate,
            baseline_scores={"a": 0.5},
            candidate_scores={"b": 0.8},
            minimum_lift=0.0,
            context={"model": "m", "workspace": "w", "scorer": "s"},
        )

def test_missing_prompt_at_ref_fails_loud(prompt_repo: tuple[Path, str, str]) -> None:
    repo, baseline, candidate = prompt_repo
    with pytest.raises(PromptExperimentError, match="git show"):
        compile_receipt(
            repo=repo,
            path="missing.md",
            baseline_ref=baseline,
            candidate_ref=candidate,
            baseline_scores={"a": 0.5},
            candidate_scores={"a": 0.8},
            minimum_lift=0.0,
            context={"model": "m", "workspace": "w", "scorer": "s"},
        )

def test_identical_content_is_not_an_experiment(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    (repo / "prompt.md").write_text("same\n", encoding="utf-8")
    _git(repo, "add", "prompt.md")
    _git(repo, "commit", "-m", "one")
    baseline = _git(repo, "rev-parse", "HEAD")
    (repo / "other.txt").write_text("change\n", encoding="utf-8")
    _git(repo, "add", "other.txt")
    _git(repo, "commit", "-m", "two")
    with pytest.raises(PromptExperimentError, match="identical"):
        _receipt(repo, baseline, _git(repo, "rev-parse", "HEAD"))

@pytest.mark.parametrize("path", ["/tmp/prompt.md", "../prompt.md", ".git/config"])
def test_path_must_stay_inside_tracked_tree(
    prompt_repo: tuple[Path, str, str], path: str
) -> None:
    repo, baseline, candidate = prompt_repo
    with pytest.raises(PromptExperimentError, match="path"):
        compile_receipt(
            repo=repo,
            path=path,
            baseline_ref=baseline,
            candidate_ref=candidate,
            baseline_scores={"a": 0.5},
            candidate_scores={"a": 0.8},
            minimum_lift=0.0,
            context={"model": "m", "workspace": "w", "scorer": "s"},
        )

def test_non_improving_candidate_is_explicitly_not_supported(
    prompt_repo: tuple[Path, str, str],
) -> None:
    repo, baseline, candidate = prompt_repo
    receipt = compile_receipt(
        repo=repo,
        path="prompt.md",
        baseline_ref=baseline,
        candidate_ref=candidate,
        baseline_scores={"a": 0.9},
        candidate_scores={"a": 0.8},
        minimum_lift=0.0,
        context={"model": "m", "workspace": "w", "scorer": "s"},
    )
    assert receipt["evaluation"]["improved"] is False
    assert receipt["promotion_evidence"] == "not_supported"
    assert receipt["activation"]["authorized"] is False
