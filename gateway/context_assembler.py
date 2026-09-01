"""Context Assembler — the single deep module for read-path context.

After Phase 2, the request-time read path is one module with one testable
surface. ``assemble_context`` is the only public entry point; everything else
in this module is an internal seam.

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
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

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
    MemoryEvidence,
    MemoryGraph,
    StoreAdapter,
    _select_unified_items,
)
from gateway.memory_policy import should_surface
from gateway.personality import personality_block

logger = logging.getLogger("kitty.context_assembler")

SkillHintFn = Callable[[str], str]


class SkillSelectionError(ValueError):
    """An explicit ``Use skill:`` directive cannot be honored truthfully."""


class SelectedSkillTooLargeError(ValueError):
    """An explicit skill cannot fit without losing part of its instructions."""

# Whole model-visible prompt caps. Memory has its own tighter selection budget,
# but every other block must also fit inside one explicit request envelope.
TOTAL_CONTEXT_TOKEN_CAPS: dict[str, int] = {
    "trivial": 3_000,
    "standard": 8_000,
    "deep": 16_000,
}
_CONTEXT_BLOCK_SHARES: dict[str, float] = {
    "domain": 0.25,
    "objective": 0.05,
    "personality": 0.10,
    "user_context": 0.25,
    "skill": 0.05,
    "memory": 0.20,
    "enrichments": 0.10,
}
_CONTEXT_TRUNCATION_MARKER = "\n[truncated by Kitty context budget]"

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
        injected_memory_items: The exact memory records rendered into
            ``system`` for this request, in prompt order — after memory
            policy, the privacy gate, and token budgeting. This is the
            truthful "which memories informed this answer" evidence;
            ``memory_items`` above remains the raw pre-filter audit list.
    """

    system: str
    memory_items: list[Item] = field(default_factory=list)
    live_blocks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    injected_memory_items: list[MemoryEvidence] = field(default_factory=list)
    context_budget: dict[str, object] = field(default_factory=dict)
    # Exact model-visible block for an explicitly selected skill. The chat route
    # uses this to fail closed if its final system-message budget would clip it.
    selected_skill_block: str | None = None
    context_health: dict[str, object] = field(
        default_factory=lambda: {
            "mode": "full",
            "degraded_sources": [],
            "budget_clipped": False,
            "warning_count": 0,
        }
    )


@dataclass
class _AssemblerDeps:
    """Internal: the seams a test can swap to drive the orchestrator."""

    adapters: list[StoreAdapter] | None = None
    enrichments: tuple[EnrichmentFn, ...] = DEFAULT_ENRICHMENTS
    skill_hint_fn: SkillHintFn | None = None
    graph_cls: type[MemoryGraph] = MemoryGraph


def _explicit_skill_name(message: str) -> str | None:
    """Return the exact registry name from one explicit directive line.

    Skill Registry accepts Unicode names, so the launcher/parser must not use a
    narrower ASCII grammar than the authority it projects.
    """
    match = re.search(r"(?im)^\s*use skill:\s*([^\r\n]+?)\s*$", message)
    if not match:
        return None
    name = match.group(1).strip()
    return name or None


def _default_skill_hint(message: str) -> str:
    """Resolve an explicit installed skill, otherwise suggest one from triggers."""
    name = _explicit_skill_name(message)
    if name is not None:
        try:
            skill = skill_registry.get(name)
            if not skill:
                raise SkillSelectionError(f"Skill not found: {name}")
            rendered = skill_registry.invoke(name)
            if rendered.get("error"):
                raise SkillSelectionError(str(rendered["error"]))
            prompt = str(rendered.get("prompt", "")).strip()
            if not prompt:
                raise SkillSelectionError(f"Skill has no usable instructions: {name}")
            return f"## Selected skill\n{name}\n\n{prompt}"
        except SkillSelectionError:
            raise
        except Exception as exc:
            raise SkillSelectionError(f"Skill unavailable: {name}: {exc}") from exc

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

    if domain == "code":
        # The Builder handoff is the task-specific instruction for build/fix turns.
        # Keep it first so the bounded domain block cannot clip that contract off
        # the tail of the much longer generic Kitty prompt.
        prompt = _join_blocks(prompts.get_prompt("builder.proposal"), prompt)

    return prompt


