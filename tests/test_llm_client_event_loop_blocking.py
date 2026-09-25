"""No async caller may reach llm_client.call_llm on the event loop's thread.

``call_llm`` is synchronous, and ``retry_with_backoff`` sleeps with a bare
``time.sleep`` when a provider answers 429. Reached from ``async def`` without
``asyncio.to_thread`` that sleep runs on the event loop's own thread, so a single
rate-limited call freezes every other concurrent task in the process -- not just
the caller.

The guard is structural rather than behavioural on purpose. An earlier
reproduction here drove ``retry_with_backoff`` bare inside ``asyncio.run`` and
asserted the loop stalled. It passed while proving nothing about this codebase:
nothing called it that way. It named ``gateway/expert_proactive.py`` as the
victim, and that module had already been fixed to offload through
``asyncio.to_thread``, while two real bare callers sat in ``scripts/curation/``
that the reproduction never looked at.

Reaching it *indirectly* blocks the loop just as hard, so the scan follows
synchronous helpers to a fixpoint. Resolution is import-aware and qualified by
module: a call is followed only when it can be tied to a specific definition,
via a same-file ``def``, a ``from x import y``, or a module alias attribute.
Matching on bare names instead would collide on ubiquitous ones -- ``get``,
``close``, ``compile`` -- and flag most of the async code in the repository.

Handing a callable to ``asyncio.to_thread`` passes a reference, not a Call node,
so every offloaded form stays invisible here and only genuinely-blocking paths
are reported. Dynamic dispatch is out of reach of any AST pass; this catches the
static paths, which is where the defect has actually appeared twice.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SEARCH_ROOTS = ("gateway", "mcp", "integrations", "workers", "scripts")

SKIP_PARTS = {".worktrees", "node_modules", "venv", ".venv", "__pycache__"}

TARGET_MODULE = "gateway.llm_client"
TARGET_NAME = "call_llm"
TARGET = f"{TARGET_MODULE}::{TARGET_NAME}"


def _python_files() -> list[Path]:
    files: list[Path] = []
    for name in SEARCH_ROOTS:
        root = ROOT / name
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            # Relative parts: this checkout may itself live under .worktrees/.
            if SKIP_PARTS.isdisjoint(path.relative_to(ROOT).parts):
                files.append(path)
    return files


def _module_of(path: Path) -> str:
    return str(path.relative_to(ROOT).with_suffix("")).replace("/", ".")


def _import_maps(tree: ast.Module) -> tuple[dict[str, str], dict[str, str]]:
    """(bare name -> "mod::name", module alias -> "mod") for this file."""
    names: dict[str, str] = {}
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for a in node.names:
                names[a.asname or a.name] = f"{node.module}::{a.name}"
        elif isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name.split(".")[0]] = a.name
    return names, aliases


def _resolve_calls(node: ast.AST, module: str, local: set[str],
                   names: dict[str, str], aliases: dict[str, str]) -> set[str]:
    """Qualified targets this node calls. Unresolvable calls are dropped.

    ``asyncio.to_thread(call_llm, ...)`` passes a Name rather than a Call, so an
    offloaded target never appears -- the distinction this guard rests on.
    """
    out: set[str] = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if isinstance(func, ast.Name):
            if func.id in local:
                out.add(f"{module}::{func.id}")
            elif func.id in names:
                out.add(names[func.id])
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            base = func.value.id
            if base in aliases:
                out.add(f"{aliases[base]}::{func.attr}")
            elif base in names:  # `from gateway import llm_client`
                out.add(f"{names[base].split('::')[1]}::{func.attr}")
    return out


def _scan() -> tuple[list[str], list[str]]:
    """Return (offending async functions, files that could not be parsed)."""
    unreadable: list[str] = []
    sync_calls: dict[str, set[str]] = {}
    async_defs: list[tuple[str, str, int, set[str]]] = []

    for path in _python_files():
        rel = str(path.relative_to(ROOT))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError) as exc:
            unreadable.append(f"{rel}: {type(exc).__name__}")
            continue

        module = _module_of(path)
        names, aliases = _import_maps(tree)
        local = {
            n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = _resolve_calls(node, module, local, names, aliases)
            if isinstance(node, ast.AsyncFunctionDef):
                async_defs.append((rel, node.name, node.lineno, calls))
            else:
                sync_calls.setdefault(f"{module}::{node.name}", set()).update(calls)

    # Sync functions reaching call_llm, directly or through other sync
    # functions. Iterated to a fixpoint so depth is not capped at one hop.
    blocking = {TARGET, f"llm_client::{TARGET_NAME}"}
    while True:
        grown = {n for n, c in sync_calls.items() if n not in blocking and c & blocking}
        if not grown:
            break
        blocking |= grown

    offenders = [
        f"{rel}:{lineno} async {name}() reaches {sorted(calls & blocking)[0]}"
        for rel, name, lineno, calls in async_defs
        if calls & blocking
    ]
    return sorted(offenders), sorted(unreadable)


def test_no_async_caller_reaches_call_llm_on_the_event_loop() -> None:
    assert _python_files(), "found no Python files to scan; the search roots are wrong"

    offenders, unreadable = _scan()

    # A file the scan cannot read is missing evidence, not a pass. Staying
    # silent would let an unparsable source hide a real offender.
    assert not unreadable, (
        "these files could not be parsed, so the invariant is unproven for them:\n  "
        + "\n  ".join(unreadable)
    )

    assert not offenders, (
        "these async functions reach the synchronous call_llm without leaving the "
        "event loop thread, so a 429 retry sleeps on it and stalls every "
        "concurrent task:\n  "
        + "\n  ".join(offenders)
        + "\nOffload the call: await asyncio.to_thread(llm_client.call_llm, ...)"
    )
