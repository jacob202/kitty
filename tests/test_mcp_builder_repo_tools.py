from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mcp.builder import repo_tools


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "Kitty Test")
    _git(tmp_path, "config", "user.email", "kitty-test@example.invalid")

    (tmp_path / "gateway").mkdir()
    (tmp_path / "gateway" / "app.py").write_text(
        "alpha = 1\nneedle = 'present'\nomega = 3\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# Kitty test\n", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "tracked-secret.txt").write_text("do not expose\n", encoding="utf-8")
    (tmp_path / ".env.test").write_text("SECRET=value\n", encoding="utf-8")

    _git(tmp_path, "add", "README.md", "gateway/app.py", "data/tracked-secret.txt", ".env.test")
    _git(tmp_path, "commit", "-m", "fixture")
    monkeypatch.setenv("KITTY_REPO_ROOT", str(tmp_path))
    return tmp_path


def test_read_tracked_file_reads_from_git_not_arbitrary_filesystem(repo: Path) -> None:
    (repo / "untracked.txt").write_text("not allowed\n", encoding="utf-8")

    result = repo_tools.read_tracked_file("gateway/app.py", start_line=2, end_line=2)

    assert result["path"] == "gateway/app.py"
    assert result["ref"] == "HEAD"
    assert result["content"] == "needle = 'present'"
    with pytest.raises(repo_tools.RepoAccessError, match="tracked"):
        repo_tools.read_tracked_file("untracked.txt")


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "../outside.txt",
        ".env.test",
        "data/tracked-secret.txt",
        "logs/app.log",
        ".git/config",
        "node_modules/pkg/index.js",
    ],
)
def test_read_tracked_file_rejects_sensitive_or_outside_paths(repo: Path, path: str) -> None:
    with pytest.raises(repo_tools.RepoAccessError):
        repo_tools.read_tracked_file(path)


def test_search_tracked_repo_is_literal_bounded_and_path_scoped(repo: Path) -> None:
    result = repo_tools.search_tracked_repo("needle", path="gateway", limit=5)

    assert result["query"] == "needle"
    assert result["count"] == 1
    assert result["matches"][0]["path"] == "gateway/app.py"
    assert result["matches"][0]["line"] == 2
    assert result["matches"][0]["text"] == "needle = 'present'"


def test_search_rejects_blank_or_sensitive_scope(repo: Path) -> None:
    with pytest.raises(repo_tools.RepoAccessError, match="blank"):
        repo_tools.search_tracked_repo("   ")
    with pytest.raises(repo_tools.RepoAccessError):
        repo_tools.search_tracked_repo("SECRET", path=".env.test")


def test_write_design_uses_isolated_branch_and_leaves_checkout_unchanged(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    original_branch = _git(repo, "branch", "--show-current")
    original_status = _git(repo, "status", "--porcelain")

    result = repo_tools.write_planning_artifact(
        kind="design",
        slug="mcp-proof",
        markdown="# Design\n\nDurable.\n",
        expected_base_sha=base,
    )

    assert result["artifact_path"].endswith("-mcp-proof-design.md")
    assert result["base_sha"] == base
    assert len(result["commit_sha"]) == 40
    assert _git(repo, "branch", "--show-current") == original_branch
    assert _git(repo, "status", "--porcelain") == original_status
    stored = _git(repo, "show", f"{result['commit_sha']}:{result['artifact_path']}")
    assert stored == "# Design\n\nDurable."


def test_write_planning_artifact_refuses_stale_base(repo: Path) -> None:
    with pytest.raises(repo_tools.StaleRepositoryError, match="expected base"):
        repo_tools.write_planning_artifact(
            kind="design",
            slug="stale",
            markdown="# stale\n",
            expected_base_sha="0" * 40,
        )


def test_plan_must_be_bound_to_existing_design_commit(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    design = repo_tools.write_planning_artifact(
        kind="design",
        slug="bound",
        markdown="# Design\n",
        expected_base_sha=base,
    )

    plan = repo_tools.write_planning_artifact(
        kind="plan",
        slug="bound",
        markdown=f"# Plan\n\nDesign commit: `{design['commit_sha']}`\n",
        expected_base_sha=design["commit_sha"],
        expected_dependency_sha=design["commit_sha"],
    )

    assert plan["dependency_sha"] == design["commit_sha"]
    assert _git(repo, "merge-base", "--is-ancestor", design["commit_sha"], plan["commit_sha"]) == ""


def test_plan_rejects_missing_or_unrelated_dependency(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(repo_tools.PlanningArtifactError, match="dependency"):
        repo_tools.write_planning_artifact(
            kind="plan",
            slug="missing-dependency",
            markdown="# Plan\n",
            expected_base_sha=base,
        )
    with pytest.raises(repo_tools.PlanningArtifactError, match="dependency"):
        repo_tools.write_planning_artifact(
            kind="plan",
            slug="bad-dependency",
            markdown="# Plan\n",
            expected_base_sha=base,
            expected_dependency_sha="f" * 40,
        )
