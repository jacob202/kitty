"""No async caller may reach llm_client.call_llm on the event loop's thread.

``call_llm`` is synchronous, and ``retry_with_backoff`` sleeps with a bare
``time.sleep`` when a provider answers 429. Called straight from ``async def``
that sleep runs on the event loop's own thread, so a single rate-limited call
freezes every other concurrent task in the process -- not just the caller.

The guard is structural rather than behavioural on purpose. An earlier
reproduction here drove ``retry_with_backoff`` bare inside ``asyncio.run`` and
asserted the loop stalled. It passed while proving nothing about this codebase:
nothing here called it that way. It named ``gateway/expert_proactive.py`` as the
victim, and that module had already been fixed to offload through
``asyncio.to_thread``. Meanwhile two real bare callers sat in
``scripts/curation/`` that the reproduction never looked at.

So this asserts the invariant that actually matters -- every async path offloads
-- across every file, instead of dramatising one synthetic misuse.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SEARCH_ROOTS = ("gateway", "mcp", "integrations", "workers", "scripts")

SKIP_PARTS = {".worktrees", "node_modules", "venv", ".venv", "__pycache__"}


def _python_files() -> list[Path]:
    files: list[Path] = []
    for name in SEARCH_ROOTS:
        root = ROOT / name
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if SKIP_PARTS.isdisjoint(path.parts):
                files.append(path)
    return files


def _bare_async_call_llm(path: Path) -> list[tuple[str, int]]:
    """Direct ``call_llm(...)`` calls lexically inside an ``async def``.

    A call handed to ``asyncio.to_thread`` is a reference, not a Call node, so
    the offloaded form never matches.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            func = sub.func
            if isinstance(func, ast.Attribute):
                name = func.attr
            elif isinstance(func, ast.Name):
                name = func.id
            else:
                continue
            if name == "call_llm":
                found.append((node.name, sub.lineno))
    return found


def test_no_async_caller_invokes_call_llm_on_the_event_loop() -> None:
    files = _python_files()
    assert files, "found no Python files to scan; the search roots are wrong"

    offenders: list[str] = []
    for path in files:
        for func_name, lineno in _bare_async_call_llm(path):
            offenders.append(f"{path.relative_to(ROOT)}:{lineno} in async {func_name}()")

    assert not offenders, (
        "these async functions call the synchronous call_llm directly, so a 429 "
        "retry sleeps on the event loop thread and stalls every concurrent task:\n  "
        + "\n  ".join(sorted(offenders))
        + "\nWrap the call: await asyncio.to_thread(llm_client.call_llm, ...)"
    )