def _flatten_items(results: dict[str, list[Item]]) -> list[Item]:
    items: list[Item] = []
    for store_items in results.values():
        items.extend(store_items)
    return items


def _filter_items_by_policy(
    results: dict[str, list[Item]], query: str
) -> dict[str, list[Item]]:
    """Filter each store's items through memory policy, keeping only those
    that should surface. Preserves the dict structure for downstream formatting."""
    filtered: dict[str, list[Item]] = {}
    for source_name, items in results.items():
        kept = [item for item in items if should_surface(item, query=query)]
        if kept:
            filtered[source_name] = kept
    return filtered


def _join_blocks(*blocks: str) -> str:
    """Concatenate non-empty blocks with a blank line between them."""
    return "\n\n".join(b for b in blocks if b)


def _warning_source(warning: str) -> str | None:
    """Extract a bounded source id without leaking exception detail."""
    if warning.startswith("context_budget:"):
        return None
    head, sep, remainder = warning.partition(":")
    if not sep:
        return "unknown"
    if head == "memory_graph":
        head, _sep, _detail = remainder.partition(":")
    name = head.strip().strip("_")
    if name.endswith("_block"):
        name = name[: -len("_block")]
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", name)[:64]
    return name or "unknown"


def _degraded_sources(warnings: list[str]) -> list[str]:
    return sorted(
        {source for warning in warnings if (source := _warning_source(warning))}
    )


def _context_degradation_marker(sources: list[str]) -> str:
    joined = ",".join(sources)
    return (
        f'<kitty_context_state mode="degraded" unavailable_sources="{joined}">'
        "Some optional context sources were unavailable for this turn. "
        "Do not imply you used missing context; mention the limitation only if it "
        "materially affects the answer."
        "</kitty_context_state>"
    )


def _context_health(warnings: list[str]) -> dict[str, object]:
    sources = _degraded_sources(warnings)
    budget_clipped = any(warning.startswith("context_budget:") for warning in warnings)
    source_warning_count = sum(
        not warning.startswith("context_budget:") for warning in warnings
    )
    return {
        "mode": "degraded" if sources else "full",
        "degraded_sources": sources,
        "budget_clipped": budget_clipped,
        "warning_count": source_warning_count,
    }


def _budget_units(text: str) -> int:
    """Conservative token upper bound: one unit per UTF-8 byte."""
    return len(text.encode("utf-8"))


def _utf8_prefix(text: str, max_units: int) -> str:
    if max_units <= 0:
        return ""
    return text.encode("utf-8")[:max_units].decode("utf-8", errors="ignore")


def _truncate_context_block(text: str, limit: int) -> str:
    if _budget_units(text) <= limit:
        return text
    if limit <= 0:
        return ""
    marker = _CONTEXT_TRUNCATION_MARKER
    marker_units = _budget_units(marker)
    if limit <= marker_units:
        return _utf8_prefix(text, limit)
    prefix = _utf8_prefix(text, limit - marker_units).rstrip()
    while prefix and _budget_units(prefix + marker) > limit:
        prefix = prefix[:-1]
    return prefix + marker


