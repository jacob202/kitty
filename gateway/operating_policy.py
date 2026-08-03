"""Executable operating contracts for model roles, image characters, and Builder.

These policies exist to stop a recurring failure mode: a label, table, or green
unit test being mistaken for a working product.  The functions in this module
make the missing decisions explicit and reject unsupported claims.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from gateway.paths import CONFIG_DIR

MODEL_POLICY_PATH = CONFIG_DIR / "model_roles.json"
BUILDER_POLICY_PATH = CONFIG_DIR / "builder_effectiveness.json"
CHARACTER_SCHEMA_PATH = CONFIG_DIR / "image_character_contract.schema.json"

_MODEL_ROLES = frozenset({"auto", "fast", "think", "code", "vision"})
_REFERENCE_PURPOSES = frozenset(
    {
        "primary_face",
        "secondary_face",
        "profile",
        "body_build",
        "hair",
        "expression",
        "style_only",
    }
)
_IDENTITY_METHODS = frozenset(
    {
        "description_only",
        "lora",
        "pulid",
        "instantid",
        "ipadapter_faceid",
        "trained_adapter",
    }
)
_FUSION_METHODS = frozenset({"single", "equal_mean", "weighted_mean", "concat", "max"})


class OperatingPolicyError(ValueError):
    """The supplied policy or measurement cannot support the advertised claim."""


@dataclass(frozen=True)
class PolicyDecision:
    status: str
    reasons: tuple[str, ...]
    missing_metrics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OperatingPolicyError(f"policy file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise OperatingPolicyError(f"policy file is invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise OperatingPolicyError(f"policy root must be an object: {path}")
    return payload


def load_model_policy(path: Path = MODEL_POLICY_PATH) -> dict[str, Any]:
    policy = _load_json(path)
    validate_model_policy(policy)
    return policy


def load_builder_policy(path: Path = BUILDER_POLICY_PATH) -> dict[str, Any]:
    policy = _load_json(path)
    validate_builder_policy(policy)
    return policy


def validate_model_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("schema_version") != 1:
        raise OperatingPolicyError("model policy schema_version must be 1")
    roles = policy.get("roles")
    if not isinstance(roles, Mapping):
        raise OperatingPolicyError("model policy roles must be an object")
    missing = sorted(_MODEL_ROLES - set(roles))
    if missing:
        raise OperatingPolicyError(f"model policy is missing roles: {missing}")

    routes: set[str] = set()
    concrete_models: set[tuple[str, str]] = set()
    for role_name in sorted(_MODEL_ROLES):
        role = roles[role_name]
        if not isinstance(role, Mapping):
            raise OperatingPolicyError(f"model role {role_name!r} must be an object")
        for field in ("kind", "public_name", "route", "purpose", "required_metrics"):
            if not role.get(field):
                raise OperatingPolicyError(f"model role {role_name!r} is missing {field}")
        route = str(role["route"])
        if route in routes and role_name != "auto":
            raise OperatingPolicyError(f"duplicate concrete model route: {route}")
        routes.add(route)

        incumbent = role.get("incumbent")
        if role_name == "auto":
            if incumbent is not None or role.get("kind") != "router":
                raise OperatingPolicyError("auto must be a router with no incumbent model")
            continue
        if not isinstance(incumbent, Mapping):
            raise OperatingPolicyError(f"model role {role_name!r} needs an incumbent")
        provider = str(incumbent.get("provider") or "")
        model = str(incumbent.get("model") or "")
        if not provider or not model:
            raise OperatingPolicyError(
                f"model role {role_name!r} incumbent needs provider and model"
            )
        key = (provider, model)
        if key in concrete_models:
            raise OperatingPolicyError(
                f"two concrete roles advertise the same incumbent: {provider}/{model}"
            )
        concrete_models.add(key)

    evaluation = policy.get("evaluation")
    if not isinstance(evaluation, Mapping):
        raise OperatingPolicyError("model policy evaluation must be an object")
    if int(evaluation.get("minimum_representative_tasks", 0)) < 1:
        raise OperatingPolicyError("minimum_representative_tasks must be positive")
    if int(evaluation.get("repeat_windows", 0)) < 1:
        raise OperatingPolicyError("repeat_windows must be positive")


def evaluate_model_candidate(
    role_name: str,
    incumbent: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
) -> PolicyDecision:
    """Decide whether a candidate may replace a role incumbent.

    Metrics are outcome-level, not token-price vanity metrics.  Required keys:
    sample_size, repeat_windows, accepted_outcome_rate,
    cost_per_accepted_outcome, median_time_to_accepted_outcome, malformed_rate,
    tool_success_rate, and critical_regressions.
    """

    loaded = dict(policy or load_model_policy())
    validate_model_policy(loaded)
    if role_name not in loaded["roles"] or role_name == "auto":
        raise OperatingPolicyError(f"{role_name!r} is not a promotable model role")

    required = {
        "sample_size",
        "repeat_windows",
        "accepted_outcome_rate",
        "cost_per_accepted_outcome",
        "median_time_to_accepted_outcome",
        "malformed_rate",
        "tool_success_rate",
        "critical_regressions",
    }
    missing = sorted(
        key for key in required if key not in incumbent or key not in candidate
    )
    if missing:
        return PolicyDecision("insufficient_evidence", (), tuple(missing))

    cfg = loaded["evaluation"]
    reasons: list[str] = []
    if int(candidate["sample_size"]) < int(cfg["minimum_representative_tasks"]):
        reasons.append("candidate sample is smaller than the required representative set")
    if int(candidate["repeat_windows"]) < int(cfg["repeat_windows"]):
        reasons.append("candidate was not reproduced across enough evaluation windows")
    if int(candidate["critical_regressions"]) > int(cfg["maximum_critical_regressions"]):
        reasons.append("candidate has a critical regression")
    if float(candidate["malformed_rate"]) > float(cfg["maximum_malformed_rate"]):
        reasons.append("candidate malformed-output rate is too high")
    tool_regression = float(incumbent["tool_success_rate"]) - float(
        candidate["tool_success_rate"]
    )
    if tool_regression > float(cfg["maximum_tool_success_regression"]):
        reasons.append("candidate tool success regressed beyond policy")

    incumbent_success = float(incumbent["accepted_outcome_rate"])
    candidate_success = float(candidate["accepted_outcome_rate"])
    success_delta = candidate_success - incumbent_success
    success_regression = incumbent_success - candidate_success
    quality_win = success_delta >= float(cfg["quality_improvement_required"])
    quality_parity = success_regression <= float(cfg["maximum_success_rate_regression"])

    incumbent_cost = float(incumbent["cost_per_accepted_outcome"])
    candidate_cost = float(candidate["cost_per_accepted_outcome"])
    cost_reduction = 0.0 if incumbent_cost <= 0 else 1 - (candidate_cost / incumbent_cost)

    incumbent_time = float(incumbent["median_time_to_accepted_outcome"])
    candidate_time = float(candidate["median_time_to_accepted_outcome"])
    latency_reduction = 0.0 if incumbent_time <= 0 else 1 - (candidate_time / incumbent_time)

    economic_win = quality_parity and cost_reduction >= float(
        cfg["cost_reduction_required"]
    )
    speed_win = quality_parity and latency_reduction >= float(
        cfg["latency_reduction_required"]
    )
    if not (quality_win or economic_win or speed_win):
        reasons.append(
            "candidate did not improve accepted outcomes, successful-outcome cost, "
            "or time-to-success enough to justify promotion"
        )

    return PolicyDecision("reject" if reasons else "promote", tuple(reasons))


def validate_builder_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("schema_version") != 1:
        raise OperatingPolicyError("Builder policy schema_version must be 1")
    tripwires = policy.get("tripwires")
    if not isinstance(tripwires, Mapping):
        raise OperatingPolicyError("Builder tripwires must be an object")
    required = {
        "maximum_campaign_elapsed_seconds",
        "maximum_current_packet_elapsed_seconds",
        "minimum_accepted_packets_per_hour",
        "maximum_consecutive_no_substantive_diff",
        "maximum_setup_metadata_fraction",
        "maximum_supervisor_to_worker_token_ratio",
        "maximum_reset_recovery_events",
        "maximum_repeated_systemic_blocker_count",
        "maximum_projected_vs_simple_baseline_ratio",
    }
    missing = sorted(required - set(tripwires))
    if missing:
        raise OperatingPolicyError(f"Builder policy is missing tripwires: {missing}")


def evaluate_builder_campaign(
    metrics: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
) -> PolicyDecision:
    """Pause a campaign that is durable but economically ineffective.

    Missing measurements are reported rather than fabricated.  A tripwire is
    evaluated only when its inputs are available.
    """

    loaded = dict(policy or load_builder_policy())
    validate_builder_policy(loaded)
    cfg = loaded["tripwires"]
    reasons: list[str] = []

    elapsed = _number(metrics.get("elapsed_seconds"))
    processed = _number(metrics.get("processed_packets"))
    accepted = _number(metrics.get("accepted_packets"))
    current = _number(metrics.get("current_packet_elapsed_seconds"))
    setup = _number(metrics.get("setup_metadata_seconds"))
    supervisor_tokens = _number(metrics.get("supervisor_tokens"))
    worker_tokens = _number(metrics.get("worker_tokens"))
    projected = _number(metrics.get("projected_completion_seconds"))
    baseline = _number(metrics.get("simple_baseline_seconds"))

    if elapsed is not None and elapsed > float(cfg["maximum_campaign_elapsed_seconds"]):
        reasons.append("campaign exceeded the maximum wall-clock budget")
    if current is not None and current > float(cfg["maximum_current_packet_elapsed_seconds"]):
        reasons.append("current packet exceeded the small-packet time budget")

    window = loaded.get("observation_window", {})
    if (
        elapsed is not None
        and processed is not None
        and accepted is not None
        and elapsed >= float(window.get("minimum_elapsed_seconds", 0))
        and processed >= float(window.get("minimum_processed_packets", 0))
    ):
        throughput = accepted / (elapsed / 3600) if elapsed > 0 else 0.0
        if throughput < float(cfg["minimum_accepted_packets_per_hour"]):
            reasons.append("accepted-packet throughput is below policy")

    no_diff = _number(metrics.get("consecutive_no_substantive_diff"))
    if no_diff is not None and no_diff >= float(
        cfg["maximum_consecutive_no_substantive_diff"]
    ):
        reasons.append("multiple consecutive attempts produced no substantive diff")

    if elapsed and setup is not None:
        if setup / elapsed > float(cfg["maximum_setup_metadata_fraction"]):
            reasons.append("setup and metadata work consume too much campaign time")

    if worker_tokens is not None and supervisor_tokens is not None and worker_tokens > 0:
        if supervisor_tokens / worker_tokens > float(
            cfg["maximum_supervisor_to_worker_token_ratio"]
        ):
            reasons.append("supervisor token use exceeds the worker budget")

    resets = _number(metrics.get("reset_recovery_events"))
    if resets is not None and resets >= float(cfg["maximum_reset_recovery_events"]):
        reasons.append("reset/recovery churn exceeded policy")

    blockers = _number(metrics.get("repeated_systemic_blocker_count"))
    if blockers is not None and blockers >= float(
        cfg["maximum_repeated_systemic_blocker_count"]
    ):
        reasons.append("the same systemic blocker repeated across packets")

    if projected is not None and baseline is not None and baseline > 0:
        if projected / baseline > float(cfg["maximum_projected_vs_simple_baseline_ratio"]):
            reasons.append("projected campaign time is worse than the simple-agent baseline")

    required = loaded.get("required_receipt_fields", [])
    missing = tuple(sorted(key for key in required if metrics.get(key) is None))
    return PolicyDecision("pause" if reasons else "continue", tuple(reasons), missing)


def validate_character_contract(character: Mapping[str, Any]) -> None:
    """Reject character records that cannot truthfully drive generation."""

    if character.get("schema_version") != 1:
        raise OperatingPolicyError("character schema_version must be 1")
    for field in ("character_id", "name", "description", "identity", "prompt", "recipe"):
        if field not in character:
            raise OperatingPolicyError(f"character is missing {field}")

    description = character["description"]
    if not isinstance(description, Mapping) or not str(
        description.get("appearance") or ""
    ).strip():
        raise OperatingPolicyError("character needs a non-empty appearance description")
    for field in ("preserve", "exclude"):
        if not isinstance(description.get(field), list):
            raise OperatingPolicyError(f"character description.{field} must be a list")

    identity = character["identity"]
    if not isinstance(identity, Mapping):
        raise OperatingPolicyError("character identity must be an object")
    method = identity.get("method")
    fusion = identity.get("fusion_method")
    if method not in _IDENTITY_METHODS:
        raise OperatingPolicyError(f"unsupported identity method: {method!r}")
    if fusion not in _FUSION_METHODS:
        raise OperatingPolicyError(f"unsupported fusion method: {fusion!r}")
    if not str(identity.get("base_family") or "").strip():
        raise OperatingPolicyError("character identity needs a base_family")

    references = identity.get("references")
    if not isinstance(references, list) or len(references) > 12:
        raise OperatingPolicyError("character references must be a list of at most 12")
    enabled = [ref for ref in references if isinstance(ref, Mapping) and ref.get("enabled")]
    if method == "description_only" and enabled:
        raise OperatingPolicyError("description_only characters cannot claim reference conditioning")
    if method != "description_only" and not enabled:
        raise OperatingPolicyError(f"identity method {method!r} needs an enabled reference")
    if fusion == "single" and len(enabled) != 1:
        raise OperatingPolicyError("single fusion requires exactly one enabled reference")

    seen: set[str] = set()
    primary_count = 0
    allow_generated = bool(identity.get("allow_generated_derivatives", False))
    total_weight = 0.0
    for ref in enabled:
        ref_id = str(ref.get("ref_id") or "")
        if not ref_id or ref_id in seen:
            raise OperatingPolicyError("enabled character references need unique ref_id values")
        seen.add(ref_id)
        purpose = ref.get("purpose")
        if purpose not in _REFERENCE_PURPOSES:
            raise OperatingPolicyError(f"unsupported reference purpose: {purpose!r}")
        if purpose == "primary_face":
            primary_count += 1
        provenance = ref.get("provenance")
        if provenance not in {"real_photo", "generated_derivative"}:
            raise OperatingPolicyError(f"unsupported reference provenance: {provenance!r}")
        if provenance == "generated_derivative" and not allow_generated:
            raise OperatingPolicyError(
                "generated derivative reference is disabled by the character policy"
            )
        for field in ("weight", "face_weight", "body_weight", "quality_score"):
            value = _number(ref.get(field))
            if value is None or not 0 <= value <= 1:
                raise OperatingPolicyError(f"reference {ref_id!r} {field} must be 0..1")
        total_weight += float(ref["weight"])
    if enabled and primary_count != 1:
        raise OperatingPolicyError("exactly one enabled primary_face reference is required")
    if fusion == "weighted_mean" and total_weight <= 0:
        raise OperatingPolicyError("weighted_mean requires a positive total reference weight")

    prompt = character["prompt"]
    if not isinstance(prompt, Mapping) or "positive" not in prompt or "negative" not in prompt:
        raise OperatingPolicyError("character prompt needs positive and negative fragments")
    recipe = character["recipe"]
    if not isinstance(recipe, Mapping) or not recipe.get("recipe_id") or not recipe.get("engine"):
        raise OperatingPolicyError("character recipe needs recipe_id and engine")


def resolve_character_for_engine(
    character: Mapping[str, Any], engine_capabilities: Mapping[str, Any]
) -> dict[str, Any]:
    """Return an execution recipe or fail instead of silently ignoring fields."""

    validate_character_contract(character)
    identity = character["identity"]
    method = identity["method"]
    fusion = identity["fusion_method"]
    supported_methods = set(engine_capabilities.get("identity_methods", []))
    supported_fusions = set(engine_capabilities.get("fusion_methods", []))
    max_refs = int(engine_capabilities.get("maximum_references", 0))
    enabled = [ref for ref in identity["references"] if ref.get("enabled")]

    if method not in supported_methods:
        raise OperatingPolicyError(
            f"engine cannot honor identity method {method!r}; refusing to ignore it"
        )
    if fusion not in supported_fusions:
        raise OperatingPolicyError(
            f"engine cannot honor fusion method {fusion!r}; refusing to weight references falsely"
        )
    if len(enabled) > max_refs:
        raise OperatingPolicyError(
            f"engine supports {max_refs} reference(s), character enables {len(enabled)}"
        )
    if any(ref["weight"] != 1 for ref in enabled) and not engine_capabilities.get(
        "per_reference_weights", False
    ):
        raise OperatingPolicyError(
            "engine cannot honor per-reference weights; refusing to pretend the sliders work"
        )

    appearance = str(character["description"]["appearance"]).strip()
    positive = str(character["prompt"]["positive"]).strip()
    negative = str(character["prompt"]["negative"]).strip()
    return {
        "character_id": character["character_id"],
        "name": character["name"],
        "engine": character["recipe"]["engine"],
        "recipe_id": character["recipe"]["recipe_id"],
        "base_family": identity["base_family"],
        "identity_method": method,
        "adapter_model": identity.get("adapter_model"),
        "adapter_strength": identity.get("adapter_strength", 1.0),
        "fusion_method": fusion,
        "references": enabled,
        "positive_prompt": ", ".join(part for part in (appearance, positive) if part),
        "negative_prompt": negative,
        "preserve": list(character["description"]["preserve"]),
        "exclude": list(character["description"]["exclude"]),
        "recipe": dict(character["recipe"]),
    }


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "OperatingPolicyError",
    "PolicyDecision",
    "load_model_policy",
    "load_builder_policy",
    "validate_model_policy",
    "evaluate_model_candidate",
    "validate_builder_policy",
    "evaluate_builder_campaign",
    "validate_character_contract",
    "resolve_character_for_engine",
]
