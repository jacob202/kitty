"""Context Control Plane — orchestrates prompt assembly and context retrieval.

This is a DEEP module. Callers (like app.py) should only use:
- get_system_prompt(): The high-leverage entry point for chat sessions.
- build_worker_context(): For specialized non-chat tasks.

Implementation details (domain routing, prompt loading, dynamic context) are private.
"""

from __future__ import annotations

import logging
from typing import Optional

from gateway import (
    domain_router,
    prompt_loader,
    journal,
    parts,
    memory_graph,
    user_context,
    voice_gate,
)
from gateway.context_enrichment import enrich_dynamic_context

logger = logging.getLogger("kitty.context_builder")


async def get_system_prompt(
    message: str, parts_mode: bool = False, domain: Optional[str] = None
) -> str:
    """The deep entry point for Kitty's reasoning setup."""
    if domain is None:
        domain = domain_router.classify_domain(message)
    system_prompt = prompt_loader.load_prompt(domain)

    if journal.is_journal_trigger(message):
        system_prompt = journal.build_interview_system_prompt(system_prompt)

    if parts_mode or parts.should_surface_parts(message):
        system_prompt = parts.build_parts_system_prompt(system_prompt)

    user_block = user_context.load_user_context()
    if user_block:
        system_prompt = f"{system_prompt}\n\n{user_block}"

    dynamic_context = await memory_graph.unified_context(message)
    dynamic_context = await enrich_dynamic_context(dynamic_context, message)

    return _assemble(system_prompt, dynamic_context)


def build_worker_context(context_type: str, **kwargs) -> str:
    """Build a plain-text context block for synchronous worker tasks."""
    if context_type in ("learning", "reset", "troubleshooter"):
        return kwargs.get("task_desc", "")

    if context_type == "researcher":
        topic = kwargs.get("topic", "")
        chunks = kwargs.get("chunks", "")
        header = f"Research topic: {topic}" if topic else ""
        return f"{header}\n\n{chunks or ''}".strip()

    return ""


def _assemble(base: str, dynamic_context: str) -> str:
    if dynamic_context:
        return f"{base}\n\n{dynamic_context}"
    return base