def _fit_context_blocks(
    blocks: list[tuple[str, str, float]],
    *,
    tier: str,
    required_full_names: set[str] | None = None,
) -> tuple[str, dict[str, object], list[str]]:
    """Fit named prompt blocks into a conservative whole-context budget."""
    if tier not in TOTAL_CONTEXT_TOKEN_CAPS:
        raise ValueError(f"unknown context tier: {tier!r}")

    present = [(name, text, share) for name, text, share in blocks if text]
    token_cap = TOTAL_CONTEXT_TOKEN_CAPS[tier]
    separator_units = max(0, len(present) - 1) * _budget_units("\n\n")
    payload_cap = max(0, token_cap - separator_units)

    required_full_names = required_full_names or set()
    required_units = sum(
        _budget_units(block_text)
        for name, block_text, _share in present
        if name in required_full_names
    )
    if required_units > payload_cap:
        names = ", ".join(sorted(required_full_names)) or "required context"
        raise SelectedSkillTooLargeError(
            f"Selected skill instructions cannot fit the {tier} context budget ({names})"
        )

    allocations: list[int] = [0] * len(present)
    remaining_cap = payload_cap - required_units
    flexible_share = sum(
        share for name, _block_text, share in present if name not in required_full_names
    )
    for index, (name, block_text, share) in enumerate(present):
        if name in required_full_names:
            allocations[index] = _budget_units(block_text)
            continue
        if remaining_cap <= 0 or flexible_share <= 0:
            allocations[index] = 0
            continue
        soft_cap = max(1, int(remaining_cap * (share / flexible_share)))
        allocations[index] = min(_budget_units(block_text), soft_cap)

    leftover = max(0, payload_cap - sum(allocations))
    for index, (name, block_text, _share) in enumerate(present):
        if leftover <= 0:
            break
        if name in required_full_names:
            continue
        missing = _budget_units(block_text) - allocations[index]
        if missing <= 0:
            continue
        extra = min(missing, leftover)
        allocations[index] += extra
        leftover -= extra

    rendered: list[str] = []
    evidence_blocks: list[dict[str, object]] = []
    warnings: list[str] = []
    for (name, block_text, _share), allocation in zip(present, allocations):
        original_units = _budget_units(block_text)
        clipped = allocation < original_units
        rendered_text = _truncate_context_block(block_text, allocation)
        included_units = _budget_units(rendered_text)
        rendered.append(rendered_text)
        evidence_blocks.append(
            {
                "name": name,
                "original_chars": len(block_text),
                "included_chars": len(rendered_text),
                "original_token_upper_bound": original_units,
                "included_token_upper_bound": included_units,
                "truncated": clipped,
            }
        )
        if clipped:
            warnings.append(
                f"context_budget:{name}: clipped {original_units} -> {included_units} utf8-byte token upper bound"
            )

    system = _join_blocks(*rendered)
    evidence: dict[str, object] = {
        "tier": tier,
        "total_token_cap": token_cap,
        "budget_unit": "utf8_bytes_upper_bound",
        "system_chars": len(system),
        "system_token_upper_bound": _budget_units(system),
        "blocks": evidence_blocks,
    }
    return system, evidence, warnings


def _reconcile_memory_evidence(
    items: list[MemoryEvidence], rendered_prompt: str
) -> list[MemoryEvidence]:
    """Keep only whole memory records that actually appear in prompt order."""
    visible: list[MemoryEvidence] = []
    cursor = 0
    for item in items:
        memory_text = item.get("text", "")
        if not memory_text:
            continue
        index = rendered_prompt.find(memory_text, cursor)
        if index < 0:
            break
        visible.append(item)
        cursor = index + len(memory_text)
    return visible

