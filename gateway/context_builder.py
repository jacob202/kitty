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

from gateway import domain_router, prompt_loader, journal, parts, memory_graph, voice_gate

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

    # 4. Dynamic Context Retrieval (unified across all stores)
    dynamic_context = await memory_graph.unified_context(message)

    # 5. Calendar context — today's upcoming events (macOS only, silent on Linux)
    try:
        from gateway.calendar import get_upcoming_text, is_available as cal_available
        if cal_available():
            cal_text = await asyncio.to_thread(get_upcoming_text, 3)
            if cal_text:
                dynamic_context = f"{dynamic_context}\n\n{cal_text}" if dynamic_context else cal_text
    except Exception:
        pass

    # 6. Ambient context — what app Jacob is currently in (opt-in via KITTY_AMBIENT_ENABLED=1)
    try:
        from gateway.ambient import get_ambient_text
        ambient = get_ambient_text()
        if ambient:
            dynamic_context = f"{dynamic_context}\n{ambient}" if dynamic_context else ambient
    except Exception:
        pass

    # 7. Active nudges — pending proactive suggestions
    try:
        from gateway.nudge import get_pending
        pending = get_pending()
        if pending:
            nudge_lines = "\n".join(f"- {n['message']}" for n in pending[:2])
            nudge_block = f"[PENDING NUDGES]\n{nudge_lines}"
            dynamic_context = f"{dynamic_context}\n\n{nudge_block}" if dynamic_context else nudge_block
    except Exception:
        pass

    # 8. Drift correction nudge (if Kitty has been off-voice this session)
    nudge = voice_gate.get_drift_nudge()
    if nudge:
        dynamic_context = (dynamic_context + nudge) if dynamic_context else nudge

    # 9. Assembly
    return _assemble(system_prompt, dynamic_context)


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

def _assemble(base: str, dynamic_context: str) -> str:
    if dynamic_context:
        return f"{base}\n\n{dynamic_context}"
    return base


def _truncate(text: str, cap: int) -> str:
    if (len(text) // 4) <= cap:
        return text
    return text[:cap * 4] + "…"


# Legacy compatibility aliases
async def build_user_context(query: str, soul_prompt: str) -> Tuple[str, str]:
    """Shim for legacy callers who expect (soul, dynamic) split."""
    dynamic = await memory_graph.unified_context(query)
    return soul_prompt, dynamic

def assemble_system_prompt(soul: str, dynamic: str) -> str:
    return f"{soul}\n\n{dynamic}".strip()


# Backward-compat: keep old function names available for any caller that patches them
from gateway.memory import get_context_block as _fetch_memory  # noqa: E402, F401
from gateway.knowledge import get_knowledge_block as _fetch_knowledge_block  # noqa: E402, F401
