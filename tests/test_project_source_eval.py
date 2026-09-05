from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = ROOT / "evals" / "project_sources"
SCORE_PATH = EVAL_ROOT / "score.py"
CORPUS_PATH = EVAL_ROOT / "corpus.json"
OBSERVATIONS_PATH = EVAL_ROOT / "observations.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_score_module():
    assert SCORE_PATH.exists(), "project-source scorer must exist"
    spec = importlib.util.spec_from_file_location("project_source_score", SCORE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_score_module_exists() -> None:
    load_score_module()


def test_corpus_is_bounded_and_covers_required_categories() -> None:
    corpus = load_json(CORPUS_PATH)
    cases = corpus["cases"]
    assert corpus["version"] == 1
    assert 20 <= len(cases) <= 30
    categories = {case["category"] for case in cases}
    required = {
        "product_purpose",
        "continuity_memory",
        "human_ai_agency",
        "engineering_coordination",
        "security_authorization",
        "false_completion",
        "image_lab",
        "external_evidence",
        "live_state_no_source",
    }
    assert required <= categories
    assert sum(not case["should_retrieve"] for case in cases) >= 5
    assert all("distractor_sources" in case for case in cases)


def test_observations_are_frozen_to_v33_candidate_set() -> None:
    score = load_score_module()
    observations = load_json(OBSERVATIONS_PATH)
    corpus = load_json(CORPUS_PATH)
    assert observations["pack_version"] == "3.3"
    assert observations["corpus_version"] == corpus["version"]
    assert observations["retriever"]["candidate_count"] == 10
    assert set(observations["source_sizes"]) == set(score.ALL_CANDIDATES)
    assert observations["paid_spend_cad"] == 0
    assert all(len(meta["sha256"]) == 64 for meta in observations["source_sizes"].values())


def test_score_reports_frozen_v33_metrics() -> None:
    score = load_score_module()
    metrics = score.score(CORPUS_PATH, OBSERVATIONS_PATH)
    retrieval = metrics["retrieval"]
    burden = metrics["context_burden"]
    assert retrieval["source_case_count"] == 18
    assert retrieval["no_source_case_count"] == 6
    assert retrieval["acceptable_hit_at_1"] == pytest.approx(15 / 18)
    assert retrieval["acceptable_hit_at_3"] == pytest.approx(1.0)
    assert retrieval["preferred_hit_at_1"] == pytest.approx(12 / 18)
    assert retrieval["preferred_hit_at_3"] == pytest.approx(17 / 18)
    assert retrieval["irrelevant_top3_rate"] == pytest.approx(28 / 54)
    assert retrieval["historical_as_live_authority_count"] == 0
    assert burden["approx_full_source_tokens"] == 85332
    assert burden["approx_irrelevant_tokens"] == 44942


def test_decision_pairs_have_one_material_improvement_and_no_regression() -> None:
    score = load_score_module()
    metrics = score.score(CORPUS_PATH, OBSERVATIONS_PATH)
    pairs = metrics["decision_pairs"]
    assert pairs["completed_pairs"] == 4
    assert pairs["decision_changed"] == 0
    assert pairs["material_improvements"] == 2
    assert pairs["regressions"] == 0
    assert pairs["models"] == ["openrouter/nvidia/nemotron-3-super-120b-a12b:free"]


def test_recommendations_follow_measured_evidence() -> None:
    score = load_score_module()
    metrics = score.score(CORPUS_PATH, OBSERVATIONS_PATH)
    recommendations = score.recommendations(metrics)
    assert recommendations == {
        "add_new_numbered_source": False,
        "freeze_numbered_pack_against_expansion": True,
        "freeze_retrieval_configuration": False,
        "keep_why_as_preserved_narrative": True,
        "include_why_in_default_retrieval": False,
    }


def test_methodology_limits_are_explicit_and_sources_are_distinct() -> None:
    score = load_score_module()
    observations = load_json(OBSERVATIONS_PATH)
    hashes = [meta["sha256"] for meta in observations["source_sizes"].values()]
    assert len(hashes) == len(set(hashes))
    metrics = score.score(CORPUS_PATH, OBSERVATIONS_PATH)
    assert metrics["retrieval"]["live_abstention_verified"] is False
    assert metrics["decision_pairs"]["evidence_type"] == "qualitative"
    assert metrics["coverage"]["duplicate_source_hash_count"] == 0
    assert metrics["why_check"]["numbered_fallback_hit_at_1"] is True


def test_overlap_metrics_identify_broad_source_attractors() -> None:
    score = load_score_module()
    metrics = score.score(CORPUS_PATH, OBSERVATIONS_PATH)
    attractors = metrics["retrieval"]["irrelevant_attractor_counts"]
    assert attractors["01"] == 7
    assert attractors["04"] == 5
    assert attractors["05"] == 5
    assert metrics["retrieval"]["top1_counts"]["01"] == 6


def test_eval_notes_avoid_broad_markdown_coordination_scope() -> None:
    assert (EVAL_ROOT / "README.txt").exists()
    assert not (EVAL_ROOT / "README.md").exists()
