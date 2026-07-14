"""Collision-safe, privacy-bounded context and run manifests for KittyBuilder.

The Builder needs enough evidence to reproduce a decision without copying
private prompts, runtime data, credentials, or full transcripts into durable
state. This module records hashes, sizes, paths, and bounded operational
metadata; the raw files remain in their existing local locations.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

CONTEXT_MANIFEST_VERSION = 1
RUN_MANIFEST_VERSION = 1


def sha256_file(path: Path) -> str:
    """Return a file digest, raising the real read error with its path."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise OSError(f"Unable to hash Builder context file {path}: {exc}") from exc
    return digest.hexdigest()


def _context_files(repo_root: Path) -> list[Path]:
    """Select public repository instructions and skill definitions to hash."""
    candidates = [
        repo_root / "AGENTS.md",
        repo_root / "opencode.jsonc",
        repo_root / ".claude" / "HANDOFF.md",
        repo_root / ".claude" / "STATE.md",
        repo_root / "docs" / "BLUEPRINT.md",
    ]
    skill_root = repo_root / ".agents" / "skills"
    if skill_root.is_dir():
        candidates.extend(skill_root.rglob("SKILL.md"))

    files: list[Path] = []
    seen: set[Path] = set()
    for path in sorted(candidates):
        if not path.is_file() or path in seen:
            continue
        seen.add(path)
        files.append(path)
    return files


def build_context_manifest(repo_root: Path, bundle_path: Path) -> dict[str, Any]:
    """Hash the bounded worker context without persisting its contents."""
    root = repo_root.resolve()
    files: list[dict[str, Any]] = []
    for path in _context_files(root):
        relative = path.relative_to(root).as_posix()
        files.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )

    bundle = bundle_path.resolve()
    return {
        "manifest_version": CONTEXT_MANIFEST_VERSION,
        "generated_at": time.time(),
        "context_files": files,
        "task_bundle": {
            "path": bundle.name,
            "sha256": sha256_file(bundle),
            "size_bytes": bundle.stat().st_size,
        },
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write a manifest atomically and fail loudly on storage errors."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise OSError(f"Unable to write Builder manifest {path}: {exc}") from exc


def write_run_manifest(path: Path, payload: dict[str, Any]) -> None:
    """Persist the current run manifest snapshot atomically."""
    write_json_atomic(path, {"manifest_version": RUN_MANIFEST_VERSION, **payload})
