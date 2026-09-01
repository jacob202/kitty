"""Explicit governed paid routes for KittyBuilder execution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from gateway import compute_governor as cg
from gateway.paths import CONFIG_DIR

PAID_ROUTES_PATH = CONFIG_DIR / "builder_paid_routes.json"
_REVIEW_TOKEN_SHAPE = {"input": 30_000, "output": 3_000}
_ALLOWED_TIERS = frozenset({"cheap", "frontier"})
_EXECUTION_TIERS = frozenset({"free", "cheap", "frontier"})
_TIER_RANK = {"free": 0, "cheap": 1, "frontier": 2}


class PaidRoutingError(ValueError):
    """Paid execution policy is missing, disabled, or unsafe."""


@dataclass(frozen=True)
class PaidRoute:
    tier: str
    provider: str
    worker_model: str
    reviewer_model: str
    governor_route: str
    projected_cost_cad: float
    max_projected_cost_cad: float
    worker_candidates: tuple[str, ...]
    reviewer_candidates: tuple[str, ...]


@dataclass(frozen=True)
class HandoffPlan:
    source_tier: str
    target_tier: str
    context_mode: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source_tier": self.source_tier,
            "target_tier": self.target_tier,
            "context_mode": self.context_mode,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class HarnessProfile:
    name: str
    workspace_mode: str
    context_strategy: str
    requires_validation: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "workspace_mode": self.workspace_mode,
            "context_strategy": self.context_strategy,
            "requires_validation": self.requires_validation,
        }


@dataclass(frozen=True)
class ExecutionRoutingPlan:
    tier: str
    provider: str
    worker_candidates: tuple[str, ...]
    reviewer_candidates: tuple[str, ...]
    projected_cost_cad: float
    max_projected_cost_cad: float
    handoff: HandoffPlan
    harness: HarnessProfile

    def to_policy_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "provider": self.provider,
            "worker_candidates": list(self.worker_candidates),
            "reviewer_candidates": list(self.reviewer_candidates),
            "projected_cost_cad": self.projected_cost_cad,
            "max_projected_cost_cad": self.max_projected_cost_cad,
            "handoff": self.handoff.to_dict(),
            "harness": self.harness.to_dict(),
        }


_HARNESS_PROFILES: dict[str, HarnessProfile] = {
    "coding": HarnessProfile(
        name="coding",
        workspace_mode="write",
        context_strategy="artifact_first",
        requires_validation=True,
    ),
    "research": HarnessProfile(
        name="research",
        workspace_mode="read_only",
        context_strategy="source_first",
        requires_validation=True,
    ),
    "review": HarnessProfile(
        name="review",
        workspace_mode="read_only",
        context_strategy="evidence_only",
        requires_validation=True,
    ),
    "recovery": HarnessProfile(
        name="recovery",
        workspace_mode="write",
        context_strategy="last_confirmed_state",
        requires_validation=True,
    ),
}
_TASK_CLASS_TO_HARNESS = {
    "implementation": "coding",
    "verified_repair": "coding",
    "code": "coding",
    "planning_pass": "research",
    "research": "research",
    "independent_review": "review",
    "review": "review",
    "recovery": "recovery",
    "resume": "recovery",
}

def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PaidRoutingError(f"paid route config missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PaidRoutingError(f"paid route config invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PaidRoutingError("paid route config root must be an object")
    return payload


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PaidRoutingError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PaidRoutingError(f"{label} must be a non-empty string")
    return value.strip()


def _positive_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise PaidRoutingError(f"{label} must be a positive number")
    return float(value)

def _fallback_models(value: Any, *, label: str, primary: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise PaidRoutingError(f"{label} fallback models must be a list")
    models: list[str] = []
    for raw in value:
        model = _text(raw, f"{label} fallback model")
        if not model.startswith("openrouter/"):
            raise PaidRoutingError(f"{label} fallback models must use OpenRouter model slugs")
        if model == primary or model in models:
            raise PaidRoutingError(f"{label} fallback contains a duplicate model {model!r}")
        models.append(model)
    return tuple(models)


def plan_handoff(source_tier: str, target_tier: str) -> HandoffPlan:
    """Return an evidence-aware context policy for a model-tier transition."""
    if source_tier not in _EXECUTION_TIERS:
        raise PaidRoutingError(
            f"unknown source tier {source_tier!r}; expected one of {sorted(_EXECUTION_TIERS)}"
        )
    if target_tier not in _EXECUTION_TIERS:
        raise PaidRoutingError(
            f"unknown target tier {target_tier!r}; expected one of {sorted(_EXECUTION_TIERS)}"
        )
    if source_tier == target_tier:
        return HandoffPlan(
            source_tier=source_tier,
            target_tier=target_tier,
            context_mode="continue",
            reason="same model tier; continue with the established bounded context",
        )
    if _TIER_RANK[source_tier] < _TIER_RANK[target_tier]:
        return HandoffPlan(
            source_tier=source_tier,
            target_tier=target_tier,
            context_mode="artifacts_compact",
            reason="escalation to a stronger tier: preserve durable artifacts and compact the weaker trajectory",
        )
    return HandoffPlan(
        source_tier=source_tier,
        target_tier=target_tier,
        context_mode="preserve_trajectory",
        reason="downshift from a stronger tier: preserve its useful trajectory for the cheaper worker",
    )


def select_harness_profile(task_class: str) -> HarnessProfile:
    key = _text(task_class, "task_class")
    profile_name = _TASK_CLASS_TO_HARNESS.get(key)
    if profile_name is None:
        raise PaidRoutingError(
            f"unknown task_class {key!r}; expected one of {sorted(_TASK_CLASS_TO_HARNESS)}"
        )
    return _HARNESS_PROFILES[profile_name]


def _pricing_model(model: str) -> str:
    prefix = "openrouter/"
    return model[len(prefix) :] if model.startswith(prefix) else model


def _projected_attempt_cost_cad(
    governor_route: str, worker_model: str, reviewer_model: str
) -> float:
    """Project one paid attempt from the *configured* model slugs.

    The worker pass keeps the governor's tier-sized token shape but is priced at
    the configured ``worker_model`` — not at the governor's hard-coded route
    model — so swapping the worker slug in the paid route config changes the
    projection. An unpriced slug is an error rather than a free ride: a silent
    zero would understate the spend-ceiling check below.
    """
    shape = cg.TYPICAL_PASS_TOKENS[governor_route]
    try:
        worker_cost = cg.estimate_cost_cad(
            _pricing_model(worker_model),
            input_tokens=shape["input"],
            output_tokens=shape["output"],
        )
        reviewer_cost = cg.estimate_cost_cad(
            _pricing_model(reviewer_model),
            input_tokens=_REVIEW_TOKEN_SHAPE["input"],
            output_tokens=_REVIEW_TOKEN_SHAPE["output"],
        )
    except cg.GovernorError as exc:
        raise PaidRoutingError(f"cannot project paid route cost: {exc}") from exc
    return worker_cost + reviewer_cost



def _projected_worker_cost_cad(governor_route: str, model: str) -> float:
    shape = cg.TYPICAL_PASS_TOKENS[governor_route]
    try:
        return cg.estimate_cost_cad(
            _pricing_model(model), input_tokens=shape["input"], output_tokens=shape["output"]
        )
    except cg.GovernorError as exc:
        raise PaidRoutingError(f"cannot project paid route cost: {exc}") from exc


def _projected_reviewer_cost_cad(model: str) -> float:
    try:
        return cg.estimate_cost_cad(
            _pricing_model(model),
            input_tokens=_REVIEW_TOKEN_SHAPE["input"],
            output_tokens=_REVIEW_TOKEN_SHAPE["output"],
        )
    except cg.GovernorError as exc:
        raise PaidRoutingError(f"cannot project paid route cost: {exc}") from exc

def resolve_paid_route(
    tier: str = "cheap", *, config_path: Path = PAID_ROUTES_PATH
) -> PaidRoute:
    """Resolve one explicit paid tier and fail closed on unsafe policy."""
    payload = _load(config_path)
    if payload.get("schema_version") != 1:
        raise PaidRoutingError("paid route schema_version must be 1")
    enabled = payload.get("paid_openrouter_enabled")
    if not isinstance(enabled, bool):
        raise PaidRoutingError("paid_openrouter_enabled must be boolean")
    if not enabled:
        raise PaidRoutingError("paid OpenRouter execution is disabled")
    if tier not in _ALLOWED_TIERS:
        raise PaidRoutingError(
            f"unknown paid tier {tier!r}; expected one of {sorted(_ALLOWED_TIERS)}"
        )
    routes = _mapping(payload.get("routes"), "paid routes")
    route = _mapping(routes.get(tier), f"paid route {tier!r}")
    provider = _text(route.get("provider"), f"paid route {tier!r}.provider")
    if provider != "openrouter":
        raise PaidRoutingError("paid Builder routes currently require provider 'openrouter'")
    worker_model = _text(
        route.get("worker_model"), f"paid route {tier!r}.worker_model"
    )
    reviewer_model = _text(
        route.get("reviewer_model"), f"paid route {tier!r}.reviewer_model"
    )
    if not worker_model.startswith("openrouter/") or not reviewer_model.startswith(
        "openrouter/"
    ):
        raise PaidRoutingError("paid worker/reviewer models must use OpenRouter model slugs")
    if worker_model == reviewer_model:
        raise PaidRoutingError("paid reviewer model must differ from the worker model")
    worker_fallbacks = _fallback_models(
        route.get("worker_fallback_models"),
        label=f"paid route {tier!r}.worker",
        primary=worker_model,
    )
    reviewer_fallbacks = _fallback_models(
        route.get("reviewer_fallback_models"),
        label=f"paid route {tier!r}.reviewer",
        primary=reviewer_model,
    )
    worker_candidates = (worker_model, *worker_fallbacks)
    reviewer_candidates = (reviewer_model, *reviewer_fallbacks)
    overlap = sorted(set(worker_candidates) & set(reviewer_candidates))
    if overlap:
        raise PaidRoutingError(
            f"paid reviewer candidates must remain independent from worker candidates; overlap={overlap}"
        )

    governor_route = _text(
        route.get("governor_route"), f"paid route {tier!r}.governor_route"
    )
    if governor_route != tier:
        raise PaidRoutingError(
            f"paid tier {tier!r} must map to governor route {tier!r}, got {governor_route!r}"
        )
    ceiling = _positive_number(
        route.get("max_projected_cad_per_attempt"),
        f"paid route {tier!r}.max_projected_cad_per_attempt",
    )
    # Candidates are tried sequentially, so reserve the worst case where every
    # worker fallback and every reviewer fallback is attempted once.
    projected = sum(
        _projected_worker_cost_cad(governor_route, worker) for worker in worker_candidates
    ) + sum(_projected_reviewer_cost_cad(reviewer) for reviewer in reviewer_candidates)
    if projected > ceiling:
        raise PaidRoutingError(
            f"paid route {tier!r} candidate set projects CAD {projected:.4f} per attempt, "
            f"above configured ceiling CAD {ceiling:.4f}"
        )
    return PaidRoute(
        tier=tier,
        provider=provider,
        worker_model=worker_model,
        reviewer_model=reviewer_model,
        governor_route=governor_route,
        projected_cost_cad=projected,
        max_projected_cost_cad=ceiling,
        worker_candidates=worker_candidates,
        reviewer_candidates=reviewer_candidates,
    )

def build_execution_routing_plan(
    tier: str,
    *,
    task_class: str,
    source_tier: str | None = None,
    config_path: Path = PAID_ROUTES_PATH,
) -> ExecutionRoutingPlan:
    """Combine paid-route truth with handoff and bounded harness policy."""
    route = resolve_paid_route(tier, config_path=config_path)
    source = tier if source_tier is None else source_tier
    return ExecutionRoutingPlan(
        tier=route.tier,
        provider=route.provider,
        worker_candidates=route.worker_candidates,
        reviewer_candidates=route.reviewer_candidates,
        projected_cost_cad=route.projected_cost_cad,
        max_projected_cost_cad=route.max_projected_cost_cad,
        handoff=plan_handoff(source, route.tier),
        harness=select_harness_profile(task_class),
    )
