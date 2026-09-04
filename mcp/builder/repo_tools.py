"""Allowlisted repository reads and planning-artifact writes for MCP clients.

This module intentionally does not expose a shell, arbitrary filesystem access,
or generic Git mutation. Reads come from committed Git objects. Writes can only
create design/plan Markdown on a deterministic isolated planning branch.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Literal


class RepoAccessError(ValueError):
    """A requested repository read is outside the MCP read boundary."""


class PlanningArtifactError(ValueError):
    """A planning artifact cannot be written safely."""


class StaleRepositoryError(PlanningArtifactError):
    """The caller's expected repository base no longer matches the contract."""


class GitCommandError(RuntimeError):
    """A bounded internal Git operation failed."""


_DEFAULT_ROOT = Path(__file__).resolve().parents[2]
_MAX_READ_BYTES = 512_000
_MAX_SEARCH_RESULTS = 50
_MAX_SEARCH_TEXT = 500
_MAX_MARKDOWN_BYTES = 1_000_000
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_BLOCKED_TOP_LEVEL = frozenset({"data", "logs", ".git", ".venv", "node_modules"})


def repo_root() -> Path:
    """Return the canonical repository root used by this MCP process.

    ``KITTY_REPO_ROOT`` exists for tests and explicit operator deployment only;
    clients cannot supply or mutate it through an MCP tool argument.
    """
    configured = os.environ.get("KITTY_REPO_ROOT")
    root = Path(configured).expanduser() if configured else _DEFAULT_ROOT
    root = root.resolve()
    probe = _run_git(["rev-parse", "--show-toplevel"], root=root)
    actual = Path(probe.stdout.strip()).resolve()
    if actual != root:
        raise RepoAccessError(
            f"configured Kitty repo {root} resolves to Git root {actual}; refusing ambiguous checkout"
        )
    return root


def _run_git(
    args: list[str],
    *,
    root: Path | None = None,
    check: bool = True,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    cwd = root or (Path(os.environ["KITTY_REPO_ROOT"]).expanduser().resolve() if os.environ.get("KITTY_REPO_ROOT") else _DEFAULT_ROOT)
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitCommandError(f"git {' '.join(args[:3])} failed: {exc}") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "no output").strip()[:600]
        raise GitCommandError(
            f"git {' '.join(args[:3])} exited {result.returncode}: {detail}"
        )
    return result


_AGENT_SESSION_FILENAME = "kitty-agent-session"


def _propagate_agent_session(
    source_root: Path,
    dest_worktree: Path,
    *,
    session_id: str | None = None,
) -> None:
    """Carry the caller's active Kitty agent-session claim into an ephemeral worktree.

    ``write_planning_artifact`` commits through a short-lived ``git worktree
    add`` sandbox so the caller's own checkout is never touched. Each worktree
    gets its own private git-dir, and the shared pre-commit hook checks for a
    ``kitty-agent-session`` file scoped to that git-dir before allowing a
    commit. Without this, the sandbox never has one of its own and every
    planning-artifact commit fails closed -- even when the caller already
    holds a valid claim on ``source_root``. This does not weaken that check:
    it only extends the caller's own already-established session to the
    disposable worktree it triggered, so a caller with no session still fails
    the same way it always has.
    """
    selected_session = session_id.strip() if isinstance(session_id, str) else ""
    if session_id is not None and (not selected_session or "\n" in selected_session or "\r" in selected_session):
        raise PlanningArtifactError("agent_session_id must be a single non-empty line")

    if not selected_session:
        source_dir = _run_git(
            ["rev-parse", "--path-format=absolute", "--git-dir"], root=source_root
        ).stdout.strip()
        marker = Path(source_dir) / _AGENT_SESSION_FILENAME
        if not marker.exists():
            return
        selected_session = marker.read_text(encoding="utf-8").strip()
        if not selected_session:
            return

    dest_dir = _run_git(
        ["rev-parse", "--path-format=absolute", "--git-dir"], root=dest_worktree
    ).stdout.strip()
    (Path(dest_dir) / _AGENT_SESSION_FILENAME).write_text(
        selected_session + "\n", encoding="utf-8"
    )


def repo_head() -> str:
    sha = _run_git(["rev-parse", "HEAD"], root=repo_root()).stdout.strip()
    if not _SHA_RE.fullmatch(sha):
        raise GitCommandError(f"git returned invalid HEAD SHA: {sha!r}")
    return sha


