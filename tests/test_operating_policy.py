from __future__ import annotations

from copy import deepcopy

import pytest

from gateway.operating_policy import (
    OperatingPolicyError,
    evaluate_builder_campaign,
    evaluate_model_candidate,
    load_builder_policy,
    load_model_policy,
    resolve_character_for_engine,
    validate_character_contract,
)


def _model_metrics(**overrides):
    metrics = {
        "sample_size": 40,
        "repeat_windows": 2,
        "accepted_outcome_rate": 0.80,
        "cost_per_accepted_outcome": 1.00,
        "median_time_to_accepted_outcome": 100.0,
        "malformed_rate": 0.01,
        "tool_success_rate": 0.95,
        "critical_regressions": 0,
    }
    metrics.update(overrides)
    return metrics


def _character() -> dict:
    return {
        "schema_version": 1,
        "character_id": "char_jacob",
        "name": "Jacob",
        "description": {
            "appearance": "late-thirties man with short salt-and-pepper hair",
            "preserve": ["natural asymmetry", "apparent age", "body hair"],
            "exclude": ["beautification", "plastic skin"],
        },
        "identity": {
            "method": "pulid",
            "base_family": "flux",
            "adapter_model": "pulid_flux_v0.9.1.safetensors",
            "adapter_strength": 0.95,
            "fusion_method": "weighted_mean",
            "allow_generated_derivatives": False,
            "references": [
                {
                    "ref_id": "front",
                    "purpose": "primary_face",
                    "provenance": "real_photo",
                    "enabled": True,
                    "weight": 0.7,
                    "face_weight": 1.0,
                    "body_weight": 0.2,
                    "quality_score": 0.9,
                    "notes": None,
                },
                {
                    "ref_id": "profile",
                    "purpose": "profile",
                    "provenance": "real_photo",
                    "enabled": True,
                    "weight": 0.3,
                    "face_weight": 0.8,
                    "body_weight": 0.0,
                    "quality_score": 0.8,
                    "notes": None,
                },
            ],
        },
        "prompt": {
            "positive": "natural skin texture, documentary photograph",
            "negative": "rejuvenated, symmetrical face, waxy skin",
        },
        "recipe": {
            "recipe_id": "flux-pulid-jacob-v1",
            "engine": "comfyui",
            "sampler": "euler",
            "scheduler": "simple",
            "steps": 26,
            "guidance": 3.0,
            "denoise": 1.0,
        },
    }


def _engine_capabilities(**overrides) -> dict:
    capabilities = {
        "engine": "comfyui",
        "base_families": ["flux"],
        "identity_methods": ["pulid"],
        "fusion_methods": ["weighted_mean"],
        "maximum_references": 4,
        "per_reference_weights": True,
        "per_region_weights": True,
        "adapter_models": ["pulid_flux_v0.9.1.safetensors"],
    }
    capabilities.update(overrides)
    return capabilities


def _full_builder_metrics(**overrides) -> dict:
    metrics = {
        "elapsed_seconds": 1800,
        "processed_packets": 1,
        "accepted_packets": 1,
        "current_packet_elapsed_seconds": 300,
        "consecutive_no_substantive_diff": 0,
        "setup_metadata_seconds": 200,
        "supervisor_tokens": 1000,
        "worker_tokens": 3000,
        "reset_recovery_events": 0,
        "repeated_systemic_blocker_count": 0,
        "projected_completion_seconds": 1800,
        "simple_baseline_seconds": 1800,
    }
    metrics.update(overrides)
    return metrics


def test_checked_in_policies_are_valid():
    model_policy = load_model_policy()
    builder_policy = load_builder_policy()

    assert set(model_policy["roles"]) == {"auto", "fast", "think", "code", "vision"}
    assert builder_policy["decision"]["on_tripwire"] == "pause"


def test_model_candidate_can_win_on_quality():
    incumbent = _model_metrics()
    candidate = _model_metrics(accepted_outcome_rate=0.87, cost_per_accepted_outcome=1.10)

    decision = evaluate_model_candidate("code", incumbent, candidate)

    assert decision.status == "promote"
    assert decision.reasons == ()


def test_model_candidate_can_win_on_cost_at_quality_parity():
    incumbent = _model_metrics()
    candidate = _model_metrics(
        accepted_outcome_rate=0.79,
        cost_per_accepted_outcome=0.70,
    )

    assert evaluate_model_candidate("fast", incumbent, candidate).status == "promote"


def test_cheaper_tokens_do_not_win_when_success_collapses():
    incumbent = _model_metrics()
    candidate = _model_metrics(
        accepted_outcome_rate=0.60,
        cost_per_accepted_outcome=0.10,
        median_time_to_accepted_outcome=50.0,
    )

    decision = evaluate_model_candidate("fast", incumbent, candidate)

    assert decision.status == "reject"
    assert any("accepted outcomes" in reason for reason in decision.reasons)


