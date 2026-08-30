#!/usr/bin/env python3
"""Kitty ImageBench manifest, blind-review, and economics runner.

This is deliberately not an image-generation engine. It sits above Kitty's
existing ImagePlan/ImageJob/ImageEvaluation owners and turns completed image
attempts into comparable evidence. Provider execution remains owned by
``gateway.image_runner``; this script performs no network or paid calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BENCHMARK_SCHEMA_VERSION = 1
SETTLED_COST_SOURCES = frozenset(
    {
        "provider_reported",
        "provider_invoice",
        "provider_contract",
        "metered_compute",
        "local_zero_marginal",
    }
)
RATING_FIELDS = (
    "would_keep",
    "identity",
    "assignment",
    "photorealism",
    "male_body_hair_anatomy",
    "prompt_reference_adherence",
    "edit_locality",
    "composition",
)


class BenchmarkContractError(ValueError):
    """Raised when benchmark evidence is incomplete or internally inconsistent."""


def _scenario(
    scenario_id: str,
    stage: str,
    prompt: str,
    required_scorers: Iterable[str],
    *,
    content_lane: str = "safe",
    enabled_by_default: bool = True,
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "stage": stage,
        "prompt": prompt,
        "required_scorers": list(required_scorers),
        "content_lane": content_lane,
        "enabled_by_default": enabled_by_default,
    }


_SCENARIOS = (
    # A — raw adult-male photorealism.
    _scenario(
        "A.natural_daylight_portrait",
        "A",
        "adult male portrait in natural daylight, realistic camera photograph",
        ("mechanics", "photorealism"),
    ),
    _scenario(
        "A.indoor_portrait",
        "A",
        "adult male indoor portrait with realistic household lighting",
        ("mechanics", "photorealism"),
    ),
    _scenario(
        "A.phone_candid",
        "A",
        "candid phone photograph of an adult man, ordinary unposed moment",
        ("mechanics", "photorealism"),
    ),
    _scenario(
        "A.harsh_flash",
        "A",
        "adult male snapshot under harsh direct flash with realistic skin response",
        ("mechanics", "photorealism"),
    ),
    _scenario(
        "A.low_light",
        "A",
        "adult male photograph in low available light with believable noise and exposure",
        ("mechanics", "photorealism"),
    ),
    _scenario(
        "A.close_skin_detail",
        "A",
        "close adult male facial photograph showing natural pores and skin texture",
        ("mechanics", "photorealism"),
    ),
    _scenario(
        "A.beard_stubble",
        "A",
        "adult male portrait with natural short beard and irregular stubble detail",
        ("mechanics", "photorealism"),
    ),
    _scenario(
        "A.body_hair",
        "A",
        "non-sexual full-torso adult male photograph with natural body hair",
        ("mechanics", "photorealism", "anatomy"),
    ),
    _scenario(
        "A.full_body",
        "A",
        "full-body adult male photograph with realistic proportions and hands visible",
        ("mechanics", "photorealism", "anatomy"),
    ),
    _scenario(
        "A.diverse_age_build",
        "A",
        "ordinary adult man with a non-model body build and age-visible facial detail",
        ("mechanics", "photorealism", "anatomy"),
    ),
    _scenario(
        "A.difficult_hands_pose",
        "A",
        "adult man seated in a difficult natural pose with both hands clearly visible",
        ("mechanics", "photorealism", "anatomy"),
    ),
    # B — one authorized/synthetic character across transformations.
    _scenario(
        "B.close_up",
        "B",
        "same authorized adult male identity, close-up portrait",
        ("mechanics", "identity", "photorealism"),
    ),
    _scenario(
        "B.full_body",
        "B",
        "same authorized adult male identity, full-body standing photograph",
        ("mechanics", "identity", "photorealism", "anatomy"),
    ),
    _scenario(
        "B.profile",
        "B",
        "same authorized adult male identity in profile view",
        ("mechanics", "identity", "photorealism"),
    ),
    _scenario(
        "B.three_quarter",
        "B",
        "same authorized adult male identity at a three-quarter angle",
        ("mechanics", "identity", "photorealism"),
    ),
    _scenario(
        "B.sitting_standing",
        "B",
        "same authorized adult male identity in a changed seated or standing pose",
        ("mechanics", "identity", "photorealism"),
    ),
    _scenario(
        "B.clothing_change",
        "B",
        "same authorized adult male identity wearing clearly different clothing",
        ("mechanics", "identity", "prompt_adherence"),
    ),
    _scenario(
        "B.lighting_change",
        "B",
        "same authorized adult male identity under substantially different lighting",
        ("mechanics", "identity", "photorealism"),
    ),
    _scenario(
        "B.expression_change",
        "B",
        "same authorized adult male identity with a changed natural expression",
        ("mechanics", "identity", "prompt_adherence"),
    ),
    _scenario(
        "B.body_build_change",
        "B",
        "same authorized adult male identity with a requested broader ordinary body build",
        ("mechanics", "identity", "anatomy", "prompt_adherence"),
    ),
    # C — semantic reference-role binding.
    _scenario(
        "C.face_reference",
        "C",
        "compose an adult male subject using the identity reference only for facial identity",
        ("mechanics", "identity", "reference_role"),
    ),
    _scenario(
        "C.body_build_reference",
        "C",
        "compose an adult male subject using a body reference for build while preserving facial identity",
        ("mechanics", "identity", "reference_role", "anatomy"),
    ),
    _scenario(
        "C.pose_reference",
        "C",
        "compose an adult male subject following the pose reference without identity leakage",
        ("mechanics", "identity", "reference_role", "composition"),
    ),
    _scenario(
        "C.wardrobe_reference",
        "C",
        "compose an adult male subject following the wardrobe reference without transferring identity",
        ("mechanics", "identity", "reference_role", "prompt_adherence"),
    ),
    _scenario(
        "C.scene_style_reference",
        "C",
        "compose an adult male subject using the scene/style reference only for environment and visual treatment",
        ("mechanics", "identity", "reference_role", "composition"),
    ),
    # D — two independent adult identities.
    _scenario(
        "D.side_by_side",
        "D",
        "two distinct authorized adult male identities side by side with stable assignment",
        ("mechanics", "identity", "assignment", "composition"),
    ),
    _scenario(
        "D.different_positions",
        "D",
        "two distinct authorized adult male identities in explicitly different left/right positions",
        ("mechanics", "identity", "assignment", "composition"),
    ),
    _scenario(
        "D.occlusion",
        "D",
        "two distinct authorized adult male identities with partial overlap and occlusion",
        ("mechanics", "identity", "assignment", "composition"),
    ),
    _scenario(
        "D.close_interaction",
        "D",
        "two distinct authorized adult male identities in close non-sexual physical interaction",
        ("mechanics", "identity", "assignment", "composition", "anatomy"),
    ),
    _scenario(
        "D.difficult_pose",
        "D",
        "two distinct authorized adult male identities in a difficult shared pose with clear limbs",
        ("mechanics", "identity", "assignment", "composition", "anatomy"),
    ),
    _scenario(
        "D.private_adult_control",
        "D",
        "two consenting fictional adult male characters in a private adult-only composition benchmark; preserve distinct identities and assignment",
        ("mechanics", "identity", "assignment", "composition", "anatomy"),
        content_lane="private_adult",
        enabled_by_default=False,
    ),
    # E — locality: one requested edit, everything else protected.
    _scenario(
        "E.single_property_edit",
        "E",
        "change exactly one approved property while preserving all non-target regions",
        ("mechanics", "requested_change", "edit_locality", "identity"),
    ),
    # F — hard mechanics/anatomy.
    _scenario(
        "F.hands",
        "F",
        "adult male subject with both hands prominent and fingers clearly separated",
        ("mechanics", "anatomy", "photorealism"),
    ),
    _scenario(
        "F.feet",
        "F",
        "full-body adult male subject with both feet clearly visible in a natural stance",
        ("mechanics", "anatomy", "photorealism"),
    ),
    _scenario(
        "F.foreshortening",
        "F",
        "adult male subject in strong photographic foreshortening with believable limbs",
        ("mechanics", "anatomy", "photorealism"),
    ),
    _scenario(
        "F.body_overlap",
        "F",
        "two adult male subjects with overlapping limbs while maintaining coherent anatomy",
        ("mechanics", "anatomy", "composition"),
    ),
    _scenario(
        "F.unusual_pose",
        "F",
        "adult male subject in an unusual but physically plausible pose",
        ("mechanics", "anatomy", "photorealism"),
    ),
    # G — same scenario is run against a raw and Kitty-pipeline candidate.
    _scenario(
        "G.raw_vs_pipeline",
        "G",
        "adult male portrait benchmark used unchanged for raw-model versus Kitty-pipeline comparison",
        ("mechanics", "photorealism"),
    ),
)


def scenario_catalog() -> list[dict[str, Any]]:
    """Return a defensive copy of the canonical ImageBench scenario catalog."""
    return json.loads(json.dumps(_SCENARIOS))


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkContractError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise BenchmarkContractError("candidate must be an object")
    result = dict(candidate)
    for field in (
        "candidate_id",
        "provider",
        "model",
        "revision",
        "compiler",
        "workflow",
        "reference_strategy",
        "quantization",
    ):
        result[field] = _nonempty_string(result.get(field), f"candidate {field}")
    lanes = result.get("content_lanes")
    if (
        not isinstance(lanes, list)
        or not lanes
        or not all(isinstance(lane, str) and lane.strip() for lane in lanes)
    ):
        raise BenchmarkContractError("candidate content_lanes must be a non-empty list of strings")
    normalized_lanes = [lane.strip() for lane in lanes]
    allowed_lanes = {"safe", "private_adult"}
    unknown_lanes = set(normalized_lanes).difference(allowed_lanes)
    if unknown_lanes:
        raise BenchmarkContractError(
            f"candidate content_lanes contains unsupported lane(s): "
            f"{', '.join(sorted(unknown_lanes))}"
        )
    if len(normalized_lanes) != len(set(normalized_lanes)):
        raise BenchmarkContractError("candidate content_lanes must not contain duplicates")
    result["content_lanes"] = normalized_lanes

    settings = result.get("settings")
    if not isinstance(settings, dict):
        raise BenchmarkContractError("candidate settings must be an object")
    result["settings"] = json.loads(json.dumps(settings, sort_keys=True))
    supplied_fingerprint = result.pop("candidate_sha256", None)
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if supplied_fingerprint is not None and supplied_fingerprint != fingerprint:
        raise BenchmarkContractError(
            "candidate_sha256 does not match the exact candidate configuration"
        )
    result["candidate_sha256"] = fingerprint
    return result


def build_run_manifest(
    candidates: list[dict[str, Any]],
    *,
    stages: list[str] | None = None,
    scenario_ids: list[str] | None = None,
    seed_base: int = 1000,
    include_private: bool = False,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Create an immutable comparison manifest without executing providers."""
    if not candidates:
        raise BenchmarkContractError("at least one candidate is required")
    validated = [_validate_candidate(candidate) for candidate in candidates]
    ids = [candidate["candidate_id"] for candidate in validated]
    if len(ids) != len(set(ids)):
        raise BenchmarkContractError("candidate_id values must be unique")
    if isinstance(seed_base, bool) or not isinstance(seed_base, int) or seed_base < 0:
        raise BenchmarkContractError("seed_base must be a non-negative integer")

    stage_filter = set(stages or "ABCDEFG")
    unknown_stages = stage_filter.difference("ABCDEFG")
    if unknown_stages:
        raise BenchmarkContractError(
            f"unknown ImageBench stage(s): {', '.join(sorted(unknown_stages))}"
        )

    scenario_filter = set(scenario_ids or [])
    known_ids = {scenario["scenario_id"] for scenario in scenario_catalog()}
    unknown_ids = scenario_filter.difference(known_ids)
    if unknown_ids:
        raise BenchmarkContractError(
            f"unknown ImageBench scenario(s): {', '.join(sorted(unknown_ids))}"
        )
    selected = [
        scenario
        for scenario in scenario_catalog()
        if scenario["stage"] in stage_filter
        and (not scenario_filter or scenario["scenario_id"] in scenario_filter)
        and (include_private or scenario["enabled_by_default"])
    ]
    if not selected:
        raise BenchmarkContractError("stage selection produced no benchmark scenarios")

    items: list[dict[str, Any]] = []
    for offset, scenario in enumerate(selected):
        seed = seed_base + offset
        for candidate in validated:
            lane = scenario["content_lane"]
            if lane not in candidate["content_lanes"]:
                raise BenchmarkContractError(
                    f"candidate {candidate['candidate_id']!r} does not support "
                    f"benchmark content lane {lane!r}"
                )
            items.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "candidate_id": candidate["candidate_id"],
                    "seed": seed,
                    "content_lane": lane,
                }
            )

    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "run_id": run_id or f"imagebench_{uuid.uuid4().hex[:16]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed_base": seed_base,
        "candidates": validated,
        "scenarios": selected,
        "items": items,
    }