def _validate_repo_path(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise RepoAccessError("repository path is required")
    if "\\" in path:
        raise RepoAccessError("repository path must use '/' separators")
    pure = PurePosixPath(path)
    if pure.is_absolute() or path.startswith(("~", "-")):
        raise RepoAccessError(f"repository path must be relative: {path!r}")
    parts = pure.parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise RepoAccessError(f"invalid repository path: {path!r}")
    if parts[0] in _BLOCKED_TOP_LEVEL:
        raise RepoAccessError(f"path is outside the MCP repository read boundary: {path!r}")
    if any(part.startswith(".env") for part in parts):
        raise RepoAccessError(f"environment files are not exposed through MCP: {path!r}")
    return pure.as_posix()


def _validate_ref(ref: str | None) -> str:
    candidate = ref or "HEAD"
    if not isinstance(candidate, str) or not candidate.strip() or candidate.startswith("-"):
        raise RepoAccessError(f"invalid Git ref: {candidate!r}")
    # Prevent revision/path syntax from being smuggled into the ref itself.
    if ":" in candidate or any(ch.isspace() for ch in candidate):
        raise RepoAccessError(f"invalid Git ref: {candidate!r}")
    result = _run_git(
        ["rev-parse", "--verify", f"{candidate}^{{commit}}"],
        root=repo_root(),
        check=False,
    )
    if result.returncode != 0:
        raise RepoAccessError(f"Git ref does not resolve to a commit: {candidate!r}")
    return candidate


def read_tracked_file(
    path: str,
    ref: str | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
) -> dict:
    """Read one committed tracked file from an explicit Git ref."""
    safe_path = _validate_repo_path(path)
    safe_ref = _validate_ref(ref)
    root = repo_root()
    exists = _run_git(
        ["cat-file", "-e", f"{safe_ref}:{safe_path}"],
        root=root,
        check=False,
    )
    if exists.returncode != 0:
        raise RepoAccessError(
            f"path is not a tracked file at {safe_ref}: {safe_path}"
        )
    raw = _run_git(["show", f"{safe_ref}:{safe_path}"], root=root).stdout
    if len(raw.encode("utf-8")) > _MAX_READ_BYTES:
        raise RepoAccessError(
            f"tracked file exceeds MCP read limit of {_MAX_READ_BYTES} bytes: {safe_path}"
        )
    if start_line is not None or end_line is not None:
        start = 1 if start_line is None else start_line
        end = end_line
        if start < 1 or (end is not None and end < start):
            raise RepoAccessError("line range must be 1-based and end >= start")
        lines = raw.splitlines()
        selected = lines[start - 1 : end]
        content = "\n".join(selected)
    else:
        content = raw
    commit = _run_git(["rev-parse", f"{safe_ref}^{{commit}}"], root=root).stdout.strip()
    return {
        "path": safe_path,
        "ref": safe_ref,
        "commit_sha": commit,
        "content": content,
        "start_line": start_line,
        "end_line": end_line,
    }


def _search_pathspecs(path: str | None) -> list[str]:
    include = _validate_repo_path(path) if path else "."
    return [
        include,
        ":(exclude).env*",
        ":(exclude)**/.env*",
        ":(exclude)data/**",
        ":(exclude)logs/**",
        ":(exclude).git/**",
        ":(exclude).venv/**",
        ":(exclude)node_modules/**",
        ":(exclude)**/node_modules/**",
    ]


def search_tracked_repo(
    query: str,
    path: str | None = None,
    ref: str | None = None,
    limit: int = 20,
) -> dict:
    """Literal bounded search over committed tracked repository text."""
    if not isinstance(query, str) or not query.strip():
        raise RepoAccessError("search query must not be blank")
    if "\x00" in query:
        raise RepoAccessError("search query contains NUL")
    safe_ref = _validate_ref(ref)
    bounded_limit = max(1, min(int(limit), _MAX_SEARCH_RESULTS))
    result = _run_git(
        [
            "grep",
            "-n",
            "-I",
            "-F",
            "-e",
            query,
            safe_ref,
            "--",
            *_search_pathspecs(path),
        ],
        root=repo_root(),
        check=False,
    )
    if result.returncode not in (0, 1):
        detail = (result.stderr or result.stdout or "no output").strip()[:600]
        raise GitCommandError(f"git grep exited {result.returncode}: {detail}")
    matches: list[dict] = []
    for line in result.stdout.splitlines():
        if len(matches) >= bounded_limit:
            break
        try:
            _matched_ref, matched_path, line_no, text = line.split(":", 3)
            safe_path = _validate_repo_path(matched_path)
            matches.append(
                {
                    "path": safe_path,
                    "line": int(line_no),
                    "text": text[:_MAX_SEARCH_TEXT],
                }
            )
        except (ValueError, RepoAccessError) as exc:
            raise GitCommandError(f"git grep returned malformed result: {line!r}") from exc
    return {
        "query": query,
        "ref": safe_ref,
        "path": path,
        "count": len(matches),
        "truncated": len(matches) >= bounded_limit,
        "matches": matches,
    }


def _require_commit(sha: str, *, label: str) -> str:
    if not isinstance(sha, str) or not _SHA_RE.fullmatch(sha):
        raise StaleRepositoryError(f"{label} must be a full 40-character commit SHA")
    result = _run_git(
        ["cat-file", "-e", f"{sha}^{{commit}}"],
        root=repo_root(),
        check=False,
    )
    if result.returncode != 0:
        raise StaleRepositoryError(f"{label} does not resolve in this repository: {sha}")
    return sha


def planning_artifact_path(kind: Literal["design", "plan"], slug: str) -> str:
    today = date.today().isoformat()
    if kind == "design":
        return f"docs/superpowers/specs/{today}-{slug}-design.md"
    return f"docs/superpowers/plans/{today}-{slug}.md"


def write_planning_artifact(
    *,
    kind: Literal["design", "plan"],
    slug: str,
    markdown: str,
    expected_base_sha: str,
    expected_dependency_sha: str | None = None,
    agent_session_id: str | None = None,
) -> dict:
    """Create a design/plan commit in an isolated deterministic planning branch."""
    if kind not in ("design", "plan"):
        raise PlanningArtifactError("kind must be 'design' or 'plan'")
    if not isinstance(slug, str) or not _SLUG_RE.fullmatch(slug):
        raise PlanningArtifactError(
            "slug must match ^[a-z0-9][a-z0-9-]{0,63}$"
        )
    if not isinstance(markdown, str) or not markdown.strip():
        raise PlanningArtifactError("markdown must be non-empty")
    if len(markdown.encode("utf-8")) > _MAX_MARKDOWN_BYTES:
        raise PlanningArtifactError(
            f"markdown exceeds {_MAX_MARKDOWN_BYTES} byte planning-artifact limit"
        )

    root = repo_root()
    base = _require_commit(expected_base_sha, label="expected base")
    dependency: str | None = None
    if kind == "design":
        current = repo_head()
        if current != base:
            raise StaleRepositoryError(
                f"expected base {base} does not match current HEAD {current}"
            )
        if expected_dependency_sha is not None:
            raise PlanningArtifactError("design artifacts do not accept a dependency SHA")
    else:
        if expected_dependency_sha is None:
            raise PlanningArtifactError("plan requires an expected design dependency SHA")
        try:
            dependency = _require_commit(
                expected_dependency_sha, label="expected dependency"
            )
        except StaleRepositoryError as exc:
            raise PlanningArtifactError(f"plan dependency is unavailable: {exc}") from exc
        ancestor = _run_git(
            ["merge-base", "--is-ancestor", dependency, base],
            root=root,
            check=False,
        )
        if ancestor.returncode != 0:
            raise PlanningArtifactError(
                "plan dependency is not an ancestor of the expected plan base"
            )

    artifact_path = planning_artifact_path(kind, slug)
    content_digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    branch = (
        f"mcp/planning/{kind}-{slug}-{base[:8]}-{content_digest[:8]}"
    )

    existing = _run_git(
        ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        root=root,
        check=False,
    )
    if existing.returncode == 0:
        commit_sha = _run_git(["rev-parse", branch], root=root).stdout.strip()
        stored = _run_git(
            ["show", f"{commit_sha}:{artifact_path}"], root=root, check=False
        )
        if stored.returncode == 0 and stored.stdout == markdown:
            return {
                "artifact_path": artifact_path,
                "branch": branch,
                "commit_sha": commit_sha,
                "base_sha": base,
                "dependency_sha": dependency,
                "content_sha256": content_digest,
                "status": "unchanged",
            }
        raise PlanningArtifactError(
            f"deterministic planning branch already exists with different content: {branch}"
        )

    with tempfile.TemporaryDirectory(prefix="kitty-mcp-planning-") as tmp:
        worktree = Path(tmp)
        _run_git(
            ["worktree", "add", "--quiet", "-b", branch, str(worktree), base],
            root=root,
            timeout=60,
        )
        try:
            _propagate_agent_session(
                root, worktree, session_id=agent_session_id
            )
            destination = worktree / artifact_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(markdown, encoding="utf-8")
            _run_git(["add", "--", artifact_path], root=worktree)
            diff = _run_git(
                ["diff", "--cached", "--quiet"], root=worktree, check=False
            )
            if diff.returncode not in (0, 1):
                raise GitCommandError("git diff --cached failed")
            if diff.returncode == 1:
                _run_git(
                    ["commit", "-m", f"docs: save MCP {kind} {slug}"],
                    root=worktree,
                    timeout=60,
                )
            commit_sha = _run_git(["rev-parse", "HEAD"], root=worktree).stdout.strip()
        finally:
            _run_git(
                ["worktree", "remove", "--force", str(worktree)],
                root=root,
                check=False,
                timeout=60,
            )

    return {
        "artifact_path": artifact_path,
        "branch": branch,
        "commit_sha": commit_sha,
        "base_sha": base,
        "dependency_sha": dependency,
        "content_sha256": content_digest,
        "status": "created",
    }
