from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

NUMBERED_SOURCES = tuple(f"{index:02d}" for index in range(9))
ALL_CANDIDATES = (*NUMBERED_SOURCES, "WHY")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _validate(corpus: dict[str, Any], observations: dict[str, Any]) -> None:
    if corpus.get("version") != 1:
        raise ValueError("unsupported project-source corpus version")
    if observations.get("corpus_version") != corpus["version"]:
        raise ValueError("observation corpus version does not match")
    case_ids = {case["id"] for case in corpus["cases"]}
    observed = set(observations["retrieval_cases"]) | set(
        observations["no_source_diagnostics"]
    )
    if case_ids != observed:
        raise ValueError("observations must cover every corpus case exactly once")


def score(corpus_path: Path, observations_path: Path) -> dict[str, Any]:
    corpus = _load(corpus_path)
    observations = _load(observations_path)
    _validate(corpus, observations)
    source_cases = [case for case in corpus["cases"] if case["should_retrieve"]]
    no_source_cases = [case for case in corpus["cases"] if not case["should_retrieve"]]

    hit1 = hit3 = preferred1 = preferred3 = 0
    preferred_count = irrelevant_slots = historical_confusions = 0
    top1_counts: Counter[str] = Counter()
    irrelevant_attractors: Counter[str] = Counter()
    top3_slots = token_burden = irrelevant_tokens = 0
    sizes = observations["source_sizes"]
    for case in source_cases:
        observation = observations["retrieval_cases"][case["id"]]
        ranking = observation["ranking"]
        expected = set(case["expected_sources"])
        top3 = ranking[:3]
        if ranking:
            top1_counts[ranking[0]] += 1
        hit1 += int(bool(ranking) and ranking[0] in expected)
        hit3 += int(any(source in expected for source in top3))
        preferred = case.get("preferred_source")
        if preferred:
            preferred_count += 1
            preferred1 += int(bool(ranking) and ranking[0] == preferred)
            preferred3 += int(preferred in top3)
        for source in top3:
            top3_slots += 1
            token_burden += int(sizes[source]["approx_tokens"])
            if source not in expected:
                irrelevant_slots += 1
                irrelevant_attractors[source] += 1
                irrelevant_tokens += int(sizes[source]["approx_tokens"])
        historical_confusions += int(observation["mistook_context_as_live_authority"])

    for case in no_source_cases:
        observation = observations["no_source_diagnostics"][case["id"]]
        historical_confusions += int(observation["mistook_context_as_live_authority"])

    completed_pairs = [
        pair for pair in observations["decision_pairs"] if pair["status"] == "complete"
    ]
    pair_models = sorted({pair["model"] for pair in completed_pairs})
    why = observations["why_check"]
    return {
        "retrieval": {
            "source_case_count": len(source_cases),
            "no_source_case_count": len(no_source_cases),
            "acceptable_hit_at_1": _ratio(hit1, len(source_cases)),
            "acceptable_hit_at_3": _ratio(hit3, len(source_cases)),
            "preferred_hit_at_1": _ratio(preferred1, preferred_count),
            "preferred_hit_at_3": _ratio(preferred3, preferred_count),
            "irrelevant_top3_rate": _ratio(irrelevant_slots, top3_slots),
            "historical_as_live_authority_count": historical_confusions,
            "live_abstention_verified": bool(observations["live_abstention_verified"]),
            "top1_counts": dict(sorted(top1_counts.items())),
            "irrelevant_attractor_counts": dict(sorted(irrelevant_attractors.items())),
        },
        "context_burden": {
            "approx_full_source_tokens": token_burden,
            "approx_irrelevant_tokens": irrelevant_tokens,
            "approx_irrelevant_token_rate": _ratio(irrelevant_tokens, token_burden),
        },
        "decision_pairs": {
            "completed_pairs": len(completed_pairs),
            "decision_changed": sum(pair["decision_changed"] for pair in completed_pairs),
            "material_improvements": sum(
                pair["material_improvement"] for pair in completed_pairs
            ),
            "regressions": sum(pair["regression"] for pair in completed_pairs),
            "models": pair_models,
            "evidence_type": "qualitative",
        },
        "coverage": {
            "missing_durable_category_detected": observations[
                "missing_durable_category_detected"
            ],
            "duplicate_source_hash_count": (
                len(sizes) - len({meta["sha256"] for meta in sizes.values()})
            ),
        },
        "why_check": {
            "unique_signal_hit_at_1": why["target_with_why"][0] == "WHY",
            "generic_purpose_top4_contains_why": "WHY" in why["generic_purpose"][:4],
            "non_target_top3_attractor_count": sum(
                "WHY" in ranking[:3] for ranking in why["non_target_rankings"]
            ),
            "numbered_fallback_hit_at_1": (
                bool(why["target_without_why"])
                and why["target_without_why"][0] in NUMBERED_SOURCES
            ),
        },
    }


def recommendations(metrics: dict[str, Any]) -> dict[str, bool]:
    missing = metrics["coverage"]["missing_durable_category_detected"]
    retrieval = metrics["retrieval"]
    why = metrics["why_check"]
    retrieval_precise_enough = (
        retrieval["preferred_hit_at_1"] >= 0.8
        and retrieval["irrelevant_top3_rate"] <= 0.25
    )
    return {
        "add_new_numbered_source": bool(missing),
        "freeze_numbered_pack_against_expansion": not missing,
        "freeze_retrieval_configuration": retrieval_precise_enough,
        "keep_why_as_preserved_narrative": why["unique_signal_hit_at_1"],
        "include_why_in_default_retrieval": (
            why["unique_signal_hit_at_1"]
            and not why["numbered_fallback_hit_at_1"]
            and why["non_target_top3_attractor_count"] == 0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    args = parser.parse_args()
    metrics = score(args.corpus, args.observations)
    print(json.dumps({"metrics": metrics, "recommendations": recommendations(metrics)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
