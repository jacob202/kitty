"""Deterministic packet contract checks run before semantic review.

These checks are deliberately literal and cheap. They do not replace tests or
review; they reject implementation shapes the packet contract explicitly says
must or must not exist, before reviewer inference is spent.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


class ContractGateError(RuntimeError):
    """Raised when the deterministic gate itself cannot inspect the worktree."""


def _git(worktree: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=worktree, capture_output=True, text=True,
        timeout=20, check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "git command failed").strip()
        raise ContractGateError(detail)
    return result.stdout


def _parts(path: str) -> tuple[str, ...]:
    return tuple(part for part in Path(path).parts if part not in ("", "."))


def _overlap(left: str, right: str) -> bool:
    a, b = _parts(left), _parts(right)
    if not a or not b:
        return False
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return longer[: len(shorter)] == shorter


def _changed_paths(worktree: Path, base_sha: str) -> list[str]:
    output = _git(worktree, "diff", "--no-renames", "--name-only", f"{base_sha}..HEAD")
    return [line.strip() for line in output.splitlines() if line.strip()]


def _changed_text(worktree: Path, changed_paths: list[str]) -> str:
    chunks: list[str] = []
    for rel in changed_paths:
        path = worktree / rel
        if not path.is_file():
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            raise ContractGateError(f"cannot read changed file {rel}: {exc}") from exc
    return "\n".join(chunks)


def evaluate_contract_checks(
    worktree: Path,
    *,
    base_sha: str,
    forbidden_symbols: list[str] | None = None,
    required_symbols: list[str] | None = None,
    forbidden_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate literal packet constraints against cumulative packet changes."""
    forbidden_symbols = list(forbidden_symbols or [])
    required_symbols = list(required_symbols or [])
    forbidden_paths = list(forbidden_paths or [])
    if not forbidden_symbols and not required_symbols and not forbidden_paths:
        return {
            "passed": True,
            "changed_paths": [],
            "forbidden_symbols_found": [],
            "required_symbols_missing": [],
            "forbidden_paths_changed": [],
        }

    changed = _changed_paths(worktree, base_sha)
    text = _changed_text(worktree, changed)

    forbidden_found = [symbol for symbol in forbidden_symbols if symbol in text]
    required_missing = [symbol for symbol in required_symbols if symbol not in text]
    forbidden_paths_changed = [
        path
        for path in changed
        if any(_overlap(path, forbidden) for forbidden in forbidden_paths)
    ]
    passed = not forbidden_found and not required_missing and not forbidden_paths_changed
    return {
        "passed": passed,
        "changed_paths": changed,
        "forbidden_symbols_found": forbidden_found,
        "required_symbols_missing": required_missing,
        "forbidden_paths_changed": forbidden_paths_changed,
    }
