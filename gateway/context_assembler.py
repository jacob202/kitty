"""Context Assembler — the single deep module for read-path context.

After Phase 2, the request-time read path is one module with one testable
surface. ``assemble_context`` is the only public entry point; everything else
in this module is an internal seam. ``context_builder`` is now a thin façade
(see :mod:`gateway.context_builder`).

Public surface:

- :class:`ContextBundle` — the structured result. ``system`` is the joined
  prompt string. ``memory_items`` are the raw :class:`Item` records the
  assemblers got from each store. ``live_blocks`` are the strings produced
  by the enrichment layer (calendar, weather, etc.). ``warnings`` lists every
  source that failed so the operator can see what was missing.

- :func:`assemble_context` — the deep entry point. Always returns a
  ``ContextBundle``; individual source failures become ``Warning`` strings,
  never exceptions. Total infrastructure failure (no LLM reachable AND no
  DB reachable) is the only condition under which it raises.

Failure handling (the partial-result contract):

- Each store adapter runs concurrently with a per-store timeout.
- A failed adapter produces an empty ``list[Item]`` and a warning string
  in the bundle.
- Each enrichment runs in isolation; a failure produces a warning string.
- The system prompt is always built from whatever sources succeeded.
- The bundle is always returned (no caller is left guessing whether a
  context build is partial).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from gateway import (
    domain_router,
    journal,
    prompts,
    skill_registry,
    user_context,
)
from gateway.context_enrichment import (
    DEFAULT_ENRICHMENTS,
    EnrichmentFn,
    run_enrichments,
)
from gateway.memory_graph import (
    CONTEXT_TOKEN_CAP,
    Item,
    MemoryGraph,
    StoreAdapter,
    _format_unified_items,
)

logger = logging.getLogger("kitty.context_assembler")

SkillHintFn = Callable[[str], str]

# --- Parts system (folded from gateway/parts.py) ---
# Triggers that suggest a parts-mode response adds value
_HIGH_STAKES_TRIGGERS = [
    "should i",
    "should we",
    "deciding",
    "decision",
    "choose",
    "choice",
    "worth it",
    "is it worth",
    "commit",
    "quit",
    "leave",
    "stay",
    "invest",
    "buy",
    "sell",
    "switch",
    "change everything",
]

_CHALLENGE_TRIGGERS = [
    "i think",
    "i believe",
    "i know",
    "obviously",
    "clearly",
    "definitely",
    "always",
    "never",
    "everyone",
    "no one",
    "the only",
    "the best",
    "for sure",
    "100%",
    "guaranteed",
]

_SOCRATIC_TRIGGERS = [
    "what do you think",
    "am i right",
    "is this a good idea",
    "does this make sense",
    "validate",
    "confirm",
    "agree",
    "tell me i'm",
    "reassure",
]


def _should_surface_parts(message: str) -> bool:
    """Return True when the context warrants auto-surfacing the parts debate."""
    text = message.lower()
    high_stakes = any(t in text for t in _HIGH_STAKES_TRIGGERS)
    assertion = any(t in text for t in _CHALLENGE_TRIGGERS)
    validation_seek = any(t in text for t in _SOCRATIC_TRIGGERS)
    return (high_stakes and assertion) or validation_seek


def _build_parts_system_prompt(base_prompt: str) -> str:
    """Append the parts debate instruction to an existing system prompt."""
    from gateway.prompts import PARTS_COUNCIL_PROMPT

    return base_prompt + "\n\n" + PARTS_COUNCIL_PROMPT


@dataclass
class ContextBundle:
    """The structured outcome of :func:`assemble_context`.

    Attributes:
        system: The joined system prompt — what callers pass to the LLM.
        memory_items: Every :class:`Item` retrieved by the store adapters,
            flattened across stores. Order is store order, then item order
            within a store. Empty list when every adapter failed.
        live_blocks: The string blocks produced by the enrichment layer
            (calendar, weather, etc.). Excludes memory items.
        warnings: Per-source failure strings in the form
            ``{source_name}: {exc_type}: {message}``. Empty when every
            source succeeded.
    """

    system: str
    memory_items: list[Item] = field(default_factory=list)
    live_blocks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _AssemblerDeps:
    """Internal: the seams a test can swap to drive the orchestrator."""

    adapters: list[StoreAdapter] | None = None
    enrichments: tuple[EnrichmentFn, ...] = DEFAULT_ENRICHMENTS
    skill_hint_fn: SkillHintFn | None = None
    graph_cls: type[MemoryGraph] = MemoryGraph


def _default_skill_hint(message: str) -> str:
    """A one-line pointer to a reasoning skill whose triggers match ``message``."""
    try:
        matches = skill_registry.suggest(message, limit=1)
    except Exception:
        return ""
    if not matches:
        return ""
    skill = matches[0]
    desc = (skill.get("description", "") or "").split(".")[0].strip()
    return f"## Relevant skill\nConsider the **{skill.get('name', 'unknown')}** skill: {desc}."


def _domain_prompt(message: str, domain: str | None) -> str:
    """Load the per-domain system prompt. Apply domain-specific mutations."""
    if domain is None:
        domain = domain_router.classify_domain(message)
    prompt = prompts.load_prompt(domain)

    if journal.is_journal_trigger(message):
        prompt = journal.build_interview_system_prompt(prompt)

    if user_context.is_interview_trigger(message):
        prompt = user_context.build_interview_prompt(prompt)

    return prompt


def _flatten_items(results: dict[str, list[Item]]) -> list[Item]:
    items: list[Item] = []
    for store_items in results.values():
        items.extend(store_items)
    return items


def _format_memory_block(results: dict[str, list[Item]], cap: int) -> str:
    """Render ``results`` (keyed by source) as the memory-graph section."""
    if not any(results.values()):
        return ""
    return _format_unified_items(results, cap=cap)


def _join_blocks(*blocks: str) -> str:
    """Concatenate non-empty blocks with a blank line between them."""
    return "\n\n".join(b for b in blocks if b)


async def assemble_context(
    message: str,
    parts_mode: bool = False,
    domain: str | None = None,
    deps: _AssemblerDeps | None = None,
) -> ContextBundle:
    """The single deep entry point for request-time context.

    Returns a :class:`ContextBundle` even when sources fail. Only raises
    on total infrastructure failure (see the module docstring).

    Args:
        message: The user's incoming message — drives memory retrieval
            and trigger detection.
        parts_mode: Force the parts-system surface. When false, the parts
            block is added only if the message triggers parts-mode detection.
        domain: Pre-classified domain. When ``None`` the domain is inferred
            from the message.
        deps: Internal — test override seam. Production callers should
            leave this as ``None``.
    """
    deps = deps or _AssemblerDeps()
    warnings: list[str] = []

    base_prompt = _domain_prompt(message, domain)
    if parts_mode or _should_surface_parts(message):
        base_prompt = _build_parts_system_prompt(base_prompt)

    user_block = user_context.load_user_context()
    if user_block:
        base_prompt = _join_blocks(base_prompt, user_block)

    hint_fn = deps.skill_hint_fn or _default_skill_hint
    hint = hint_fn(message)
    if hint:
        base_prompt = _join_blocks(base_prompt, hint)

    graph = deps.graph_cls(deps.adapters)
    graph_result = await graph.search_all(message)
    warnings.extend(f"memory_graph:{err}" for err in graph_result.errors)

    memory_block = _format_memory_block(graph_result.results, CONTEXT_TOKEN_CAP)

    enrichment_blocks, enrichment_warnings = await run_enrichments(deps.enrichments, message)
    warnings.extend(enrichment_warnings)

    system = _join_blocks(
        base_prompt,
        memory_block,
        *enrichment_blocks,
    )

    return ContextBundle(
        system=system,
        memory_items=_flatten_items(graph_result.results),
        live_blocks=list(enrichment_blocks),
        warnings=warnings,
    )


def _looks_like_total_failure(bundle: ContextBundle) -> bool:
    """A bundle is a total failure when there is nothing to prompt the LLM with.

    Concretely: no memory items, no live blocks, and at least one warning
    in the memory_graph layer (the only place a hard infrastructure failure
    surfaces). Pure enrichment failures alone are not total — the prompt
    is still usable.
    """
    has_memory = bool(bundle.memory_items)
    has_live = bool(bundle.live_blocks)
    has_memory_warnings = any(w.startswith("memory_graph:") for w in bundle.warnings)
    return not has_memory and not has_live and has_memory_warnings


def assert_not_total_failure(bundle: ContextBundle) -> ContextBundle:
    """Raise :class:`RuntimeError` if the bundle is a total infrastructure failure.

    Callers that want the strict "no LLM AND no DB" raise semantics should
    call this after :func:`assemble_context`. The base function never raises
    so a partial result is always available; the route layer decides when
    "total failure" is fatal.
    """
    if _looks_like_total_failure(bundle):
        raise RuntimeError(
            f"context assembler: total infrastructure failure (warnings={bundle.warnings!r})"
        )
    return bundle


__all__ = [
    "ContextBundle",
    "SkillHintFn",
    "assemble_context",
    "assert_not_total_failure",
]
