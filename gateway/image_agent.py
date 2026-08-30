"""Bounded image-specialist controller (issue #336, slice A3).

A1 gave the conversation a memory and A2 gave the plan a durable identity, but
nothing turned "keep his face, make his build broader" into a validated
operation. This module is that step: a bounded LLM loop that reads the session,
picks one intent, and returns a validated decision.

Boundaries:
- The model chooses intent. It never mutates job state. This module persists an
  approved plan (A2's store) and records the turn; dispatch stays with
  ``image_runner`` via the caller, so a decision can be inspected before any
  renderer or GPU is touched.
- The loop is bounded at ``MAX_ROUNDS`` LLM calls. Read-only tools consume a
  round like anything else, and exhausting the budget without a terminal action
  raises. There is no unbounded ReAct loop and no "one more round" escape.
- Every failure is loud. Malformed output, an unknown reference, an unsupported
  operation, a renderer that cannot actually edit, and a spent budget each raise
  a distinct error. Returning a plausible-looking plan built on a reference the
  session does not own is the exact failure issue #336 exists to prevent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from gateway import paths as _paths

MAX_ROUNDS = 3

#: Workflow bundle that makes a real reference-conditioned edit possible. Until
#: A4 adds and hash-pins it, the worker only exposes text-to-image, and an
#: "edit" would be a fresh reroll wearing the language of an edit.
EDIT_WORKFLOW_ID = "image_to_image_v1"

_WORKFLOWS_DIR = _paths.ROOT / "workflows"

_TERMINAL_ACTIONS = {"generate", "edit", "cancel", "clarify"}

#: Exact key set each action accepts. An unexpected key is malformed output,
#: not a field to ignore — a silently dropped "denoise" reads as an honoured one.
_ACTION_FIELDS: dict[str, tuple[set[str], set[str]]] = {
    # action: (required, optional)
    "list_assets": (set(), set()),
    "get_guidance": ({"tag"}, set()),
    "inspect_anchor": (set(), set()),
    "generate": (
        {"prompt", "summary"},
        {"character_id", "recipe_id", "guidance_tags"},
    ),
    "edit": (
        {"prompt", "summary"},
        {
            "anchor_job_id",
            "protected_traits",
            "requested_changes",
            "recipe_id",
            "guidance_tags",
        },
    ),
    "cancel": ({"reason"}, set()),
    "clarify": ({"question"}, set()),
}

_SYSTEM_PROMPT = """You are Kitty's image specialist. You turn a natural request into exactly one validated action.

Reply with a single JSON object and nothing else. No prose, no markdown, no code fences.

Read-only actions (you may use these to gather context; each one costs a round):
  {"action": "list_assets"}
  {"action": "get_guidance", "tag": "<one available guidance tag>"}
  {"action": "inspect_anchor"}

Final actions (choose exactly one to finish):
  {"action": "generate", "prompt": "<full render prompt>", "summary": "<one sentence for the user>",
   "character_id": "<optional, must be in the session registry>",
   "recipe_id": "<optional>", "guidance_tags": ["<optional available tags>"]}
  {"action": "edit", "prompt": "<full render prompt>", "summary": "<one sentence for the user>",
   "protected_traits": ["<what must not change>"], "requested_changes": ["<what should change>"],
   "anchor_job_id": "<optional, must be the session's current anchor>",
   "recipe_id": "<optional>", "guidance_tags": ["<optional available tags>"]}
  {"action": "cancel", "reason": "<why this cannot or should not run>"}
  {"action": "clarify", "question": "<the one question that unblocks you>"}

Rules:
- Use "edit" only when the request builds on the currently selected result. Use "generate" otherwise.
- Never invent an id. Only ids listed in the session registry exist.
- Include no keys beyond those listed for your chosen action.
- Lists must not repeat an entry.
- If the request is ambiguous in a way that changes the image, ask with "clarify" instead of guessing.
- Content lane: every request this agent decides is the safe lane. There is no
  way to declare private_adult, a consent basis, or an adult confirmation from
  text, and no keyword in a prompt changes the lane. Those fields are set by
  the approved plan only, never by the agent.