def evaluate_artifact_for_scenario(
    scenario: dict[str, Any],
    image_path: Path,
    *,
    scorers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one artifact through the canonical fail-closed evaluator."""
    from gateway.image_evaluation import evaluate_image

    required = scenario.get("required_scorers")
    if not isinstance(required, list) or not all(
        isinstance(name, str) and name.strip() for name in required
    ):
        raise BenchmarkContractError("scenario required_scorers must be non-empty strings")
    if not image_path.is_file():
        raise BenchmarkContractError(f"benchmark artifact is missing: {image_path}")
    result = evaluate_image(
        image_path=str(image_path),
        required_scorers=list(required),
        scorers=scorers,
    )
    return result.to_dict()


def _required_string_fields() -> tuple[str, ...]:
    return (
        "job_id",
        "plan_id",
        "intent_sha256",
        "artifact_id",
        "artifact_sha256",
        "provider",
        "model",
        "revision",
        "compiler",
        "workflow",
        "reference_strategy",
        "quantization",
        "candidate_sha256",
        "cost_source",
    )


def _is_nonnegative_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and float(value) >= 0.0
    )


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _observation_failures(
    observation: dict[str, Any],
    *,
    scenario: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[list[str], list[str]]:
    infrastructure: list[str] = []
    reproducibility: list[str] = []

    for field in _required_string_fields():
        value = observation.get(field)
        if not isinstance(value, str) or not value.strip():
            reproducibility.append(f"{field} is missing")
    attempt = observation.get("attempt")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt <= 0:
        reproducibility.append("attempt must be a positive integer")
    for field in ("settled_cost_usd", "latency_seconds"):
        if not _is_nonnegative_number(observation.get(field)):
            reproducibility.append(f"{field} must be a finite non-negative number")

    cost_source = observation.get("cost_source")
    if isinstance(cost_source, str) and cost_source.strip():
        if cost_source not in SETTLED_COST_SOURCES:
            reproducibility.append(
                f"cost_source {cost_source!r} is not an accepted settled cost source"
            )
        elif cost_source == "local_zero_marginal" and observation.get("settled_cost_usd") != 0:
            reproducibility.append("local_zero_marginal requires settled_cost_usd to be exactly 0")
        elif cost_source == "provider_contract":
            settings = candidate.get("settings")
            contract = settings.get("cost_contract") if isinstance(settings, dict) else None
            if not isinstance(contract, dict):
                reproducibility.append(
                    "provider_contract requires candidate settings.cost_contract"
                )
            else:
                kind = contract.get("kind")
                rate = contract.get("usd_per_megapixel")
                as_of = contract.get("as_of")
                width = observation.get("artifact_width")
                height = observation.get("artifact_height")
                if kind != "ceil_output_megapixels":
                    reproducibility.append(
                        "provider_contract kind must be 'ceil_output_megapixels'"
                    )
                rate_number = (
                    float(rate)
                    if isinstance(rate, (int, float)) and not isinstance(rate, bool)
                    else None
                )
                if rate_number is None or not math.isfinite(rate_number) or rate_number <= 0:
                    reproducibility.append(
                        "provider_contract usd_per_megapixel must be finite and > 0"
                    )
                if not isinstance(as_of, str) or not as_of.strip():
                    reproducibility.append("provider_contract as_of provenance is required")
                if (
                    isinstance(width, bool)
                    or isinstance(height, bool)
                    or not isinstance(width, int)
                    or not isinstance(height, int)
                    or width <= 0
                    or height <= 0
                ):
                    reproducibility.append(
                        "provider_contract requires positive artifact_width/artifact_height"
                    )
                elif rate_number is not None and math.isfinite(rate_number) and rate_number > 0:
                    expected = math.ceil((width * height) / 1_000_000.0) * rate_number
                    settled = observation.get("settled_cost_usd")
                    settled_number = (
                        float(settled)
                        if isinstance(settled, (int, float)) and not isinstance(settled, bool)
                        else None
                    )
                    if (
                        settled_number is not None
                        and math.isfinite(settled_number)
                        and settled_number >= 0
                        and not math.isclose(settled_number, expected, rel_tol=0.0, abs_tol=1e-9)
                    ):
                        reproducibility.append(
                            "provider_contract settled_cost_usd does not match pinned contract and artifact dimensions"
                        )
    for field in ("intent_sha256", "artifact_sha256", "candidate_sha256"):
        if not _is_sha256(observation.get(field)):
            reproducibility.append(f"{field} must be a 64-character SHA-256 hex digest")

    for field in (
        "provider",
        "model",
        "revision",
        "compiler",
        "workflow",
        "reference_strategy",
        "quantization",
        "candidate_sha256",
    ):
        if observation.get(field) != candidate[field]:
            reproducibility.append(
                f"{field} {observation.get(field)!r} does not match candidate {candidate[field]!r}"
            )

    evaluation = observation.get("evaluation")
    if not isinstance(evaluation, dict):
        infrastructure.append("evaluation evidence is missing")
        return infrastructure, reproducibility
    if not isinstance(evaluation.get("passed"), bool):
        infrastructure.append("evaluation passed evidence is not boolean")
    dimensions = evaluation.get("dimensions")
    versions = evaluation.get("scorer_versions")
    if not isinstance(dimensions, dict) or not isinstance(versions, dict):
        infrastructure.append("evaluation scorer evidence is malformed")
        return infrastructure, reproducibility
    for scorer in scenario["required_scorers"]:
        if scorer not in dimensions or scorer not in versions:
            infrastructure.append(f"required scorer {scorer!r} is missing")
        elif not isinstance(versions[scorer], str) or not versions[scorer].strip():
            infrastructure.append(f"required scorer {scorer!r} has no version provenance")

    return infrastructure, reproducibility


def _validate_manifest(
    manifest: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], set[tuple[str, str]]]:
    """Validate that a persisted run still represents canonical benchmark truth."""
    if not isinstance(manifest, dict):
        raise BenchmarkContractError("manifest must be an object")
    if manifest.get("schema_version") != BENCHMARK_SCHEMA_VERSION:
        raise BenchmarkContractError("unsupported ImageBench manifest schema_version")

    raw_scenarios = manifest.get("scenarios")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise BenchmarkContractError("manifest must include scenarios")
    canonical_by_id = {item["scenario_id"]: item for item in scenario_catalog()}
    scenarios: dict[str, dict[str, Any]] = {}
    scenario_offsets: dict[str, int] = {}
    for offset, raw in enumerate(raw_scenarios):
        if not isinstance(raw, dict):
            raise BenchmarkContractError(f"manifest scenario {offset} must be an object")
        scenario_id = _nonempty_string(raw.get("scenario_id"), "manifest scenario_id")
        if scenario_id in scenarios:
            raise BenchmarkContractError(f"manifest has duplicate scenario_id {scenario_id!r}")
        canonical = canonical_by_id.get(scenario_id)
        if canonical is None:
            raise BenchmarkContractError(
                f"manifest references unknown canonical scenario {scenario_id!r}"
            )
        if raw != canonical:
            raise BenchmarkContractError(
                f"manifest canonical scenario {scenario_id!r} does not match the canonical definition"
            )
        scenarios[scenario_id] = canonical
        scenario_offsets[scenario_id] = offset

    raw_candidates = manifest.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise BenchmarkContractError("manifest must include candidates")
    candidates: dict[str, dict[str, Any]] = {}
    for raw in raw_candidates:
        validated = _validate_candidate(raw)
        candidate_id = validated["candidate_id"]
        if candidate_id in candidates:
            raise BenchmarkContractError(f"manifest has duplicate candidate_id {candidate_id!r}")
        candidates[candidate_id] = validated

    seed_base = manifest.get("seed_base")
    if isinstance(seed_base, bool) or not isinstance(seed_base, int) or seed_base < 0:
        raise BenchmarkContractError("manifest seed_base must be a non-negative integer")

    raw_items = manifest.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise BenchmarkContractError("manifest items must include every selected comparison pair")
    scheduled_pairs: set[tuple[str, str]] = set()
    for index, item in enumerate(raw_items):
        if not isinstance(item, dict):
            raise BenchmarkContractError(f"manifest item {index} must be an object")
        scenario_id = _nonempty_string(
            item.get("scenario_id"), f"manifest item {index} scenario_id"
        )
        candidate_id = _nonempty_string(
            item.get("candidate_id"), f"manifest item {index} candidate_id"
        )
        scenario = scenarios.get(scenario_id)
        candidate = candidates.get(candidate_id)
        if scenario is None or candidate is None:
            raise BenchmarkContractError(
                f"manifest item {index} references an unselected scenario or candidate"
            )
        pair = (scenario_id, candidate_id)
        if pair in scheduled_pairs:
            raise BenchmarkContractError(f"manifest items contain duplicate pair {pair!r}")
        scheduled_pairs.add(pair)
        if item.get("content_lane") != scenario["content_lane"]:
            raise BenchmarkContractError(
                f"manifest item {index} content lane does not match canonical scenario"
            )
        if scenario["content_lane"] not in candidate["content_lanes"]:
            raise BenchmarkContractError(
                f"manifest candidate {candidate_id!r} cannot execute content lane "
                f"{scenario['content_lane']!r}"
            )
        expected_seed = seed_base + scenario_offsets[scenario_id]
        if item.get("seed") != expected_seed:
            raise BenchmarkContractError(
                f"manifest item {index} seed does not match deterministic scenario seed "
                f"{expected_seed}"
            )

    expected_pairs = {
        (scenario_id, candidate_id) for scenario_id in scenarios for candidate_id in candidates
    }
    if scheduled_pairs != expected_pairs:
        raise BenchmarkContractError(
            "manifest items do not exactly cover every selected scenario/candidate pair"
        )
    return scenarios, candidates, scheduled_pairs


def summarize_run(manifest: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate blind keeper ratings, scorer gates, economics, and latency."""
    scenarios, candidates, scheduled_pairs = _validate_manifest(manifest)

    infrastructure_failures: list[str] = []
    reproducibility_failures: list[str] = []
    observed_pairs: set[tuple[str, str]] = set()
    missing_attempt_reviews: list[dict[str, Any]] = []
    seen_job_ids: set[str] = set()
    seen_attempts: set[tuple[str, str, int]] = set()
    per_candidate: dict[str, list[tuple[dict[str, Any], bool, bool]]] = {
        key: [] for key in candidates
    }

    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            reproducibility_failures.append(f"observation {index}: expected an object")
            continue
        scenario_id = observation.get("scenario_id")
        candidate_id = observation.get("candidate_id")
        prefix = f"observation {index} ({scenario_id!r}, {candidate_id!r})"
        if not isinstance(scenario_id, str):
            reproducibility_failures.append(f"{prefix}: scenario_id must be a string")
            continue
        if not isinstance(candidate_id, str):
            reproducibility_failures.append(f"{prefix}: candidate_id must be a string")
            continue
        scenario = scenarios.get(scenario_id)
        candidate = candidates.get(candidate_id)
        if scenario is None:
            reproducibility_failures.append(f"{prefix}: unknown scenario_id")
            continue
        if candidate is None:
            reproducibility_failures.append(f"{prefix}: unknown candidate_id")
            continue
        if (scenario_id, candidate_id) not in scheduled_pairs:
            reproducibility_failures.append(f"{prefix}: pair was not scheduled by the manifest")
            continue
        infra, repro = _observation_failures(observation, scenario=scenario, candidate=candidate)
        infrastructure_failures.extend(f"{prefix}: {message}" for message in infra)
        reproducibility_failures.extend(f"{prefix}: {message}" for message in repro)

        job_id = observation.get("job_id")
        if isinstance(job_id, str) and job_id.strip():
            if job_id in seen_job_ids:
                reproducibility_failures.append(f"{prefix}: duplicate job_id {job_id!r}")
                continue
            seen_job_ids.add(job_id)

        attempt = observation.get("attempt")
        if isinstance(attempt, int) and not isinstance(attempt, bool) and attempt > 0:
            attempt_key = (scenario_id, candidate_id, attempt)
            if attempt_key in seen_attempts:
                reproducibility_failures.append(
                    f"{prefix}: duplicate attempt {attempt} for comparison pair"
                )
                continue
            seen_attempts.add(attempt_key)

        per_candidate[candidate_id].append((observation, not infra and not repro, not repro))
        observed_pairs.add((scenario_id, candidate_id))
        if not isinstance(observation.get("would_keep"), bool):
            missing_attempt_reviews.append(
                {
                    "scenario_id": scenario_id,
                    "candidate_id": candidate_id,
                    "job_id": job_id,
                    "attempt": observation.get("attempt"),
                }
            )

    missing_review_pairs = sorted(scheduled_pairs.difference(observed_pairs))
    missing_blind_reviews = list(missing_attempt_reviews)
    missing_blind_reviews.extend(
        {"scenario_id": scenario_id, "candidate_id": candidate_id}
        for scenario_id, candidate_id in missing_review_pairs
    )

    candidate_summaries: list[dict[str, Any]] = []
    for candidate_id, attempts in per_candidate.items():
        reviewed = [
            (item, valid, reproducible)
            for item, valid, reproducible in attempts
            if isinstance(item.get("would_keep"), bool)
        ]
        keepers = [entry for entry in reviewed if entry[0]["would_keep"] is True]
        accepted = [
            item
            for item, valid, _reproducible in keepers
            if valid
            and isinstance(item.get("evaluation"), dict)
            and item["evaluation"].get("passed") is True
        ]
        costs = [
            float(item["settled_cost_usd"])
            for item, _valid, reproducible in attempts
            if reproducible and _is_nonnegative_number(item.get("settled_cost_usd"))
        ]
        latencies = [
            float(item["latency_seconds"])
            for item, _valid, reproducible in attempts
            if reproducible and _is_nonnegative_number(item.get("latency_seconds"))
        ]
        keeper_count = len(keepers)
        accepted_count = len(accepted)
        valid_count = sum(1 for _item, valid, _reproducible in attempts if valid)
        candidate_summaries.append(
            {
                "candidate_id": candidate_id,
                "attempts": len(attempts),
                "reviewed": len(reviewed),
                "evidence_valid_attempts": valid_count,
                "keepers": keeper_count,
                "accepted": accepted_count,
                "keep_rate": (keeper_count / len(reviewed)) if reviewed else None,
                "accepted_rate": (accepted_count / len(reviewed)) if reviewed else None,
                "total_settled_cost_usd": sum(costs),
                "attempts_per_accepted_image": (len(attempts) / accepted_count)
                if accepted_count
                else None,
                "cost_per_accepted_image_usd": (sum(costs) / accepted_count)
                if accepted_count
                else None,
                "latency_p50_seconds": _percentile(latencies, 0.50),
                "latency_p95_seconds": _percentile(latencies, 0.95),
            }
        )

    complete = not (infrastructure_failures or reproducibility_failures or missing_blind_reviews)
    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "run_id": manifest.get("run_id"),
        "complete_for_comparison": complete,
        "infrastructure_failures": infrastructure_failures,
        "reproducibility_failures": reproducibility_failures,
        "missing_blind_reviews": missing_blind_reviews,
        "candidates": candidate_summaries,
    }


