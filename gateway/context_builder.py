"""Context Control Plane — thin façade for backward compatibility.

Phase 2 of the gateway deepening program (per
``docs/superpowers/specs/2026-06-24-gateway-deepening-program-design.md``)
moved all read-path orchestration into
:mod:`gateway.context_assembler`. This module is kept for one release as
a façade so existing callers (``routes.completions``, ``routes.ask``,
``app.py``, ``buddy``, and any test that imported
``get_system_prompt`` or ``build_worker_context``) keep working
unchanged.

Do NOT add new logic here. Add it to ``gateway.context_assembler`` and
have the new callers import from there. This module will be deleted in
the release after ``context_assembler`` has proven stable.
"""

from __future__ import annotations

from typing import Optional

from gateway.context_assembler import (
    ContextBundle,
    assemble_context,
    assert_not_total_failure,
)

__all__ = [
    "ContextBundle",
    "assemble_context",
    "assert_not_total_failure",
    "get_system_prompt",
    "build_worker_context",
]


async def get_system_prompt(
    message: str, parts_mode: bool = False, domain: Optional[str] = None
) -> str:
    """Back-compat shim. Returns the joined system prompt string.

    Equivalent to ``(await assemble_context(message, parts_mode, domain)).system``.
    This is the same string the assembler would build; the only
    difference is the return type (string here, ``ContextBundle`` in
    the new path).
    """
    bundle = await assemble_context(message, parts_mode=parts_mode, domain=domain)
    return bundle.system


def build_worker_context(context_type: str, **kwargs) -> str:
    """Build a plain-text context block for synchronous worker tasks.

    Unchanged from pre-Phase 2. This is independent of the read path
    and has no caller in the assembler.
    """
    if context_type in ("learning", "reset", "troubleshooter"):
        return kwargs.get("task_desc", "")

    if context_type == "researcher":
        topic = kwargs.get("topic", "")
        chunks = kwargs.get("chunks", "")
        header = f"Research topic: {topic}" if topic else ""
        return f"{header}\n\n{chunks or ''}".strip()

    return ""