"""


class ImageAgentError(RuntimeError):
    """Raised when the controller cannot produce a safe decision."""


class AgentProtocolError(ImageAgentError):
    """Raised when model output is not a valid, fully-specified action."""


class AgentLoopExhaustedError(ImageAgentError):
    """Raised when MAX_ROUNDS passed without the model committing to an action."""


class UnknownReferenceError(ImageAgentError):
    """Raised when an action names an id the session does not own."""


class UnsupportedOperationError(ImageAgentError):
    """Raised when the requested operation cannot apply to this session."""


class CapabilityError(ImageAgentError):
    """Raised when no renderer can actually perform the requested operation."""


class BudgetRefusedError(ImageAgentError):
    """Raised when a session has spent its attempt or cost allowance."""


@dataclass(frozen=True)
class AgentBudget:
    """Per-session ceiling on render work the controller may authorise."""

    max_attempts: int = 12
    max_spend_usd: float = 5.0


@dataclass
class AgentDecision:
    """The controller's single validated outcome for one user request."""

    action: str
    session_id: str
    rounds_used: int
    summary: str = ""
    plan_id: str | None = None
    plan: dict[str, Any] | None = None
    operation: str | None = None
    recipe_id: str | None = None
    anchor_job_id: str | None = None
    protected_traits: list[str] = field(default_factory=list)
    requested_changes: list[str] = field(default_factory=list)
    guidance_tags: list[str] = field(default_factory=list)
    question: str | None = None
    reason: str | None = None
    observations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "session_id": self.session_id,
            "rounds_used": self.rounds_used,
            "summary": self.summary,
            "plan_id": self.plan_id,
            "plan": self.plan,
            "operation": self.operation,
            "recipe_id": self.recipe_id,
            "anchor_job_id": self.anchor_job_id,
            "protected_traits": list(self.protected_traits),
            "requested_changes": list(self.requested_changes),
            "guidance_tags": list(self.guidance_tags),
            "question": self.question,
            "reason": self.reason,
            "observations": list(self.observations),
        }


def _default_llm(messages: list[dict[str, str]]) -> str:
    from gateway.llm_client import call_llm

    return call_llm(
        messages,
        max_tokens=900,
        temperature=0.1,
        response_format={"type": "json_object"},
        operation="image.agent",
    )