async def assemble_context(
    message: str,
    parts_mode: bool = False,
    domain: str | None = None,
    deps: _AssemblerDeps | None = None,
    objective: str | None = None,
    tier: str = "standard",
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
        objective: Optional per-thread goal. When set, a ``Thread goal:``
            line is injected into the system prompt. When ``None`` the
            assembled output is byte-identical to pre-packet behaviour.
        tier: Per-tier context budget and enrichment control.
            ``trivial`` (300 tokens, no enrichments),
            ``standard`` (1200 tokens, full enrichments — the default,
            byte-identical to pre-packet behaviour),
            ``deep`` (2400 tokens, full enrichments).
    """
    deps = deps or _AssemblerDeps()
    warnings: list[str] = []

    domain_block = _domain_prompt(message, domain)
    if parts_mode or _should_surface_parts(message):
        domain_block = _build_parts_system_prompt(domain_block)

    objective_block = f"Thread goal: {objective}" if objective else ""
    personality = personality_block()
    user_block = user_context.load_user_context()
    hint_fn = deps.skill_hint_fn or _default_skill_hint
    explicit_skill_name = _explicit_skill_name(message) if deps.skill_hint_fn is None else None
    hint = hint_fn(message)
    selected_skill_block = hint if explicit_skill_name and hint else None

    # Trivial chats are deliberately context-light. The classifier has already
    # established that historical memory cannot materially improve this turn,
    # so querying every memory store here would only add latency and possible
    # failure surface. Standard/deep retain the existing graph retrieval path.
    memory_items: list[Item] = []
    injected_memory_items: list[MemoryEvidence] = []
    memory_block = ""

    if tier != "trivial":
        graph = deps.graph_cls(deps.adapters)
        graph_result = await graph.search_all(message)
        warnings.extend(f"memory_graph:{err}" for err in graph_result.errors)

        cap = 2400 if tier == "deep" else CONTEXT_TOKEN_CAP
        filtered_results = _filter_items_by_policy(graph_result.results, message)
        memory_sections, injected_memory_items = _select_unified_items(
            filtered_results, cap
        )
        memory_block = "\n\n".join(memory_sections)
        memory_items = _flatten_items(graph_result.results)

    if tier == "trivial":
        enrichment_blocks: list[str] = []
        enrichment_warnings: list[str] = []
    else:
        enrichment_blocks, enrichment_warnings = await run_enrichments(deps.enrichments, message)
    warnings.extend(enrichment_warnings)

    source_degradation = _degraded_sources(warnings)
    if source_degradation:
        # Put reliability truth first inside the domain block so ordinary
        # tail-clipping cannot erase the fact that context was partial.
        domain_block = _join_blocks(
            _context_degradation_marker(source_degradation), domain_block
        )

    enrichment_share = _CONTEXT_BLOCK_SHARES["enrichments"]
    each_enrichment_share = (
        enrichment_share / len(enrichment_blocks) if enrichment_blocks else 0.0
    )
    context_blocks: list[tuple[str, str, float]] = []
    # An explicit selection is user intent, not a suggestion. Put it first so
    # later final-message prefix fitting cannot silently discard it, and reserve
    # its complete instructions at this layer.
    if selected_skill_block:
        context_blocks.append(("skill", hint, _CONTEXT_BLOCK_SHARES["skill"]))
    context_blocks.extend([
        ("domain", domain_block, _CONTEXT_BLOCK_SHARES["domain"]),
        ("objective", objective_block, _CONTEXT_BLOCK_SHARES["objective"]),
        ("personality", personality, _CONTEXT_BLOCK_SHARES["personality"]),
        ("user_context", user_block, _CONTEXT_BLOCK_SHARES["user_context"]),
    ])
    if not selected_skill_block:
        context_blocks.append(("skill", hint, _CONTEXT_BLOCK_SHARES["skill"]))
    context_blocks.append(("memory", memory_block, _CONTEXT_BLOCK_SHARES["memory"]))
    context_blocks.extend(
        (f"enrichment:{index}", block, each_enrichment_share)
        for index, block in enumerate(enrichment_blocks)
    )
    system, budget_evidence, _budget_warnings = _fit_context_blocks(
        context_blocks,
        tier=tier,
        required_full_names={"skill"} if selected_skill_block else None,
    )
    budget_evidence["truncations"] = list(_budget_warnings)
    warnings.extend(_budget_warnings)
    injected_memory_items = _reconcile_memory_evidence(injected_memory_items, system)

    return ContextBundle(
        system=system,
        memory_items=memory_items,
        live_blocks=list(enrichment_blocks),
        warnings=warnings,
        injected_memory_items=injected_memory_items,
        context_budget=budget_evidence,
        selected_skill_block=selected_skill_block,
        context_health=_context_health(warnings),
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
    call this after `assemble_context`. The base function never raises
    so a partial result is always available; the route layer decides when
    "total failure" is fatal.
    """
    if _looks_like_total_failure(bundle):
        raise RuntimeError(
            f"context assembler: total infrastructure failure (warnings={bundle.warnings!r})"
        )
    return bundle


async def get_system_prompt(
    message: str,
    parts_mode: bool = False,
    domain: Optional[str] = None,
    objective: str | None = None,
    tier: str = "standard",
) -> str:
    """Return the joined system prompt string.

    Equivalent to `(await assemble_context(..., objective=objective, tier=tier)).system`.
    Kept as a convenience wrapper for callers that only need the system string.
    """
    if objective is None:
        bundle = await assemble_context(message, parts_mode=parts_mode, domain=domain, tier=tier)
    else:
        bundle = await assemble_context(
            message, parts_mode=parts_mode, domain=domain, objective=objective, tier=tier
        )
    return bundle.system


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


__all__ = [
    "ContextBundle",
    "SkillHintFn",
    "SkillSelectionError",
    "SelectedSkillTooLargeError",
    "assemble_context",
    "assert_not_total_failure",
    "get_system_prompt",
    "build_worker_context",
]
