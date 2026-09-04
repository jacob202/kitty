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


def _install_session_gated_hook(repo: Path) -> None:
    """Mirror `.githooks/pre-commit`'s real contract without the full CLI: any
    commit in a worktree lacking a `kitty-agent-session` file in its own
    git-dir is refused. Every real planning-artifact commit runs through a
    temporary ``git worktree add`` sandbox with its own private git-dir, so
    this reproduces the exact production interaction (KX-COORD-01's
    per-worktree session-claim hook vs. the ephemeral MCP planning worktree)."""
    hooks_dir = repo / ".githooks"
    hooks_dir.mkdir(exist_ok=True)
    hook = hooks_dir / "pre-commit"
    hook.write_text(
        "#!/usr/bin/env sh\n"
        "set -eu\n"
        'git_dir="$(git rev-parse --path-format=absolute --git-dir)"\n'
        'if [ ! -f "$git_dir/kitty-agent-session" ]; then\n'
        '  echo "ERROR: no Kitty agent session is established for this worktree; run kitty agent claim first" >&2\n'
        "  exit 1\n"
        "fi\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    # write_planning_artifact checks out the ephemeral worktree from a real
    # base commit, so the hook must be a tracked file *in* that commit --
    # not just present in the calling worktree's untracked working copy --
    # or the temp worktree's checkout simply won't have it to run. This setup
    # commit predates `core.hooksPath` being turned on, so it needs no
    # bypass; every commit `write_planning_artifact` makes afterward is
    # exactly what is under test.
    _git(repo, "add", ".githooks/pre-commit")
    _git(repo, "commit", "-m", "test: install session-gated pre-commit hook")
    _git(repo, "config", "core.hooksPath", ".githooks")


def test_write_planning_artifact_inherits_caller_session_into_temp_worktree(
    repo: Path,
) -> None:
    _install_session_gated_hook(repo)
    calling_git_dir = _git(repo, "rev-parse", "--path-format=absolute", "--git-dir")
    (Path(calling_git_dir) / "kitty-agent-session").write_text(
        "test-session-inherits\n", encoding="utf-8"
    )
    base = _git(repo, "rev-parse", "HEAD")

    result = repo_tools.write_planning_artifact(
        kind="design",
        slug="hook-inherit-proof",
        markdown="# Design\n\nHooked.\n",
        expected_base_sha=base,
    )

    assert len(result["commit_sha"]) == 40


def test_write_planning_artifact_still_fails_closed_without_a_session(
    repo: Path,
) -> None:
    _install_session_gated_hook(repo)
    base = _git(repo, "rev-parse", "HEAD")

    with pytest.raises(repo_tools.GitCommandError, match="no Kitty agent session"):
        repo_tools.write_planning_artifact(
            kind="design",
            slug="hook-refuse-proof",
            markdown="# Design\n\nUnclaimed.\n",
            expected_base_sha=base,
        )


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
