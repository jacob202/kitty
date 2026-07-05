"""Project resume — refresh()/resume() composer (P6, docs/packets/021).

refresh(id) composes real state per project: local git for kind="code"
projects, memory_graph mentions, and signals referencing the project name.
Each source is independently bounded so one slow/broken source cannot fail
the whole refresh — same discipline as state_composer.compose_now(). No
LLM summarization in v1 (mechanical only); a follow-on packet can add it
with last-written-wins semantics per the original P6 design note.

resume(id) is a pure read of the stored fields — no composition, no side
effects.

Public API:
  refresh(project_id) -> dict
  resume(project_id) -> dict
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any

from gateway import memory_graph, project_store, signal_store
from gateway.paths import PROJECT_ROOT

logger = logging.getLogger("kitty.project_resume")

SOURCE_TIMEOUT_SECONDS = 5.0
GIT_TIMEOUT_SECONDS = 4.0
SIGNAL_SCAN_LIMIT = 200
GIT_LOG_LINES = 5


def refresh(project_id: int) -> dict[str, Any]:
    """Recompose a project's state from git/memory/signals and persist it."""
    project = project_store.get(project_id)
    if project is None:
        raise project_store.ProjectNotFound(f"no project with id {project_id}")

    sources: dict[str, Any] = {}
    pool = ThreadPoolExecutor(max_workers=3)
    try:
        futures = {
            "git": pool.submit(_git_source, project),
            "memory": pool.submit(_memory_source, project),
            "signals": pool.submit(_signals_source, project),
        }
        for name, future in futures.items():
            try:
                sources[name] = {"ok": True, **future.result(timeout=SOURCE_TIMEOUT_SECONDS)}
            except FutureTimeoutError:
                sources[name] = {"ok": False, "error": f"timed out after {SOURCE_TIMEOUT_SECONDS}s"}
            except Exception as exc:  # noqa: BLE001 — one bad source must not kill the refresh
                logger.warning("project %s refresh source %s failed: %s", project_id, name, exc)
                sources[name] = {"ok": False, "error": str(exc)}
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    summary = _render_summary(sources)
    updated = project_store.update_fields(
        project_id,
        summary=summary,
        last_touched=time.time(),
    )
    return {**updated, "sources": sources}


def resume(project_id: int) -> dict[str, Any]:
    """Render the stored packet shape. Pure read — no composition."""
    project = project_store.get(project_id)
    if project is None:
        raise project_store.ProjectNotFound(f"no project with id {project_id}")
    return {
        "id": project["id"],
        "name": project["name"],
        "kind": project["kind"],
        "status": project["status"],
        "last_touched": project["last_touched"],
        "summary": project["summary"],
        "open_questions": project["open_questions"],
        "next_actions": project["next_actions"],
        "delegable": project["delegable"],
        "links": project["links"],
    }


def _git_source(project: dict[str, Any]) -> dict[str, Any]:
    if project["kind"] != "code":
        return {"paths": [], "note": "non-code project — no git composition"}
    paths = project["paths"]
    if not paths:
        return {"paths": [], "note": "no git paths registered"}

    results = []
    for raw_path in paths:
        candidate = Path(raw_path)
        path = candidate if candidate.is_absolute() else (PROJECT_ROOT / candidate).resolve()
        if not (path / ".git").exists():
            results.append({"path": str(path), "ok": False, "error": "not a git repository"})
            continue
        try:
            branch = _run_git(path, ["branch", "--show-current"]).strip()
            dirty = bool(_run_git(path, ["status", "--porcelain"]).strip())
            log_lines = _run_git(
                path, ["log", f"-{GIT_LOG_LINES}", "--format=%h %s"]
            ).splitlines()
            results.append(
                {"path": str(path), "ok": True, "branch": branch, "dirty": dirty, "recent_log": log_lines}
            )
        except Exception as exc:  # noqa: BLE001 — one bad path must not kill the whole git source
            results.append({"path": str(path), "ok": False, "error": str(exc)})
    return {"paths": results}


def _run_git(path: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=path,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
        check=True,
    )
    return result.stdout


def _memory_source(project: dict[str, Any]) -> dict[str, Any]:
    result = _run_memory_search(project["name"])
    mentions = []
    for section, items in result.results.items():
        for item in items[:5]:
            mentions.append({"section": section, "text": getattr(item, "text", "")[:200]})
    return {"mentions": mentions, "source_errors": result.errors}


def _run_memory_search(query: str):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(memory_graph.search_all(query))
    raise RuntimeError("_memory_source cannot run inside an event loop")


def _signals_source(project: dict[str, Any]) -> dict[str, Any]:
    name_lower = project["name"].lower()
    recent = signal_store.list_recent(limit=SIGNAL_SCAN_LIMIT)
    matches = [s for s in recent if name_lower in json.dumps(s.get("payload", {})).lower()]
    return {"matches": matches[:10], "scanned": len(recent)}


def _render_summary(sources: dict[str, Any]) -> str:
    """Mechanical, no-LLM summary line. See module docstring on v1 scope."""
    parts: list[str] = []

    git = sources.get("git", {})
    if git.get("ok"):
        for entry in git.get("paths", []):
            if entry.get("ok"):
                dirty = " (dirty)" if entry.get("dirty") else ""
                parts.append(f"{entry.get('branch') or 'unknown branch'}{dirty}")

    memory = sources.get("memory", {})
    if memory.get("ok"):
        count = len(memory.get("mentions", []))
        if count:
            parts.append(f"{count} memory mention(s)")

    signals = sources.get("signals", {})
    if signals.get("ok"):
        count = len(signals.get("matches", []))
        if count:
            parts.append(f"{count} signal(s)")

    return "; ".join(parts) if parts else "no data yet — refresh again after registering paths"
