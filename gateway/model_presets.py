"""Curated, evidence-honest model picker payloads.

The picker is a read-side view over Kitty's existing model-role policy and
provider discovery snapshot. It is not a second model registry and it never
promotes a discovered candidate into production routing.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from gateway.model_discovery import OPENROUTER_SNAPSHOT, ModelDiscoveryError, load_snapshot
from gateway.operating_policy import load_model_policy


class ModelPresetError(RuntimeError):
    """The picker cannot safely represent the configured model policy."""


def _nonnegative_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number


def _per_million(value: Any) -> float | None:
    number = _nonnegative_float(value)
    return None if number is None else number * 1_000_000


def _pricing(model: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = model.get("pricing") if isinstance(model, Mapping) else None
    raw = raw if isinstance(raw, Mapping) else {}
    prompt = _per_million(raw.get("prompt"))
    completion = _per_million(raw.get("completion"))
    state = "known" if prompt is not None or completion is not None else "unknown"
    return {
        "state": state,
        "input_usd_per_million": prompt,
        "output_usd_per_million": completion,
        "source": "provider discovery snapshot" if state == "known" else None,
    }


def _model_map(snapshot: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    rows = snapshot.get("models") if isinstance(snapshot, Mapping) else None
    if not isinstance(rows, list):
        return {}
    return {
        row["id"]: row
        for row in rows
        if isinstance(row, Mapping) and isinstance(row.get("id"), str)
    }


def _discovery(snapshot_path: Path) -> tuple[dict[str, Any], dict[str, Mapping[str, Any]]]:
    try:
        snapshot = load_snapshot(snapshot_path, allow_missing=True)
    except ModelDiscoveryError as exc:
        return ({"state": "stale_or_invalid", "reason": str(exc), "checked_at": None}, {})
    if snapshot is None:
        return (
            {
                "state": "missing",
                "reason": "no provider discovery snapshot is available; configured roles are still shown",
                "checked_at": None,
            },
            {},
        )
    return (
        {"state": "available", "reason": None, "checked_at": snapshot.get("checked_at")},
        _model_map(snapshot),
    )


def _candidate_payload(model: Mapping[str, Any], role_name: str) -> dict[str, Any]:
    suggested = model.get("suggested_roles")
    suggested = suggested if isinstance(suggested, list) else []
    return {
        "provider": "openrouter",
        "model": model.get("id"),
        "name": model.get("name") or model.get("id"),
        "context_length": model.get("context_length"),
        "input_modalities": model.get("input_modalities") or [],
        "output_modalities": model.get("output_modalities") or [],
        "supported_parameters": model.get("supported_parameters") or [],
        "pricing": _pricing(model),
        "role_signal": {
            "role": role_name,
            "matches": role_name in suggested,
            "basis": "Kitty-derived catalogue heuristic; not a quality benchmark",
        },
        "quality": {"state": "unknown", "reason": "no representative evaluation is attached"},
        "latency": {"state": "unknown", "reason": "no measured runtime observation is attached"},
    }


def _cheaper_alternatives(
    incumbent: Mapping[str, Any] | None,
    role_name: str,
    models: Mapping[str, Mapping[str, Any]],
    *,
    threshold: float,
    limit: int = 3,
) -> list[dict[str, Any]]:
    if not incumbent:
        return []
    incumbent_pricing = _pricing(incumbent)
    base_in = incumbent_pricing["input_usd_per_million"]
    base_out = incumbent_pricing["output_usd_per_million"]
    # A free incumbent has no meaningful percentage-saving denominator.
    if base_in is None or base_out is None or base_in <= 0 or base_out <= 0:
        return []

    candidates: list[tuple[float, Mapping[str, Any]]] = []
    for model in models.values():
        if model.get("id") == incumbent.get("id"):
            continue
        roles = model.get("suggested_roles")
        if not isinstance(roles, list) or role_name not in roles:
            continue
        price = _pricing(model)
        candidate_in = price["input_usd_per_million"]
        candidate_out = price["output_usd_per_million"]
        if candidate_in is None or candidate_out is None:
            continue
        input_saving = 1 - (candidate_in / base_in)
        output_saving = 1 - (candidate_out / base_out)
        if input_saving < threshold or output_saving < threshold:
            continue
        candidates.append((min(input_saving, output_saving), model))

    candidates.sort(key=lambda item: (-item[0], str(item[1].get("id"))))
    result: list[dict[str, Any]] = []
    for saving, model in candidates[:limit]:
        payload = _candidate_payload(model, role_name)
        payload["reason"] = (
            f"at least {round(saving * 100)}% cheaper on both input and output than the configured incumbent; "
            "quality and latency are unevaluated"
        )
        result.append(payload)
    return result


def _cost_threshold(model_policy: Mapping[str, Any]) -> float:
    evaluation = model_policy.get("evaluation")
    raw = evaluation.get("cost_reduction_required") if isinstance(evaluation, Mapping) else None
    if raw is None:
        raise ModelPresetError("model policy cost_reduction_required must be a number")
    try:
        threshold = float(raw)
    except (TypeError, ValueError) as exc:
        raise ModelPresetError("model policy cost_reduction_required must be a number") from exc
    if not math.isfinite(threshold) or threshold < 0 or threshold > 1:
        raise ModelPresetError("model policy cost_reduction_required must be between 0 and 1")
    return threshold


def build_model_picker(
    *,
    snapshot_path: Path = OPENROUTER_SNAPSHOT,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the small serious-choice set plus explicitly scoped alternatives."""
    model_policy = dict(policy or load_model_policy())
    roles = model_policy.get("roles")
    if not isinstance(roles, Mapping):
        raise ModelPresetError("model policy has no roles mapping")

    discovery, models = _discovery(snapshot_path)
    threshold = _cost_threshold(model_policy)
    presets: list[dict[str, Any]] = []

    for role_name, role in roles.items():
        if not isinstance(role, Mapping):
            continue
        incumbent = role.get("incumbent")
        incumbent = incumbent if isinstance(incumbent, Mapping) else None
        model_id = incumbent.get("model") if incumbent else None
        discovered = models.get(model_id) if isinstance(model_id, str) else None
        preset = {
            "role": role_name,
            "label": role.get("public_name") or role_name,
            "route": role.get("route"),
            "purpose": role.get("purpose"),
            "kind": role.get("kind"),
            "provider": incumbent.get("provider") if incumbent else None,
            "model": model_id,
            "configured": incumbent is not None or role.get("kind") == "router",
            "catalogue": _candidate_payload(discovered, role_name) if discovered else None,
            "catalogue_state": "matched" if discovered else ("not_applicable" if not model_id else "not_observed"),
            "alternatives": _cheaper_alternatives(discovered, role_name, models, threshold=threshold),
        }
        presets.append(preset)

    return {
        "schema_version": 1,
        "source": "config/model_roles.json + provider discovery snapshot",
        "discovery": discovery,
        "presets": presets,
        "claims": {
            "role_tags": "heuristic unless backed by representative evaluation",
            "alternatives": "cost-screened only; not quality-ranked",
        },
    }


__all__ = ["ModelPresetError", "build_model_picker"]