def _parse_action(raw: str) -> dict[str, Any]:
    """Parse one model turn into a fully-specified action, or raise.

    Strict on purpose: no code-fence stripping, no unknown-key tolerance, no
    defaulting of a missing field. A half-understood action renders a real image
    and bills a real GPU, so an unparseable turn has to stop the loop.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentProtocolError(
            f"model response was not valid JSON: {raw[:200]!r}"
        ) from exc

    if not isinstance(parsed, dict):
        raise AgentProtocolError(
            f"model response must be a JSON object, got {type(parsed).__name__}"
        )

    action = parsed.get("action")
    if not isinstance(action, str) or not action.strip():
        raise AgentProtocolError(f"model response has no action: {raw[:200]!r}")
    action = action.strip()

    if action not in _ACTION_FIELDS:
        raise AgentProtocolError(
            f"unknown action {action!r}; expected one of "
            f"{', '.join(sorted(_ACTION_FIELDS))}"
        )

    required, optional = _ACTION_FIELDS[action]
    supplied = set(parsed) - {"action"}
    missing = required - supplied
    if missing:
        raise AgentProtocolError(
            f"action {action!r} is missing required field(s): {', '.join(sorted(missing))}"
        )
    unexpected = supplied - required - optional
    if unexpected:
        raise AgentProtocolError(
            f"action {action!r} has unexpected field(s): {', '.join(sorted(unexpected))}"
        )
    return parsed


def _require_text(payload: dict[str, Any], key: str, action: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AgentProtocolError(
            f"action {action!r} field {key!r} must be a non-empty string"
        )
    return value.strip()


def _require_list(payload: dict[str, Any], key: str, action: str) -> list[str]:
    """Read an optional string list, rejecting non-strings, blanks, and repeats."""
    value = payload.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise AgentProtocolError(
            f"action {action!r} field {key!r} must be a list, got {type(value).__name__}"
        )
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise AgentProtocolError(
                f"action {action!r} field {key!r} must contain only non-empty strings"
            )
        text = item.strip()
        if text in cleaned:
            raise AgentProtocolError(
                f"action {action!r} field {key!r} repeats entry {text!r}"
            )
        cleaned.append(text)
    return cleaned


def _optional_id(payload: dict[str, Any], key: str, action: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AgentProtocolError(
            f"action {action!r} field {key!r} must be a non-empty string when supplied"
        )
    return value.strip()


def session_registry(session: Any) -> dict[str, list[str]]:
    """Every id this session owns, grouped by kind.

    This is the whole universe of references the model may name. Anything else
    is a hallucination, and resolving it would attach someone else's face to
    Jacob's render.
    """
    from gateway import image_sessions

    characters = [session.character_id] if session.character_id else []
    jobs = [j.job_id for j in image_sessions.list_session_jobs(session.session_id)]
    return {
        "characters": characters,
        "references": list(session.reference_ids),
        "jobs": jobs,
        "anchor": [session.anchor_job_id] if session.anchor_job_id else [],
    }


def _check_budget(session: Any, budget: AgentBudget, action: str) -> None:
    if session.attempt_count >= budget.max_attempts:
        raise BudgetRefusedError(
            f"session {session.session_id!r} has used {session.attempt_count} of "
            f"{budget.max_attempts} allowed attempts; {action} refused"
        )
    if session.spend_usd >= budget.max_spend_usd:
        raise BudgetRefusedError(
            f"session {session.session_id!r} has spent ${session.spend_usd:.2f} of its "
            f"${budget.max_spend_usd:.2f} allowance; {action} refused"
        )


def edit_workflow_available() -> bool:
    """Whether a real reference-conditioned edit can be rendered at all.

    The worker binds workflows by bundle directory, so the presence of the
    bundle is the honest local signal. A4 adds it; until then an edit must
    fail here rather than silently downgrade to a text-to-image reroll.
    """
    return (_WORKFLOWS_DIR / EDIT_WORKFLOW_ID).is_dir()


def _route_recipe(
    *,
    has_character: bool,
    preferred_recipe: str | None,
    operation: str,
    quality_tier: str,
    identity_mode: str,
) -> Any:
    from gateway import image_recipes

    try:
        decision = image_recipes.auto_route(
            has_character=has_character,
            character_count=1 if has_character else 0,
            quality_tier=quality_tier,
            identity_mode=identity_mode,
            operation=operation,
            preferred_recipe=preferred_recipe,
        )
    except image_recipes.RecipeError as exc:
        raise CapabilityError(str(exc)) from exc

    recipe = decision.recipe
    # auto_route does not filter on operation, so the img2img capability has to
    # be asserted here or an edit routes to a text-only recipe.
    if operation == "img2img" and (recipe is None or not recipe.supports_img2img):
        raise CapabilityError(
            f"recipe {decision.recipe_id!r} does not support img2img; "
            "no available recipe can perform a reference-conditioned edit"
        )
    return decision


def _build_and_persist_plan(
    session_id: str,
    prompt: str,
    *,
    character_id: str | None,
    recipe_id: str | None,
    guidance_tags: list[str],
    operation: str,
    anchor_job_id: str | None,
    requested_changes: list[str] | None = None,
    protected_traits: list[str] | None = None,
) -> Any:
    from gateway.image_plan import ImagePlanError, build_image_plan
    from gateway.image_plans import PlanStoreError, persist_plan

    try:
        plan = build_image_plan(
            prompt,
            character_id=character_id,
            recipe_id=recipe_id,
            guidance_tags=guidance_tags,
            operation=operation,
            requested_changes=requested_changes,
            protected_traits=protected_traits,
        )
    except ImagePlanError as exc:
        raise UnsupportedOperationError(str(exc)) from exc

    try:
        stored = persist_plan(
            session_id, plan, operation=operation, anchor_job_id=anchor_job_id
        )
    except PlanStoreError as exc:
        raise UnsupportedOperationError(str(exc)) from exc
    return stored


def _observe_list_assets(session: Any) -> str:
    from gateway import image_guidance, image_sessions

    registry = session_registry(session)
    jobs = image_sessions.list_session_jobs(session.session_id)
    return json.dumps(
        {
            "registry": registry,
            "jobs": [
                {"job_id": j.job_id, "status": j.status.value, "prompt": j.prompt}
                for j in jobs
            ],
            "protected_traits": session.protected_traits,
            "requested_changes": session.requested_changes,
            "available_guidance_tags": image_guidance.available_guidance_tags(),
        }
    )


def _observe_guidance(tag: str) -> str:
    from gateway.image_guidance import available_guidance_tags, get_guidance

    content = get_guidance(tag)
    if content is None:
        raise UnknownReferenceError(
            f"unknown guidance tag {tag!r}; available: "
            f"{', '.join(available_guidance_tags())}"
        )
    return content


def _observe_anchor(session: Any) -> str:
    from gateway import image_jobs

    if not session.anchor_job_id:
        return json.dumps({"anchor": None, "reason": "no result selected yet"})
    job = image_jobs.get_job(session.anchor_job_id)
    if job is None:
        raise UnknownReferenceError(
            f"session anchor {session.anchor_job_id!r} no longer exists"
        )
    return json.dumps(
        {
            "anchor": {
                "job_id": job.job_id,
                "artifact_id": session.anchor_artifact_id,
                "status": job.status.value,
                "prompt": job.prompt,
                "provider": job.provider,
            },
            "edit_workflow_available": edit_workflow_available(),
        }
    )


def _decide_generate(
    payload: dict[str, Any], session: Any, budget: AgentBudget, rounds: int
) -> AgentDecision:
    _check_budget(session, budget, "generate")

    prompt = _require_text(payload, "prompt", "generate")
    summary = _require_text(payload, "summary", "generate")
    guidance_tags = _require_list(payload, "guidance_tags", "generate")
    recipe_id = _optional_id(payload, "recipe_id", "generate")
    character_id = _optional_id(payload, "character_id", "generate")

    if character_id is not None:
        registry = session_registry(session)
        if character_id not in registry["characters"] + registry["references"]:
            raise UnknownReferenceError(
                f"character {character_id!r} is not in session "
                f"{session.session_id!r}; known: {registry}"
            )

    decision = _route_recipe(
        has_character=bool(character_id),
        preferred_recipe=recipe_id,
        operation="txt2img",
        quality_tier="quality",
        identity_mode="balanced",
    )
    stored = _build_and_persist_plan(
        session.session_id,
        prompt,
        character_id=character_id,
        recipe_id=decision.recipe_id,
        guidance_tags=guidance_tags,
        operation="txt2img",
        anchor_job_id=None,
    )
    return AgentDecision(
        action="generate",
        session_id=session.session_id,
        rounds_used=rounds,
        summary=summary,
        plan_id=stored.plan_id,
        plan=stored.to_dict(),
        operation="txt2img",
        recipe_id=decision.recipe_id,
        guidance_tags=guidance_tags,
    )


def _decide_edit(
    payload: dict[str, Any], session: Any, budget: AgentBudget, rounds: int
) -> AgentDecision:
    _check_budget(session, budget, "edit")

    prompt = _require_text(payload, "prompt", "edit")
    summary = _require_text(payload, "summary", "edit")
    guidance_tags = _require_list(payload, "guidance_tags", "edit")
    protected_traits = _require_list(payload, "protected_traits", "edit")
    requested_changes = _require_list(payload, "requested_changes", "edit")
    recipe_id = _optional_id(payload, "recipe_id", "edit")
    anchor_job_id = _optional_id(payload, "anchor_job_id", "edit")

    if not session.anchor_job_id:
        raise UnsupportedOperationError(
            f"session {session.session_id!r} has no selected result to edit from; "
            "select a result first or generate a new image"
        )
    # The model reads the anchor, it does not choose one. Naming a different job
    # means it is editing something the user never selected.
    if anchor_job_id is not None and anchor_job_id != session.anchor_job_id:
        raise UnknownReferenceError(
            f"anchor {anchor_job_id!r} is not the current anchor of session "
            f"{session.session_id!r} ({session.anchor_job_id!r})"
        )

    if not edit_workflow_available():
        raise CapabilityError(
            f"no {EDIT_WORKFLOW_ID!r} workflow bundle is installed, so the "
            "renderer cannot consume the selected image as an input; a "
            "text-to-image reroll is not an edit"
        )

    decision = _route_recipe(
        has_character=bool(session.character_id),
        preferred_recipe=recipe_id,
        operation="img2img",
        quality_tier="quality",
        identity_mode="balanced",
    )
    stored = _build_and_persist_plan(
        session.session_id,
        prompt,
        character_id=session.character_id,
        recipe_id=decision.recipe_id,
        guidance_tags=guidance_tags,
        operation="img2img",
        anchor_job_id=session.anchor_job_id,
        requested_changes=requested_changes,
        protected_traits=protected_traits,
    )
    return AgentDecision(
        action="edit",
        session_id=session.session_id,
        rounds_used=rounds,
        summary=summary,
        plan_id=stored.plan_id,
        plan=stored.to_dict(),
        operation="img2img",
        recipe_id=decision.recipe_id,
        anchor_job_id=session.anchor_job_id,
        protected_traits=protected_traits,
        requested_changes=requested_changes,
        guidance_tags=guidance_tags,
    )


def _persist_decision(session_id: str, decision: AgentDecision) -> None:
    """Record the outcome on the session so a restart resumes with it."""
    from gateway import image_sessions

    updates: dict[str, Any] = {}
    if decision.plan is not None:
        updates["last_plan"] = decision.plan
    if decision.protected_traits:
        updates["protected_traits"] = decision.protected_traits
    if decision.requested_changes:
        updates["requested_changes"] = decision.requested_changes
    if updates:
        image_sessions.update_session(session_id, **updates)

    spoken = decision.summary or decision.question or decision.reason
    image_sessions.append_turn(
        session_id, image_sessions.TurnRole.ASSISTANT, spoken
    )


def _build_context(session: Any) -> str:
    from gateway import image_guidance, image_sessions

    turns = image_sessions.list_turns(session.session_id)
    return json.dumps(
        {
            "session_id": session.session_id,
            "registry": session_registry(session),
            "anchor_job_id": session.anchor_job_id,
            "protected_traits": session.protected_traits,
            "requested_changes": session.requested_changes,
            "attempt_count": session.attempt_count,
            "spend_usd": session.spend_usd,
            "edit_workflow_available": edit_workflow_available(),
            "available_guidance_tags": image_guidance.available_guidance_tags(),
            "history": [
                {"role": t.role.value, "content": t.content, "job_id": t.job_id}
                for t in turns
            ],
        }
    )


def decide(
    session_id: str,
    request: str,
    *,
    budget: AgentBudget | None = None,
    llm: Callable[[list[dict[str, str]]], str] | None = None,
    max_rounds: int = MAX_ROUNDS,
) -> AgentDecision:
    """Turn one natural request into one validated action for *session_id*.

    Runs at most *max_rounds* model calls. Read-only actions feed an observation
    back and consume a round; the first terminal action is validated and
    returned. Raises rather than returning a partial or guessed decision.
    """
    from gateway import image_sessions

    if not request or not request.strip():
        raise ImageAgentError("request must not be empty")
    if max_rounds < 1:
        raise ImageAgentError(f"max_rounds must be at least 1, got {max_rounds}")

    budget = budget or AgentBudget()
    call = llm or _default_llm

    session = image_sessions.require_session(session_id)
    if session.status.is_terminal():
        raise UnsupportedOperationError(
            f"session {session_id!r} ended at {session.ended_at}; open a new session"
        )

    image_sessions.append_turn(
        session_id, image_sessions.TurnRole.USER, request.strip()
    )
    session = image_sessions.require_session(session_id)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Session context:\n{_build_context(session)}"},
        {"role": "user", "content": request.strip()},
    ]

    observations: list[str] = []
    for round_index in range(1, max_rounds + 1):
        raw = call(messages)
        payload = _parse_action(raw)
        action = payload["action"].strip()

        if action in _TERMINAL_ACTIONS:
            decision = _finalize(payload, action, session, budget, round_index)
            decision.observations = observations
            _persist_decision(session_id, decision)
            return decision

        observation = _run_read_action(payload, action, session)
        observations.append(f"{action}: {observation}")
        messages.append({"role": "assistant", "content": raw})
        messages.append(
            {"role": "user", "content": f"Observation for {action}:\n{observation}"}
        )

    raise AgentLoopExhaustedError(
        f"image agent used all {max_rounds} rounds for session {session_id!r} "
        f"without committing to an action; observations: {observations}"
    )


def _run_read_action(payload: dict[str, Any], action: str, session: Any) -> str:
    if action == "list_assets":
        return _observe_list_assets(session)
    if action == "get_guidance":
        return _observe_guidance(_require_text(payload, "tag", action))
    if action == "inspect_anchor":
        return _observe_anchor(session)
    raise AgentProtocolError(f"unroutable read action {action!r}")


def _finalize(
    payload: dict[str, Any],
    action: str,
    session: Any,
    budget: AgentBudget,
    rounds: int,
) -> AgentDecision:
    if action == "generate":
        return _decide_generate(payload, session, budget, rounds)
    if action == "edit":
        return _decide_edit(payload, session, budget, rounds)
    if action == "cancel":
        reason = _require_text(payload, "reason", action)
        return AgentDecision(
            action="cancel",
            session_id=session.session_id,
            rounds_used=rounds,
            summary=reason,
            reason=reason,
        )
    if action == "clarify":
        question = _require_text(payload, "question", action)
        return AgentDecision(
            action="clarify",
            session_id=session.session_id,
            rounds_used=rounds,
            summary=question,
            question=question,
        )
    raise AgentProtocolError(f"unroutable terminal action {action!r}")
