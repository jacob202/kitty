"""Context Control Plane — orchestrates prompt assembly and context retrieval.

This is a DEEP module. Callers (like app.py) should only use:
- get_system_prompt(): The high-leverage entry point for chat sessions.
- build_worker_context(): For specialized non-chat tasks.

Implementation details (domain routing, prompt loading, dynamic context) are private.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple, List, Dict, Any

from gateway import domain_router, prompt_loader, journal, parts, knowledge, memory

logger = logging.getLogger("kitty.context_builder")

# Retrieval constants
MEMORY_LIMIT: int = 5
KNOWLEDGE_LIMIT: int = 3
MEMORY_TOKEN_CAP: int = 500
KNOWLEDGE_TOKEN_CAP: int = 700
MEMORY_SIMILARITY_THRESHOLD: float = 0.7


async def get_system_prompt(
    message: str, parts_mode: bool = False, domain: Optional[str] = None
) -> str:
    """The deep entry point for Kitty's reasoning setup.
    
    1. Classifies the domain of the message (unless ``domain`` is provided).
    2. Loads the appropriate base prompt.
    3. Detects and applies specialized modes (Journal, Parts).
    4. Fetches and appends dynamic context (Memory, Knowledge).
    """
    # 1. Classification & Base Prompt
    if domain is None:
        domain = domain_router.classify_domain(message)
    system_prompt = prompt_loader.load_prompt(domain)

    # 2. Specialized Mode: Journal
    if journal.is_journal_trigger(message):
        system_prompt = journal.build_interview_system_prompt(system_prompt)

    # 3. Specialized Mode: Parts (Internal Council)
    if parts_mode or parts.should_surface_parts(message):
        system_prompt = parts.build_parts_system_prompt(system_prompt)

    # 4. Dynamic Context Retrieval
    memory_block, knowledge_block = await _fetch_all_context(message)
    
    # 5. Assembly
    return _assemble(system_prompt, memory_block, knowledge_block)


def build_worker_context(context_type: str, **kwargs) -> str:
    """Build a plain-text context block for synchronous worker tasks."""
    if context_type == "brief":
        top_task = kwargs.get("top_task", "")
        m = kwargs.get("memory", "")
        tz = kwargs.get("tz", "")
        parts_list = []
        if top_task: parts_list.append(f"Current Top Task: {top_task}")
        if m: parts_list.append(f"Recent Memories: {m}")
        if tz: parts_list.append(f"Timezone: {tz}")
        return "\n".join(parts_list)

    if context_type in ("learning", "reset", "troubleshooter"):
        return kwargs.get("task_desc", "")

    if context_type == "researcher":
        topic = kwargs.get("topic", "")
        chunks = kwargs.get("chunks", "")
        header = f"Research topic: {topic}" if topic else ""
        return f"{header}\n\n{chunks or ''}".strip()

    return ""


# --- Private Implementation Details ---

async def _fetch_knowledge_for_context(query: str) -> str:
    """Load knowledge chunks for injection; must run on the event loop (search is async)."""
    try:
        chunks: List[Dict[str, Any]] = await knowledge.search(query, limit=KNOWLEDGE_LIMIT)
        if not chunks:
            return ""
        lines = []
        for c in chunks:
            src = c.get("source", "unknown")
            dtype = c.get("doc_type", "general")
            text = (c.get("text") or "")[:400]
            label = f"[Source: {src} | type: {dtype}]"
            lines.append(f"{label}\n{text}")
        raw = "\n".join(lines)
        return _truncate(raw, KNOWLEDGE_TOKEN_CAP)
    except Exception:
        logger.warning("Knowledge fetch failed", exc_info=True)
        return ""


async def _fetch_all_context(query: str) -> Tuple[str, str]:
    """Fetch memory and knowledge concurrently."""
    results = await asyncio.gather(
        asyncio.to_thread(_fetch_memory, query),
        _fetch_knowledge_for_context(query),
        return_exceptions=True,
    )

    mem = results[0] if isinstance(results[0], str) else ""
    kn = results[1] if isinstance(results[1], str) else ""

    if isinstance(results[0], Exception): logger.warning("Memory fetch raised: %s", results[0])
    if isinstance(results[1], Exception): logger.warning("Knowledge fetch raised: %s", results[1])
    
    return mem, kn


def _fetch_memory(query: str) -> str:
    try:
        raw = memory.get_context_block(query, limit=MEMORY_LIMIT)
        return _truncate(raw, MEMORY_TOKEN_CAP) if raw else ""
    except Exception:
        logger.warning("Memory fetch failed", exc_info=True)
        return ""


def _build_dynamic(mem: str, kn: str) -> str:
    """Build the dynamic context block from memory and knowledge strings."""
    sections = []
    if mem: sections.append(f"[MEMORY]\n{mem}")
    if kn: sections.append(f"[KNOWLEDGE]\n{kn}")
    return "\n\n".join(sections)


def _assemble(base: str, mem: str, kn: str) -> str:
    dynamic = _build_dynamic(mem, kn)
    if dynamic:
        return f"{base}\n\n{dynamic}"
    return base


def _truncate(text: str, cap: int) -> str:
    if (len(text) // 4) <= cap:
        return text
    return text[:cap * 4] + "…"


# Legacy compatibility aliases
async def build_user_context(query: str, soul_prompt: str) -> Tuple[str, str]:
    """Shim for legacy callers who expect (soul, dynamic) split."""
    mem, kn = await _fetch_all_context(query)
    dynamic = []
    if mem: dynamic.append(f"[MEMORY]\n{mem}")
    if kn: dynamic.append(f"[KNOWLEDGE]\n{kn}")
    return soul_prompt, "\n\n".join(dynamic)

def assemble_system_prompt(soul: str, dynamic: str) -> str:
    return f"{soul}\n\n{dynamic}".strip()
