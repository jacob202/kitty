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

def _pricing_model(model: str) -> str:
    prefix = "openrouter/"
    return model[len(prefix) :] if model.startswith(prefix) else model


def _projected_attempt_cost_cad(governor_route: str, worker_model: str, reviewer_model: str) -> float:
    shape = cg.TYPICAL_PASS_TOKENS[governor_route]
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
    return worker_cost + reviewer_cost


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
    projected = _projected_attempt_cost_cad(governor_route, worker_model, reviewer_model)
    if projected > ceiling:
        raise PaidRoutingError(
            f"paid route {tier!r} projects CAD {projected:.4f} per attempt, "
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
    )
