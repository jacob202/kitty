import asyncio
import logging
from gateway.prompt_loader import load_prompt
from gateway.memory import search_memory
from gateway.knowledge import search_knowledge

logger = logging.getLogger("kitty.context")

MEMORY_BUDGET_TOKENS    = 500
KNOWLEDGE_BUDGET_TOKENS = 700
RELEVANCE_THRESHOLD     = 0.7
WORKER_BUDGET_TOKENS    = 300

WORKER_TEMPLATES = {
    "brief": "{top_task}\n{memory}\nJacob's timezone: {tz}",
    "researcher": "Topic: {topic}\n{chunks}",
    "onboarding": "{user_text}",
    "learning": "{task_desc}",
    "reset": "{task_desc}",
    "troubleshooter": "{task_desc}"
}


def _count_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


async def _fetch_memory(query: str) -> list[dict]:
    return await asyncio.to_thread(search_memory, query, limit=10)


async def _fetch_knowledge(query: str) -> list[dict]:
    return await asyncio.to_thread(search_knowledge, query, limit=10)


async def build_user_context(query: str, domain: str) -> tuple[str, str]:
    """Returns (cached_prefix, dynamic_suffix)"""
    cached_prefix = load_prompt(domain)

    results = await asyncio.gather(
        _fetch_memory(query),
        _fetch_knowledge(query),
        return_exceptions=True
    )

    mem_results = []
    know_results = []

    if isinstance(results[0], Exception):
        logger.warning("memory fetch failed: %s", results[0])
    else:
        mem_results = results[0]

    if isinstance(results[1], Exception):
        logger.warning("knowledge fetch failed: %s", results[1])
    else:
        know_results = results[1]

    mem_filtered = [m for m in mem_results if m.get("score", 1.0) >= RELEVANCE_THRESHOLD]
    know_filtered = [k for k in know_results if k.get("score", 1.0) >= RELEVANCE_THRESHOLD]

    mem_filtered.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    know_filtered.sort(key=lambda x: x.get("score", 0), reverse=True)

    mem_kept = []
    mem_tokens = 0
    for m in mem_filtered:
        text = m.get("memory", m.get("text", ""))
        tokens = _count_tokens(text)
        if mem_tokens + tokens <= MEMORY_BUDGET_TOKENS:
            mem_kept.append(text)
            mem_tokens += tokens

    know_kept = []
    know_tokens = 0
    for k in know_filtered:
        text = k.get("text", "")
        tokens = _count_tokens(text)
        if know_tokens + tokens <= KNOWLEDGE_BUDGET_TOKENS:
            know_kept.append(text)
            know_tokens += tokens

    sections = []
    if mem_kept:
        sections.append("### About Jacob\n" + "\n".join(f"- {m}" for m in mem_kept))
    if know_kept:
        sections.append("### Relevant context\n" + "\n".join(know_kept))

    dynamic_suffix = "\n\n".join(sections)
    return cached_prefix, dynamic_suffix


def build_worker_context(task_type: str, **kwargs) -> str:
    template = WORKER_TEMPLATES.get(task_type, "")

    memory = kwargs.get("memory")
    if memory is not None:
        tokens = _count_tokens(memory)
        if tokens > 100:
            words = memory.split()
            memory = " ".join(words[:int(100 / 1.3)]) + "..."
        kwargs["memory"] = memory
    else:
        kwargs["memory"] = ""

    format_args = {k: v for k, v in kwargs.items()}
    for key in ["top_task", "tz", "topic", "chunks", "user_text", "task_desc", "memory"]:
        if key not in format_args:
            format_args[key] = ""

    text = template.format(**format_args).strip()

    if _count_tokens(text) > WORKER_BUDGET_TOKENS:
        words = text.split()
        text = " ".join(words[:int(WORKER_BUDGET_TOKENS / 1.3)]) + "..."

    return text
