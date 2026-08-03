"""Executable operating contracts for model roles, image characters, and Builder.

A label, database row, or green unit test is not a working product.  These
validators require the operating decisions and evidence needed to support the
claim a role, character, or Builder campaign makes.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

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
_MODEL_METRIC_KEYS = frozenset(
    {
        "sample_size",
        "repeat_windows",
        "accepted_outcome_rate",
        "cost_per_accepted_outcome",
        "median_time_to_accepted_outcome",
        "malformed_rate",
        "tool_success_rate",
        "critical_regressions",
    }
)
_BUILDER_CORE_METRICS = frozenset(
    {"elapsed_seconds", "processed_packets", "accepted_packets"}
)
_WEIGHT_TOLERANCE = 1e-6


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
    discovery = _mapping(policy.get("discovery"), "model policy discovery")
    cadence = _positive_int(discovery.get("cadence_days"), "discovery.cadence_days")
    if cadence > 365:
        raise OperatingPolicyError("discovery.cadence_days must be at most 365")
    if not isinstance(discovery.get("automatic_promotion"), bool):
        raise OperatingPolicyError("discovery.automatic_promotion must be boolean")
    _string_list(discovery.get("sources"), "discovery.sources", require_nonempty=True)

    roles = _mapping(policy.get("roles"), "model policy roles")
    missing = sorted(_MODEL_ROLES - set(roles))
    unknown = sorted(set(roles) - _MODEL_ROLES)
    if missing or unknown:
        raise OperatingPolicyError(f"model policy roles missing={missing} unknown={unknown}")

    routes: set[str] = set()
    concrete_models: set[tuple[str, str]] = set()
    for role_name in sorted(_MODEL_ROLES):
        role = _mapping(roles[role_name], f"model role {role_name!r}")
        for field in ("kind", "public_name", "route", "purpose"):
            _text(role.get(field), f"model role {role_name!r}.{field}")
        metrics = _string_list(
            role.get("required_metrics"),
            f"model role {role_name!r}.required_metrics",
            require_nonempty=True,
        )
        if len(metrics) != len(set(metrics)):
            raise OperatingPolicyError(
                f"model role {role_name!r}.required_metrics contains duplicates"
            )
        route = str(role["route"])
        if route in routes:
            raise OperatingPolicyError(f"duplicate model route: {route}")
        routes.add(route)

        incumbent = role.get("incumbent")
        if role_name == "auto":
            if incumbent is not None or role.get("kind") != "router":
                raise OperatingPolicyError("auto must be a router with no incumbent model")
            continue
        if role.get("kind") != "model_role":
            raise OperatingPolicyError(f"model role {role_name!r}.kind must be model_role")
        concrete = _mapping(incumbent, f"model role {role_name!r}.incumbent")
        provider = _text(concrete.get("provider"), f"model role {role_name!r}.provider")
        model = _text(concrete.get("model"), f"model role {role_name!r}.model")
        identity = (provider, model)
        if identity in concrete_models:
            raise OperatingPolicyError(
                f"two concrete roles advertise the same incumbent: {provider}/{model}"
            )
        concrete_models.add(identity)

    evaluation = _mapping(policy.get("evaluation"), "model policy evaluation")
    _positive_int(
        evaluation.get("minimum_representative_tasks"),
        "evaluation.minimum_representative_tasks",
    )
    _positive_int(evaluation.get("repeat_windows"), "evaluation.repeat_windows")
    _nonnegative_int(
        evaluation.get("maximum_critical_regressions"),
        "evaluation.maximum_critical_regressions",
    )
    for key in (
        "maximum_malformed_rate",
        "maximum_success_rate_regression",
        "quality_improvement_required",
        "cost_reduction_required",
        "latency_reduction_required",
        "maximum_tool_success_regression",
    ):
        _rate(evaluation.get(key), f"evaluation.{key}")


def evaluate_model_candidate(
    role_name: str,
    incumbent: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
) -> PolicyDecision:
    """Decide whether a candidate may replace a role incumbent.

    Token price alone never wins.  The unit is an accepted outcome including
    retries, supervision, elapsed time, malformed responses, and tool failures.
    """

    loaded = dict(policy or load_model_policy())
    validate_model_policy(loaded)
    if role_name not in loaded["roles"] or role_name == "auto":
        raise OperatingPolicyError(f"{role_name!r} is not a promotable model role")

    missing = tuple(
        sorted(key for key in _MODEL_METRIC_KEYS if key not in incumbent or key not in candidate)
    )
    if missing:
        return PolicyDecision("insufficient_evidence", (), missing)

    incumbent_metrics = _validated_model_metrics(incumbent, "incumbent")
    candidate_metrics = _validated_model_metrics(candidate, "candidate")
    cfg = loaded["evaluation"]
    reasons: list[str] = []

    if candidate_metrics["sample_size"] < int(cfg["minimum_representative_tasks"]):
        reasons.append("candidate sample is smaller than the required representative set")
    if candidate_metrics["repeat_windows"] < int(cfg["repeat_windows"]):
        reasons.append("candidate was not reproduced across enough evaluation windows")
    if candidate_metrics["critical_regressions"] > int(cfg["maximum_critical_regressions"]):
        reasons.append("candidate has a critical regression")
    if candidate_metrics["malformed_rate"] > float(cfg["maximum_malformed_rate"]):
        reasons.append("candidate malformed-output rate is too high")

    tool_regression = (
        incumbent_metrics["tool_success_rate"] - candidate_metrics["tool_success_rate"]
    )
    if tool_regression > float(cfg["maximum_tool_success_regression"]):
        reasons.append("candidate tool success regressed beyond policy")

    incumbent_success = incumbent_metrics["accepted_outcome_rate"]
    candidate_success = candidate_metrics["accepted_outcome_rate"]
    success_delta = candidate_success - incumbent_success
    success_regression = incumbent_success - candidate_success
    quality_win = success_delta >= float(cfg["quality_improvement_required"])
    quality_parity = success_regression <= float(cfg["maximum_success_rate_regression"])

    cost_reduction = _reduction(
        incumbent_metrics["cost_per_accepted_outcome"],
        candidate_metrics["cost_per_accepted_outcome"],
    )
    latency_reduction = _reduction(
        incumbent_metrics["median_time_to_accepted_outcome"],
        candidate_metrics["median_time_to_accepted_outcome"],
    )
    economic_win = quality_parity and cost_reduction >= float(cfg["cost_reduction_required"])
    speed_win = quality_parity and latency_reduction >= float(cfg["latency_reduction_required"])
    if not (quality_win or economic_win or speed_win):
        reasons.append(
            "candidate did not improve accepted outcomes, successful-outcome cost, "
            "or time-to-success enough to justify promotion"
        )

    return PolicyDecision("reject" if reasons else "promote", tuple(reasons))


def validate_builder_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("schema_version") != 1:
        raise OperatingPolicyError("Builder policy schema_version must be 1")
    window = _mapping(policy.get("observation_window"), "Builder observation_window")
    _nonnegative_number(window.get("minimum_elapsed_seconds"), "minimum_elapsed_seconds")
    _nonnegative_int(window.get("minimum_processed_packets"), "minimum_processed_packets")

    tripwires = _mapping(policy.get("tripwires"), "Builder tripwires")
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
    for key in (
        "maximum_campaign_elapsed_seconds",
        "maximum_current_packet_elapsed_seconds",
        "minimum_accepted_packets_per_hour",
        "maximum_supervisor_to_worker_token_ratio",
        "maximum_projected_vs_simple_baseline_ratio",
    ):
        _positive_number(tripwires.get(key), f"tripwires.{key}")
    _rate(
        tripwires.get("maximum_setup_metadata_fraction"),
        "tripwires.maximum_setup_metadata_fraction",
    )
    for key in (
        "maximum_consecutive_no_substantive_diff",
        "maximum_reset_recovery_events",
        "maximum_repeated_systemic_blocker_count",
    ):
        _positive_int(tripwires.get(key), f"tripwires.{key}")

    required_fields = _string_list(
        policy.get("required_receipt_fields"),
        "required_receipt_fields",
        require_nonempty=True,
    )
    if len(required_fields) != len(set(required_fields)):
        raise OperatingPolicyError("required_receipt_fields contains duplicates")
    decision = _mapping(policy.get("decision"), "Builder decision")
    if decision.get("on_tripwire") != "pause":
        raise OperatingPolicyError("Builder decision.on_tripwire must be pause")
    if decision.get("on_missing_core_metrics") != "insufficient_evidence":
        raise OperatingPolicyError(
            "Builder decision.on_missing_core_metrics must be insufficient_evidence"
        )
    if decision.get("on_missing_required_metrics_after_observation_window") != "pause":
        raise OperatingPolicyError(
            "missing required Builder telemetry must pause after the observation window"
        )
    _text(decision.get("message"), "Builder decision.message")


def evaluate_builder_campaign(
    metrics: Mapping[str, Any],
    *,
    policy: Mapping[str, Any] | None = None,
) -> PolicyDecision:
    """Pause a campaign that is durable but economically ineffective.

    Missing telemetry is never converted to zero.  Core measurements missing
    entirely produce ``insufficient_evidence``; once the observation window has
    elapsed, any other required measurement gap is itself a pause condition.
    """

    loaded = dict(policy or load_builder_policy())
    validate_builder_policy(loaded)
    required = tuple(str(key) for key in loaded["required_receipt_fields"])
    missing = tuple(sorted(key for key in required if metrics.get(key) is None))
    missing_core = tuple(sorted(_BUILDER_CORE_METRICS & set(missing)))
    if missing_core:
        return PolicyDecision("insufficient_evidence", (), missing)

    values = {
        key: _optional_nonnegative_metric(metrics.get(key), key)
        for key in required
        if metrics.get(key) is not None
    }
    elapsed = values["elapsed_seconds"]
    processed = values["processed_packets"]
    accepted = values["accepted_packets"]
    if accepted > processed:
        raise OperatingPolicyError("accepted_packets cannot exceed processed_packets")

    cfg = loaded["tripwires"]
    window = loaded["observation_window"]
    observed = (
        elapsed >= float(window["minimum_elapsed_seconds"])
        and processed >= float(window["minimum_processed_packets"])
    )
    reasons: list[str] = []
    if observed and missing:
        reasons.append(
            "required effectiveness telemetry is missing after the observation window: "
            + ", ".join(missing)
        )

    if elapsed > float(cfg["maximum_campaign_elapsed_seconds"]):
        reasons.append("campaign exceeded the maximum wall-clock budget")
    current = values.get("current_packet_elapsed_seconds")
    if current is not None and current > float(cfg["maximum_current_packet_elapsed_seconds"]):
        reasons.append("current packet exceeded the small-packet time budget")
    if observed:
        throughput = accepted / (elapsed / 3600) if elapsed > 0 else 0.0
        if throughput < float(cfg["minimum_accepted_packets_per_hour"]):
            reasons.append("accepted-packet throughput is below policy")

    no_diff = values.get("consecutive_no_substantive_diff")
    if no_diff is not None and no_diff >= float(
        cfg["maximum_consecutive_no_substantive_diff"]
    ):
        reasons.append("multiple consecutive attempts produced no substantive diff")
    setup = values.get("setup_metadata_seconds")
    if elapsed > 0 and setup is not None:
        if setup / elapsed > float(cfg["maximum_setup_metadata_fraction"]):
            reasons.append("setup and metadata work consume too much campaign time")
    supervisor = values.get("supervisor_tokens")
    worker = values.get("worker_tokens")
    if supervisor is not None and worker is not None:
        if worker == 0 and supervisor > 0:
            reasons.append("supervisor consumed tokens while the worker recorded none")
        elif worker > 0 and supervisor / worker > float(
            cfg["maximum_supervisor_to_worker_token_ratio"]
        ):
            reasons.append("supervisor token use exceeds the worker budget")
    resets = values.get("reset_recovery_events")
    if resets is not None and resets >= float(cfg["maximum_reset_recovery_events"]):
        reasons.append("reset/recovery churn exceeded policy")
    blockers = values.get("repeated_systemic_blocker_count")
    if blockers is not None and blockers >= float(
        cfg["maximum_repeated_systemic_blocker_count"]
    ):
        reasons.append("the same systemic blocker repeated across packets")
    projected = values.get("projected_completion_seconds")
    baseline = values.get("simple_baseline_seconds")
    if projected is not None and baseline is not None:
        if baseline == 0 and projected > 0:
            reasons.append("simple baseline is zero while the campaign still projects work")
        elif baseline > 0 and projected / baseline > float(
            cfg["maximum_projected_vs_simple_baseline_ratio"]
        ):
            reasons.append("projected campaign time is worse than the simple-agent baseline")

    return PolicyDecision("pause" if reasons else "continue", tuple(reasons), missing)


def validate_character_contract(character: Mapping[str, Any]) -> None:
    """Reject character records that cannot truthfully drive generation."""

    if character.get("schema_version") != 1:
        raise OperatingPolicyError("character schema_version must be 1")
    _text(character.get("character_id"), "character_id")
    _text(character.get("name"), "name")

    description = _mapping(character.get("description"), "character description")
    _text(description.get("appearance"), "character description.appearance")
    _unique_string_list(description.get("preserve"), "character description.preserve")
    _unique_string_list(description.get("exclude"), "character description.exclude")

    identity = _mapping(character.get("identity"), "character identity")
    method = identity.get("method")
    fusion = identity.get("fusion_method")
    if method not in _IDENTITY_METHODS:
        raise OperatingPolicyError(f"unsupported identity method: {method!r}")
    if fusion not in _FUSION_METHODS:
        raise OperatingPolicyError(f"unsupported fusion method: {fusion!r}")
    _text(identity.get("base_family"), "character identity.base_family")
    adapter_model = identity.get("adapter_model")
    if method == "description_only":
        if adapter_model not in {None, ""}:
            raise OperatingPolicyError("description_only identity cannot claim an adapter model")
    else:
        _text(adapter_model, f"identity method {method!r}.adapter_model")
    strength = identity.get("adapter_strength", 1.0)
    _bounded_number(strength, "character identity.adapter_strength", 0, 2)
    if not isinstance(identity.get("allow_generated_derivatives", False), bool):
        raise OperatingPolicyError("allow_generated_derivatives must be boolean")

    references = identity.get("references")
    if not isinstance(references, list) or len(references) > 12:
        raise OperatingPolicyError("character references must be a list of at most 12")
    seen: set[str] = set()
    enabled: list[Mapping[str, Any]] = []
    allow_generated = bool(identity.get("allow_generated_derivatives", False))
    for index, raw_ref in enumerate(references):
        ref = _mapping(raw_ref, f"character reference[{index}]")
        ref_id = _text(ref.get("ref_id"), f"character reference[{index}].ref_id")
        if ref_id in seen:
            raise OperatingPolicyError(f"duplicate character reference ref_id: {ref_id}")
        seen.add(ref_id)
        if ref.get("purpose") not in _REFERENCE_PURPOSES:
            raise OperatingPolicyError(
                f"unsupported reference purpose: {ref.get('purpose')!r}"
            )
        provenance = ref.get("provenance")
        if provenance not in {"real_photo", "generated_derivative"}:
            raise OperatingPolicyError(f"unsupported reference provenance: {provenance!r}")
        if not isinstance(ref.get("enabled"), bool):
            raise OperatingPolicyError(f"reference {ref_id!r}.enabled must be boolean")
        for field in ("weight", "face_weight", "body_weight", "quality_score"):
            _bounded_number(ref.get(field), f"reference {ref_id!r}.{field}", 0, 1)
        notes = ref.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise OperatingPolicyError(f"reference {ref_id!r}.notes must be string or null")
        if ref["enabled"]:
            if provenance == "generated_derivative" and not allow_generated:
                raise OperatingPolicyError(
                    "generated derivative reference is disabled by the character policy"
                )
            enabled.append(ref)

    if method == "description_only" and enabled:
        raise OperatingPolicyError("description_only characters cannot claim reference conditioning")
    if method != "description_only" and not enabled:
        raise OperatingPolicyError(f"identity method {method!r} needs an enabled reference")
    if enabled:
        primary_count = sum(ref["purpose"] == "primary_face" for ref in enabled)
        if primary_count != 1:
            raise OperatingPolicyError("exactly one enabled primary_face reference is required")
    weights = [float(ref["weight"]) for ref in enabled]
    if fusion == "single" and (len(enabled) != 1 or not _close(sum(weights), 1.0)):
        raise OperatingPolicyError("single fusion requires one enabled reference with weight 1")
    if fusion == "weighted_mean" and not _close(sum(weights), 1.0):
        raise OperatingPolicyError("weighted_mean enabled reference weights must add to 1")
    if fusion == "equal_mean" and weights and any(
        not _close(weight, weights[0]) for weight in weights[1:]
    ):
        raise OperatingPolicyError("equal_mean references must carry equal weights")

    prompt = _mapping(character.get("prompt"), "character prompt")
    if not isinstance(prompt.get("positive"), str) or not isinstance(prompt.get("negative"), str):
        raise OperatingPolicyError("character prompt positive and negative must be strings")
    recipe = _mapping(character.get("recipe"), "character recipe")
    _text(recipe.get("recipe_id"), "character recipe.recipe_id")
    _text(recipe.get("engine"), "character recipe.engine")
    if recipe.get("steps") is not None:
        _positive_int(recipe["steps"], "character recipe.steps")
    if recipe.get("guidance") is not None:
        _nonnegative_number(recipe["guidance"], "character recipe.guidance")
    if recipe.get("denoise") is not None:
        _bounded_number(recipe["denoise"], "character recipe.denoise", 0, 1)


def resolve_character_for_engine(
    character: Mapping[str, Any], engine_capabilities: Mapping[str, Any]
) -> dict[str, Any]:
    """Return an execution recipe or fail instead of silently ignoring fields."""

    validate_character_contract(character)
    caps = _mapping(engine_capabilities, "engine capabilities")
    recipe = character["recipe"]
    identity = character["identity"]
    method = str(identity["method"])
    fusion = str(identity["fusion_method"])
    engine = _text(caps.get("engine"), "engine capabilities.engine")
    if engine != recipe["engine"]:
        raise OperatingPolicyError(
            f"character recipe targets {recipe['engine']!r}, capabilities describe {engine!r}"
        )
    base_families = set(
        _string_list(caps.get("base_families"), "engine capabilities.base_families")
    )
    if identity["base_family"] not in base_families:
        raise OperatingPolicyError(
            f"engine {engine!r} cannot honor base family {identity['base_family']!r}"
        )
    supported_methods = set(
        _string_list(caps.get("identity_methods"), "engine capabilities.identity_methods")
    )
    supported_fusions = set(
        _string_list(caps.get("fusion_methods"), "engine capabilities.fusion_methods")
    )
    if method not in supported_methods:
        raise OperatingPolicyError(
            f"engine cannot honor identity method {method!r}; refusing to ignore it"
        )
    if fusion not in supported_fusions:
        raise OperatingPolicyError(
            f"engine cannot honor fusion method {fusion!r}; refusing to weight references falsely"
        )
    maximum_references = _nonnegative_int(
        caps.get("maximum_references"), "engine capabilities.maximum_references"
    )
    enabled = [ref for ref in identity["references"] if ref["enabled"]]
    if len(enabled) > maximum_references:
        raise OperatingPolicyError(
            f"engine supports {maximum_references} reference(s), character enables {len(enabled)}"
        )
    if fusion == "weighted_mean" and not caps.get("per_reference_weights", False):
        raise OperatingPolicyError(
            "engine cannot honor per-reference weights; refusing to pretend the sliders work"
        )
    uses_region_weights = any(
        not _close(float(ref["face_weight"]), float(ref["weight"]))
        or not _close(float(ref["body_weight"]), float(ref["weight"]))
        for ref in enabled
    )
    if uses_region_weights and not caps.get("per_region_weights", False):
        raise OperatingPolicyError(
            "engine cannot honor face/body reference weights; refusing to ignore them"
        )
    adapter_model = identity.get("adapter_model")
    advertised_adapters = caps.get("adapter_models")
    if adapter_model and advertised_adapters is not None:
        supported_adapters = set(
            _string_list(advertised_adapters, "engine capabilities.adapter_models")
        )
        if adapter_model not in supported_adapters:
            raise OperatingPolicyError(
                f"engine does not advertise character adapter {adapter_model!r}"
            )

    appearance = str(character["description"]["appearance"]).strip()
    positive = str(character["prompt"]["positive"]).strip()
    return {
        "character_id": character["character_id"],
        "name": character["name"],
        "engine": engine,
        "recipe_id": recipe["recipe_id"],
        "base_family": identity["base_family"],
        "identity_method": method,
        "adapter_model": adapter_model,
        "adapter_strength": identity.get("adapter_strength", 1.0),
        "fusion_method": fusion,
        "references": enabled,
        "positive_prompt": ", ".join(part for part in (appearance, positive) if part),
        "negative_prompt": str(character["prompt"]["negative"]).strip(),
        "preserve": list(character["description"]["preserve"]),
        "exclude": list(character["description"]["exclude"]),
        "recipe": dict(recipe),
    }


def _validated_model_metrics(raw: Mapping[str, Any], label: str) -> dict[str, float | int]:
    return {
        "sample_size": _positive_int(raw.get("sample_size"), f"{label}.sample_size"),
        "repeat_windows": _positive_int(
            raw.get("repeat_windows"), f"{label}.repeat_windows"
        ),
        "accepted_outcome_rate": _rate(
            raw.get("accepted_outcome_rate"), f"{label}.accepted_outcome_rate"
        ),
        "cost_per_accepted_outcome": _nonnegative_number(
            raw.get("cost_per_accepted_outcome"),
            f"{label}.cost_per_accepted_outcome",
        ),
        "median_time_to_accepted_outcome": _nonnegative_number(
            raw.get("median_time_to_accepted_outcome"),
            f"{label}.median_time_to_accepted_outcome",
        ),
        "malformed_rate": _rate(raw.get("malformed_rate"), f"{label}.malformed_rate"),
        "tool_success_rate": _rate(
            raw.get("tool_success_rate"), f"{label}.tool_success_rate"
        ),
        "critical_regressions": _nonnegative_int(
            raw.get("critical_regressions"), f"{label}.critical_regressions"
        ),
    }


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OperatingPolicyError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OperatingPolicyError(f"{label} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, label: str, *, require_nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (require_nonempty and not value):
        qualifier = "a non-empty" if require_nonempty else "an"
        raise OperatingPolicyError(f"{label} must be {qualifier} array of strings")
    normalized = []
    for item in value:
        normalized.append(_text(item, f"{label} item"))
    return normalized


def _unique_string_list(value: Any, label: str) -> list[str]:
    normalized = _string_list(value, label)
    if len(normalized) != len(set(normalized)):
        raise OperatingPolicyError(f"{label} contains duplicates")
    return normalized


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OperatingPolicyError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise OperatingPolicyError(f"{label} must be a finite number")
    return number


def _nonnegative_number(value: Any, label: str) -> float:
    number = _finite_number(value, label)
    if number < 0:
        raise OperatingPolicyError(f"{label} must be non-negative")
    return number


def _positive_number(value: Any, label: str) -> float:
    number = _finite_number(value, label)
    if number <= 0:
        raise OperatingPolicyError(f"{label} must be positive")
    return number


def _bounded_number(value: Any, label: str, low: float, high: float) -> float:
    number = _finite_number(value, label)
    if not low <= number <= high:
        raise OperatingPolicyError(f"{label} must be between {low} and {high}")
    return number


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OperatingPolicyError(f"{label} must be a non-negative integer")
    return value


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise OperatingPolicyError(f"{label} must be a positive integer")
    return value


def _rate(value: Any, label: str) -> float:
    return _bounded_number(value, label, 0, 1)


def _optional_nonnegative_metric(value: Any, label: str) -> float:
    return _nonnegative_number(value, f"Builder metric {label}")


def _reduction(incumbent: float | int, candidate: float | int) -> float:
    incumbent_value = float(incumbent)
    candidate_value = float(candidate)
    if incumbent_value == 0:
        return 0.0 if candidate_value == 0 else -math.inf
    return 1 - (candidate_value / incumbent_value)


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0, abs_tol=_WEIGHT_TOLERANCE)


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