def test_model_promotion_requires_repeated_representative_evidence():
    incumbent = _model_metrics()
    candidate = _model_metrics(sample_size=8, repeat_windows=1, accepted_outcome_rate=0.95)

    decision = evaluate_model_candidate("think", incumbent, candidate)

    assert decision.status == "reject"
    assert any("representative set" in reason for reason in decision.reasons)
    assert any("evaluation windows" in reason for reason in decision.reasons)


def test_model_metrics_reject_nan_instead_of_comparing_it():
    with pytest.raises(OperatingPolicyError, match="finite number"):
        evaluate_model_candidate(
            "fast",
            _model_metrics(),
            _model_metrics(cost_per_accepted_outcome=float("nan")),
        )


def test_twenty_four_hours_for_seven_packets_is_an_automatic_pause():
    decision = evaluate_builder_campaign(
        _full_builder_metrics(
            elapsed_seconds=24 * 3600,
            processed_packets=7,
            accepted_packets=7,
            current_packet_elapsed_seconds=1800,
            setup_metadata_seconds=8 * 3600,
            supervisor_tokens=1_000_000,
            worker_tokens=800_000,
            reset_recovery_events=8,
            repeated_systemic_blocker_count=4,
            projected_completion_seconds=24 * 3600,
            simple_baseline_seconds=3 * 3600,
        )
    )

    assert decision.status == "pause"
    joined = " | ".join(decision.reasons)
    assert "wall-clock" in joined
    assert "throughput" in joined
    assert "setup and metadata" in joined
    assert "reset/recovery" in joined
    assert "simple-agent baseline" in joined


def test_builder_metrics_never_invent_missing_evidence_before_observation_window():
    decision = evaluate_builder_campaign(
        {
            "elapsed_seconds": 100,
            "processed_packets": 0,
            "accepted_packets": 0,
        }
    )

    assert decision.status == "continue"
    assert "worker_tokens" in decision.missing_metrics
    assert "setup_metadata_seconds" in decision.missing_metrics


def test_missing_core_builder_metrics_are_not_treated_as_continue():
    decision = evaluate_builder_campaign({"processed_packets": 1, "accepted_packets": 0})

    assert decision.status == "insufficient_evidence"
    assert "elapsed_seconds" in decision.missing_metrics


def test_missing_required_telemetry_pauses_after_observation_window():
    decision = evaluate_builder_campaign(
        {
            "elapsed_seconds": 3600,
            "processed_packets": 2,
            "accepted_packets": 2,
        }
    )

    assert decision.status == "pause"
    assert any("telemetry is missing" in reason for reason in decision.reasons)


def test_character_contract_makes_description_and_reference_policy_explicit():
    validate_character_contract(_character())


def test_character_rejects_generated_derivatives_unless_explicitly_allowed():
    character = _character()
    character["identity"]["references"][1]["provenance"] = "generated_derivative"

    with pytest.raises(OperatingPolicyError, match="generated derivative"):
        validate_character_contract(character)


def test_character_requires_exactly_one_primary_reference():
    character = _character()
    character["identity"]["references"][1]["purpose"] = "primary_face"

    with pytest.raises(OperatingPolicyError, match="exactly one"):
        validate_character_contract(character)


def test_invalid_disabled_reference_is_not_silently_ignored():
    character = _character()
    character["identity"]["references"].append(
        {
            "ref_id": "bad-disabled",
            "purpose": "not-a-purpose",
            "provenance": "real_photo",
            "enabled": False,
            "weight": 0,
            "face_weight": 0,
            "body_weight": 0,
            "quality_score": 0.5,
            "notes": None,
        }
    )

    with pytest.raises(OperatingPolicyError, match="unsupported reference purpose"):
        validate_character_contract(character)


def test_weighted_reference_weights_must_add_to_one():
    character = _character()
    character["identity"]["references"][1]["weight"] = 0.2

    with pytest.raises(OperatingPolicyError, match="add to 1"):
        validate_character_contract(character)


def test_engine_cannot_silently_ignore_per_image_weights():
    with pytest.raises(OperatingPolicyError, match="sliders work"):
        resolve_character_for_engine(
            _character(),
            _engine_capabilities(per_reference_weights=False),
        )


def test_engine_cannot_silently_ignore_face_and_body_weights():
    with pytest.raises(OperatingPolicyError, match="face/body"):
        resolve_character_for_engine(
            _character(),
            _engine_capabilities(per_region_weights=False),
        )


def test_engine_and_character_base_family_must_match():
    with pytest.raises(OperatingPolicyError, match="base family"):
        resolve_character_for_engine(
            _character(),
            _engine_capabilities(base_families=["qwen-image"]),
        )


def test_engine_resolution_returns_the_actual_prompt_and_weights():
    resolved = resolve_character_for_engine(
        deepcopy(_character()),
        _engine_capabilities(),
    )

    assert resolved["identity_method"] == "pulid"
    assert [ref["weight"] for ref in resolved["references"]] == [0.7, 0.3]
    assert "salt-and-pepper" in resolved["positive_prompt"]
    assert resolved["negative_prompt"].startswith("rejuvenated")