def build_blind_review_manifest(
    manifest: dict[str, Any],
    observations: list[dict[str, Any]],
    *,
    shuffle_seed: int = 0,
) -> dict[str, Any]:
    """Build a reviewer-facing manifest with model/provider identity removed."""
    scenarios, _candidates, scheduled_pairs = _validate_manifest(manifest)
    items: list[dict[str, Any]] = []
    for index, observation in enumerate(observations):
        scenario_id = observation.get("scenario_id")
        candidate_id = observation.get("candidate_id")
        if not isinstance(scenario_id, str):
            raise BenchmarkContractError(f"observation {index} has a non-string scenario_id")
        scenario = scenarios.get(scenario_id)
        if scenario is None:
            raise BenchmarkContractError(
                f"observation {index} references unknown scenario {scenario_id!r}"
            )
        if not isinstance(candidate_id, str) or (scenario_id, candidate_id) not in scheduled_pairs:
            raise BenchmarkContractError(
                f"observation {index} references a pair not scheduled by the manifest"
            )
        artifact_id = _nonempty_string(
            observation.get("artifact_id"), f"observation {index} artifact_id"
        )
        artifact_sha = _nonempty_string(
            observation.get("artifact_sha256"),
            f"observation {index} artifact_sha256",
        )
        blind_id = hashlib.sha256(
            f"{manifest.get('run_id')}:{scenario_id}:{artifact_sha}".encode("utf-8")
        ).hexdigest()[:20]
        items.append(
            {
                "blind_id": blind_id,
                "scenario_id": scenario_id,
                "artifact_id": artifact_id,
                "prompt": scenario["prompt"],
                "rating_fields": list(RATING_FIELDS),
            }
        )
    random.Random(shuffle_seed).shuffle(items)
    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "run_id": manifest.get("run_id"),
        "blind": True,
        "items": items,
    }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkContractError(f"cannot load JSON from {path}: {exc}") from exc


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_candidates(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    raise BenchmarkContractError("candidate file must contain one object or a list of objects")


def _load_observations(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if isinstance(payload, dict) and isinstance(payload.get("observations"), list):
        payload = payload["observations"]
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise BenchmarkContractError("observations must be a JSON list of objects")
    return payload


def _parse_assignment_reference(value: str) -> Any:
    from mcp.imagen.face_match import CharacterFaceReference

    parts = value.split(":", 3)
    if len(parts) != 4:
        raise BenchmarkContractError(
            "--assignment-reference must be character_id:cast_slot:position:path, "
            f"got {value!r}"
        )
    character_id, cast_slot, position, path_str = (part.strip() for part in parts)
    if not character_id or not cast_slot:
        raise BenchmarkContractError(
            f"--assignment-reference character_id/cast_slot must be non-empty: {value!r}"
        )
    if position not in {"left", "right"}:
        raise BenchmarkContractError(
            f"--assignment-reference position must be 'left' or 'right', got {position!r}"
        )
    path = Path(path_str)
    if not path.is_file():
        raise BenchmarkContractError(f"--assignment-reference path does not exist: {path}")
    return CharacterFaceReference(
        cast_slot=cast_slot, character_id=character_id, path=path, position=position
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("catalog", help="print the canonical ImageBench scenario catalog")

    evaluate = sub.add_parser("evaluate", help="evaluate one artifact with production scorers")
    evaluate.add_argument("--scenario", required=True, help="exact canonical scenario_id")
    evaluate.add_argument("--image", required=True, type=Path)
    evaluate.add_argument("--output", required=True, type=Path)
    evaluate.add_argument("--identity-reference", type=Path)
    evaluate.add_argument("--identity-threshold", type=float, default=0.45)
    evaluate.add_argument(
        "--assignment-reference",
        action="append",
        default=[],
        metavar="CHARACTER_ID:CAST_SLOT:POSITION:PATH",
        help=(
            "two-character identity assignment reference, repeatable (max 2): "
            "character_id:cast_slot:left|right:path. Required for stage-D scenarios."
        ),
    )
    evaluate.add_argument("--assignment-min-similarity", type=float, default=0.45)
    evaluate.add_argument("--assignment-min-margin", type=float, default=0.05)
    evaluate.add_argument("--auxiliary-image", action="append", type=Path, default=[])
    evaluate.add_argument("--vlm-model")
    evaluate.add_argument("--vlm-model-revision")
    evaluate.add_argument("--vlm-base-url", default="http://127.0.0.1:11434")

    manifest = sub.add_parser("manifest", help="create an offline benchmark run manifest")
    manifest.add_argument("--candidate-file", required=True, type=Path)
    manifest.add_argument("--output", required=True, type=Path)
    manifest.add_argument("--stage", action="append", choices=list("ABCDEFG"))
    manifest.add_argument("--scenario", action="append", help="exact scenario_id; repeatable")
    manifest.add_argument("--seed-base", type=int, default=1000)
    manifest.add_argument("--include-private", action="store_true")

    blind = sub.add_parser("blind", help="create a provider-blind human review manifest")
    blind.add_argument("--manifest", required=True, type=Path)
    blind.add_argument("--observations", required=True, type=Path)
    blind.add_argument("--output", required=True, type=Path)
    blind.add_argument("--shuffle-seed", type=int, default=0)

    report = sub.add_parser("report", help="aggregate keeper rate, gates, economics and latency")
    report.add_argument("--manifest", required=True, type=Path)
    report.add_argument("--observations", required=True, type=Path)
    report.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            print(json.dumps(scenario_catalog(), indent=2))
            return 0
        if args.command == "evaluate":
            from gateway.image_evaluation import EvaluationUnavailable
            from gateway.image_scorers import build_imagebench_scorers

            scenario = next(
                (item for item in scenario_catalog() if item["scenario_id"] == args.scenario),
                None,
            )
            if scenario is None:
                raise BenchmarkContractError(f"unknown canonical scenario_id {args.scenario!r}")
            required = scenario["required_scorers"]
            assignment_references = [
                _parse_assignment_reference(value) for value in args.assignment_reference
            ]
            resolved_ref_paths = [Path(ref.path).resolve() for ref in assignment_references]
            if len(set(resolved_ref_paths)) != len(resolved_ref_paths):
                raise BenchmarkContractError(
                    "--assignment-reference paths must be distinct files — scoring "
                    "two characters against the same photo would silently prove nothing"
                )
            scorers = build_imagebench_scorers(
                required_scorers=required,
                prompt=scenario["prompt"],
                identity_reference_path=(
                    str(args.identity_reference) if args.identity_reference is not None else None
                ),
                identity_threshold=args.identity_threshold,
                assignment_references=assignment_references,
                assignment_min_similarity=args.assignment_min_similarity,
                assignment_min_margin=args.assignment_min_margin,
                auxiliary_image_paths=[str(path) for path in args.auxiliary_image],
                vlm_model=args.vlm_model,
                vlm_model_revision=args.vlm_model_revision,
                vlm_base_url=args.vlm_base_url,
            )
            try:
                payload = evaluate_artifact_for_scenario(scenario, args.image, scorers=scorers)
            except EvaluationUnavailable as exc:
                raise BenchmarkContractError(str(exc)) from exc
            _write_json(args.output, payload)
            return 0
        if args.command == "manifest":
            payload = build_run_manifest(
                _load_candidates(args.candidate_file),
                stages=args.stage,
                scenario_ids=args.scenario,
                seed_base=args.seed_base,
                include_private=args.include_private,
            )
            _write_json(args.output, payload)
            return 0
        manifest = _load_json(args.manifest)
        observations = _load_observations(args.observations)
        if args.command == "blind":
            _write_json(
                args.output,
                build_blind_review_manifest(manifest, observations, shuffle_seed=args.shuffle_seed),
            )
            return 0
        if args.command == "report":
            report = summarize_run(manifest, observations)
            _write_json(args.output, report)
            return 0 if report["complete_for_comparison"] else 2
    except BenchmarkContractError as exc:
        parser.error(str(exc))
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
