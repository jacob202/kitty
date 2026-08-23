from __future__ import annotations

import copy

import pytest

from scripts import image_lab_benchmark as bench


def _candidate(candidate_id: str = "airforce-grok-2") -> dict:
    return {
        "candidate_id": candidate_id,
        "provider": "airforce",
        "model": "grok-imagine-image-2.0",
        "revision": "provider-managed",
        "compiler": "provider-native@1",
        "workflow": "hosted-generic@1",
        "reference_strategy": "none",
        "quantization": "provider-managed",
        "content_lanes": ["safe"],
        "settings": {"quality": "quality"},
    }


def _observation(
    manifest: dict, *, keep: bool = True, cost: float = 0.04, latency: float = 10.0
) -> dict:
    item = manifest["items"][0]
    scenario = next(s for s in manifest["scenarios"] if s["scenario_id"] == item["scenario_id"])
    candidate = next(c for c in manifest["candidates"] if c["candidate_id"] == item["candidate_id"])
    scorers = scenario["required_scorers"]
    return {
        "scenario_id": item["scenario_id"],
        "candidate_id": item["candidate_id"],
        "attempt": 1,
        "job_id": "job_123",
        "plan_id": "imgplan_123",
        "intent_sha256": "a" * 64,
        "artifact_id": "artifact_image_job_123",
        "artifact_sha256": "b" * 64,
        "provider": candidate["provider"],
        "model": candidate["model"],
        "revision": candidate["revision"],
        "compiler": candidate["compiler"],
        "workflow": candidate["workflow"],
        "reference_strategy": candidate["reference_strategy"],
        "quantization": candidate["quantization"],
        "candidate_sha256": candidate["candidate_sha256"],
        "settled_cost_usd": cost,
        "cost_source": "provider_reported",
        "latency_seconds": latency,
        "evaluation": {
            "passed": True,
            "dimensions": {name: 0.9 for name in scorers},
            "scorer_versions": {name: f"{name}@1" for name in scorers},
            "labels": [],
        },
        "would_keep": keep,
    }


def test_catalog_covers_all_required_imagebench_stages() -> None:
    catalog = bench.scenario_catalog()
    assert {s["stage"] for s in catalog} == set("ABCDEFG")
    assert any(s["scenario_id"] == "A.natural_daylight_portrait" for s in catalog)
    assert any(s["scenario_id"] == "A.body_hair" for s in catalog)
    assert any(s["scenario_id"] == "B.body_build_change" for s in catalog)
    assert any(s["scenario_id"] == "C.pose_reference" for s in catalog)
    assert any(s["scenario_id"] == "D.occlusion" for s in catalog)
    assert any(s["scenario_id"] == "E.single_property_edit" for s in catalog)
    assert any(s["scenario_id"] == "F.foreshortening" for s in catalog)
    assert any(s["scenario_id"] == "G.raw_vs_pipeline" for s in catalog)


def test_private_adult_scenario_is_opt_in_only() -> None:
    candidate = {**_candidate(), "content_lanes": ["safe", "private_adult"]}
    normal = bench.build_run_manifest([candidate], stages=["D"], seed_base=100)
    private = bench.build_run_manifest(
        [candidate], stages=["D"], seed_base=100, include_private=True
    )
    assert all(item["content_lane"] == "safe" for item in normal["items"])
    assert any(item["content_lane"] == "private_adult" for item in private["items"])


def test_private_scenario_refuses_candidate_without_private_lane() -> None:
    with pytest.raises(bench.BenchmarkContractError, match="private_adult"):
        bench.build_run_manifest(
            [_candidate()],
            scenario_ids=["D.private_adult_control"],
            include_private=True,
        )


def test_private_scenario_accepts_explicit_private_executor_candidate() -> None:
    candidate = {
        **_candidate("private-worker"),
        "provider": "kitty_worker",
        "model": "private-workflow",
        "content_lanes": ["safe", "private_adult"],
    }
    manifest = bench.build_run_manifest(
        [candidate],
        scenario_ids=["D.private_adult_control"],
        include_private=True,
    )
    assert manifest["items"] == [
        {
            "scenario_id": "D.private_adult_control",
            "candidate_id": "private-worker",
            "seed": 1000,
            "content_lane": "private_adult",
        }
    ]


def test_manifest_pins_exact_candidate_and_uses_same_scenario_seed_across_candidates() -> None:
    c1 = _candidate("candidate-a")
    c2 = {**_candidate("candidate-b"), "model": "another-exact-model"}
    manifest = bench.build_run_manifest([c1, c2], stages=["A"], seed_base=700)

    assert manifest["schema_version"] == bench.BENCHMARK_SCHEMA_VERSION
    assert [c["candidate_id"] for c in manifest["candidates"]] == ["candidate-a", "candidate-b"]
    assert all(len(c["candidate_sha256"]) == 64 for c in manifest["candidates"])
    first_scenario = manifest["scenarios"][0]["scenario_id"]
    seeds = {item["seed"] for item in manifest["items"] if item["scenario_id"] == first_scenario}
    assert seeds == {700}


def test_candidate_without_exact_revision_is_rejected() -> None:
    candidate = _candidate()
    candidate["revision"] = ""
    with pytest.raises(bench.BenchmarkContractError, match="revision"):
        bench.build_run_manifest([candidate], stages=["A"])


def test_blind_review_manifest_hides_candidate_and_provider_identity() -> None:
    manifest = bench.build_run_manifest([_candidate()], stages=["A"], seed_base=1)
    observations = [_observation(manifest)]
    review = bench.build_blind_review_manifest(manifest, observations, shuffle_seed=7)

    assert review["run_id"] == manifest["run_id"]
    assert len(review["items"]) == 1
    item = review["items"][0]
    assert set(item) == {"blind_id", "scenario_id", "artifact_id", "prompt", "rating_fields"}
    assert "candidate" not in str(item).lower()
    assert "airforce" not in str(item).lower()
    assert "grok" not in str(item).lower()


def test_report_computes_keeper_economics_and_latency() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()],
        scenario_ids=["A.natural_daylight_portrait"],
        seed_base=1,
    )
    obs1 = _observation(manifest, keep=False, cost=0.03, latency=8.0)
    obs2 = copy.deepcopy(obs1)
    obs2.update(
        attempt=2,
        job_id="job_456",
        artifact_id="artifact_image_job_456",
        artifact_sha256="c" * 64,
        settled_cost_usd=0.05,
        latency_seconds=12.0,
        would_keep=True,
    )

    report = bench.summarize_run(manifest, [obs1, obs2])
    summary = report["candidates"][0]
    assert summary["attempts"] == 2
    assert summary["keepers"] == 1
    assert summary["keep_rate"] == pytest.approx(0.5)
    assert summary["total_settled_cost_usd"] == pytest.approx(0.08)
    assert summary["attempts_per_accepted_image"] == pytest.approx(2.0)
    assert summary["cost_per_accepted_image_usd"] == pytest.approx(0.08)
    assert summary["latency_p50_seconds"] == pytest.approx(10.0)
    assert summary["latency_p95_seconds"] == pytest.approx(11.8)
    assert report["complete_for_comparison"] is True


def test_missing_required_scorer_is_infrastructure_failure_not_pass() -> None:
    manifest = bench.build_run_manifest([_candidate()], stages=["A"], seed_base=1)
    observation = _observation(manifest)
    required = manifest["scenarios"][0]["required_scorers"][0]
    observation["evaluation"]["scorer_versions"].pop(required)
    observation["evaluation"]["dimensions"].pop(required)

    report = bench.summarize_run(manifest, [observation])
    assert report["complete_for_comparison"] is False
    assert report["infrastructure_failures"]
    assert required in report["infrastructure_failures"][0]


def test_missing_reproducibility_provenance_blocks_comparison() -> None:
    manifest = bench.build_run_manifest([_candidate()], stages=["A"], seed_base=1)
    observation = _observation(manifest)
    observation["plan_id"] = None

    report = bench.summarize_run(manifest, [observation])
    assert report["complete_for_comparison"] is False
    assert report["reproducibility_failures"]
    assert "plan_id" in report["reproducibility_failures"][0]


def test_observation_candidate_identity_must_match_manifest() -> None:
    manifest = bench.build_run_manifest([_candidate()], stages=["A"], seed_base=1)
    observation = _observation(manifest)
    observation["model"] = "wrong-model"

    report = bench.summarize_run(manifest, [observation])
    assert report["complete_for_comparison"] is False
    assert any("model" in failure for failure in report["reproducibility_failures"])


def test_artifact_evaluation_delegates_to_fail_closed_canonical_evaluator(tmp_path) -> None:
    from gateway.image_evaluation import EvaluationUnavailable

    image = tmp_path / "candidate.png"
    image.write_bytes(b"not-read-by-stub")
    scenario = next(
        s for s in bench.scenario_catalog() if s["scenario_id"] == "A.natural_daylight_portrait"
    )

    with pytest.raises(EvaluationUnavailable, match="required scorers unavailable"):
        bench.evaluate_artifact_for_scenario(scenario, image, scorers={})


def test_artifact_evaluation_returns_versioned_canonical_evidence(tmp_path) -> None:
    from gateway.image_evaluation import ScorerResult

    image = tmp_path / "candidate.png"
    image.write_bytes(b"not-read-by-stub")
    scenario = next(
        s for s in bench.scenario_catalog() if s["scenario_id"] == "A.natural_daylight_portrait"
    )
    scorers = {
        name: (lambda _path, name=name: ScorerResult(True, 0.9, f"{name}@1"))
        for name in scenario["required_scorers"]
    }

    evidence = bench.evaluate_artifact_for_scenario(scenario, image, scorers=scorers)
    assert evidence["passed"] is True
    assert set(evidence["scorer_versions"]) == set(scenario["required_scorers"])


def test_manifest_cli_can_select_one_named_scenario(tmp_path) -> None:
    candidate_file = tmp_path / "candidate.json"
    output = tmp_path / "manifest.json"
    candidate_file.write_text(__import__("json").dumps(_candidate()), encoding="utf-8")

    rc = bench.main(
        [
            "manifest",
            "--candidate-file",
            str(candidate_file),
            "--output",
            str(output),
            "--scenario",
            "A.natural_daylight_portrait",
            "--seed-base",
            "17",
        ]
    )

    payload = __import__("json").loads(output.read_text(encoding="utf-8"))
    assert rc == 0
    assert [s["scenario_id"] for s in payload["scenarios"]] == ["A.natural_daylight_portrait"]
    assert {item["seed"] for item in payload["items"]} == {17}


def test_each_observed_attempt_requires_its_own_blind_keep_review() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    reviewed = _observation(manifest, keep=True)
    unreviewed = copy.deepcopy(reviewed)
    unreviewed.update(
        attempt=2,
        job_id="job_unreviewed",
        artifact_id="artifact_image_job_unreviewed",
        artifact_sha256="d" * 64,
    )
    unreviewed.pop("would_keep")

    report = bench.summarize_run(manifest, [reviewed, unreviewed])
    assert report["complete_for_comparison"] is False
    assert any(item.get("job_id") == "job_unreviewed" for item in report["missing_blind_reviews"])


def test_required_gate_failure_is_not_an_accepted_image_even_if_human_would_keep() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    observation = _observation(manifest, keep=True, cost=0.07)
    observation["evaluation"]["passed"] = False

    report = bench.summarize_run(manifest, [observation])
    summary = report["candidates"][0]
    assert summary["keepers"] == 1
    assert summary["accepted"] == 0
    assert summary["keep_rate"] == pytest.approx(1.0)
    assert summary["accepted_rate"] == pytest.approx(0.0)
    assert summary["attempts_per_accepted_image"] is None
    assert summary["cost_per_accepted_image_usd"] is None


def test_duplicate_job_evidence_blocks_comparison_and_cannot_double_count_cost() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    first = _observation(manifest, keep=True, cost=0.04)
    duplicate = copy.deepcopy(first)
    duplicate["attempt"] = 2

    report = bench.summarize_run(manifest, [first, duplicate])
    assert report["complete_for_comparison"] is False
    assert any("duplicate job_id" in failure for failure in report["reproducibility_failures"])
    assert report["candidates"][0]["total_settled_cost_usd"] == pytest.approx(0.04)


def test_candidate_fingerprint_covers_settings_and_quantization() -> None:
    first = bench.build_run_manifest([_candidate()], scenario_ids=["A.natural_daylight_portrait"])[
        "candidates"
    ][0]
    changed_settings = _candidate()
    changed_settings["settings"] = {"quality": "final"}
    second = bench.build_run_manifest(
        [changed_settings], scenario_ids=["A.natural_daylight_portrait"]
    )["candidates"][0]
    changed_quant = _candidate()
    changed_quant["quantization"] = "int8"
    third = bench.build_run_manifest([changed_quant], scenario_ids=["A.natural_daylight_portrait"])[
        "candidates"
    ][0]

    assert (
        len({first["candidate_sha256"], second["candidate_sha256"], third["candidate_sha256"]}) == 3
    )


def test_observation_with_wrong_candidate_fingerprint_blocks_comparison() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    observation = _observation(manifest)
    observation["candidate_sha256"] = "f" * 64

    report = bench.summarize_run(manifest, [observation])
    assert report["complete_for_comparison"] is False
    assert any("candidate_sha256" in failure for failure in report["reproducibility_failures"])


def test_cost_requires_explicit_settlement_source() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    observation = _observation(manifest)
    observation["cost_source"] = ""

    report = bench.summarize_run(manifest, [observation])
    assert report["complete_for_comparison"] is False
    assert any("cost_source" in failure for failure in report["reproducibility_failures"])


def test_malformed_provenance_hash_blocks_comparison() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    observation = _observation(manifest)
    observation["artifact_sha256"] = "not-a-sha"

    report = bench.summarize_run(manifest, [observation])
    assert report["complete_for_comparison"] is False
    assert any("artifact_sha256" in failure for failure in report["reproducibility_failures"])


def test_budget_reservation_is_not_settled_cost_evidence() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    observation = _observation(manifest)
    observation["cost_source"] = "budget_reservation"

    report = bench.summarize_run(manifest, [observation])
    assert report["complete_for_comparison"] is False
    assert any("settled cost source" in failure for failure in report["reproducibility_failures"])


def test_local_zero_marginal_cost_must_actually_be_zero() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    observation = _observation(manifest, cost=0.01)
    observation["cost_source"] = "local_zero_marginal"

    report = bench.summarize_run(manifest, [observation])
    assert report["complete_for_comparison"] is False
    assert any("local_zero_marginal" in failure for failure in report["reproducibility_failures"])


def test_provider_contract_cost_requires_pinned_contract_and_reproduces_amount() -> None:
    candidate = _candidate("fal-contract")
    candidate["provider"] = "fal"
    candidate["model"] = "fal-ai/flux-pulid"
    candidate["settings"] = {
        "cost_contract": {
            "kind": "ceil_output_megapixels",
            "usd_per_megapixel": 0.0333,
            "as_of": "2026-08-23",
        }
    }
    manifest = bench.build_run_manifest([candidate], scenario_ids=["A.natural_daylight_portrait"])
    observation = _observation(manifest, cost=0.0666)
    observation.update(
        cost_source="provider_contract",
        artifact_width=1024,
        artifact_height=1024,
    )

    report = bench.summarize_run(manifest, [observation])
    assert report["complete_for_comparison"] is True
    assert report["candidates"][0]["total_settled_cost_usd"] == pytest.approx(0.0666)


def test_provider_contract_cost_fails_when_amount_does_not_match_dimensions() -> None:
    candidate = _candidate("fal-contract")
    candidate["provider"] = "fal"
    candidate["model"] = "fal-ai/flux-pulid"
    candidate["settings"] = {
        "cost_contract": {
            "kind": "ceil_output_megapixels",
            "usd_per_megapixel": 0.0333,
            "as_of": "2026-08-23",
        }
    }
    manifest = bench.build_run_manifest([candidate], scenario_ids=["A.natural_daylight_portrait"])
    observation = _observation(manifest, cost=0.07)
    observation.update(
        cost_source="provider_contract",
        artifact_width=1024,
        artifact_height=1024,
    )

    report = bench.summarize_run(manifest, [observation])
    assert report["complete_for_comparison"] is False
    assert any("provider_contract" in failure for failure in report["reproducibility_failures"])


def test_tampered_canonical_scorer_requirements_are_rejected() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    manifest["scenarios"][0]["required_scorers"] = ["mechanics"]

    with pytest.raises(bench.BenchmarkContractError, match="canonical scenario"):
        bench.summarize_run(
            manifest,
            [
                _observation(
                    bench.build_run_manifest(
                        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
                    )
                )
            ],
        )


def test_tampered_manifest_items_cannot_remove_required_comparison_pair() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    manifest["items"] = []

    with pytest.raises(bench.BenchmarkContractError, match="manifest items"):
        bench.summarize_run(manifest, [])


def test_infrastructure_failure_cannot_count_as_accepted() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    observation = _observation(manifest, keep=True, cost=0.04)
    required = manifest["scenarios"][0]["required_scorers"][0]
    observation["evaluation"]["scorer_versions"].pop(required)
    observation["evaluation"]["dimensions"].pop(required)

    report = bench.summarize_run(manifest, [observation])
    assert report["complete_for_comparison"] is False
    assert report["candidates"][0]["accepted"] == 0
    assert report["candidates"][0]["cost_per_accepted_image_usd"] is None


def test_attempt_number_must_be_positive_integer() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    observation = _observation(manifest)
    observation["attempt"] = 0

    report = bench.summarize_run(manifest, [observation])
    assert report["complete_for_comparison"] is False
    assert any("attempt" in failure for failure in report["reproducibility_failures"])


def test_attempt_number_cannot_be_reused_for_same_comparison_pair() -> None:
    manifest = bench.build_run_manifest(
        [_candidate()], scenario_ids=["A.natural_daylight_portrait"]
    )
    first = _observation(manifest)
    second = copy.deepcopy(first)
    second.update(
        job_id="job_second",
        artifact_id="artifact_image_job_second",
        artifact_sha256="e" * 64,
    )

    report = bench.summarize_run(manifest, [first, second])
    assert report["complete_for_comparison"] is False
    assert any("duplicate attempt" in failure for failure in report["reproducibility_failures"])


def test_evaluate_cli_uses_production_scorers_and_writes_versioned_evidence(
    tmp_path, monkeypatch
) -> None:
    from PIL import Image

    import gateway.image_scorers as production_scorers

    image = tmp_path / "candidate.png"
    pixels = Image.new("RGB", (512, 512))
    for y in range(512):
        for x in range(512):
            pixels.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))
    pixels.save(image)
    output = tmp_path / "evaluation.json"

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "YES"}

    class TagsResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "models": [
                    {
                        "name": "qwen2.5-vl:7b",
                        "model": "qwen2.5-vl:7b",
                        "digest": "sha256:abc123",
                    }
                ]
            }

    monkeypatch.setattr(production_scorers.httpx, "get", lambda *args, **kwargs: TagsResponse())
    monkeypatch.setattr(production_scorers.httpx, "post", lambda *args, **kwargs: Response())

    rc = bench.main(
        [
            "evaluate",
            "--scenario",
            "A.natural_daylight_portrait",
            "--image",
            str(image),
            "--output",
            str(output),
            "--vlm-model",
            "qwen2.5-vl:7b",
            "--vlm-model-revision",
            "sha256:abc123",
        ]
    )

    payload = __import__("json").loads(output.read_text(encoding="utf-8"))
    assert rc == 0
    assert payload["passed"] is True
    assert payload["scorer_versions"]["mechanics"] == "mechanics-pil@1"
    assert payload["scorer_versions"]["photorealism"].endswith("@sha256:abc123")


def test_evaluate_cli_fails_closed_when_required_production_scorer_is_unavailable(
    tmp_path,
) -> None:
    from PIL import Image

    image = tmp_path / "candidate.png"
    Image.new("RGB", (512, 512), "white").save(image)
    output = tmp_path / "evaluation.json"

    with pytest.raises(SystemExit) as exc:
        bench.main(
            [
                "evaluate",
                "--scenario",
                "A.natural_daylight_portrait",
                "--image",
                str(image),
                "--output",
                str(output),
            ]
        )

    assert exc.value.code == 2
    assert not output.exists()


def test_assignment_reference_flag_rejects_malformed_value(tmp_path) -> None:
    from PIL import Image

    image = tmp_path / "candidate.png"
    Image.new("RGB", (512, 512), "white").save(image)
    output = tmp_path / "evaluation.json"

    with pytest.raises(SystemExit) as exc:
        bench.main(
            [
                "evaluate",
                "--scenario",
                "D.side_by_side",
                "--image",
                str(image),
                "--output",
                str(output),
                "--assignment-reference",
                "not-enough-parts",
            ]
        )

    assert exc.value.code == 2
    assert not output.exists()


def test_assignment_reference_flag_rejects_bad_position(tmp_path) -> None:
    from PIL import Image

    image = tmp_path / "candidate.png"
    Image.new("RGB", (512, 512), "white").save(image)
    ref = tmp_path / "ref.png"
    Image.new("RGB", (512, 512), "white").save(ref)
    output = tmp_path / "evaluation.json"

    with pytest.raises(SystemExit) as exc:
        bench.main(
            [
                "evaluate",
                "--scenario",
                "D.side_by_side",
                "--image",
                str(image),
                "--output",
                str(output),
                "--assignment-reference",
                f"james:left_slot:middle:{ref}",
            ]
        )

    assert exc.value.code == 2
    assert not output.exists()


def test_assignment_reference_flag_rejects_missing_file(tmp_path) -> None:
    from PIL import Image

    image = tmp_path / "candidate.png"
    Image.new("RGB", (512, 512), "white").save(image)
    output = tmp_path / "evaluation.json"

    with pytest.raises(SystemExit) as exc:
        bench.main(
            [
                "evaluate",
                "--scenario",
                "D.side_by_side",
                "--image",
                str(image),
                "--output",
                str(output),
                "--assignment-reference",
                f"james:left_slot:left:{tmp_path / 'missing.png'}",
            ]
        )

    assert exc.value.code == 2
    assert not output.exists()


def test_assignment_reference_flag_rejects_duplicate_photo(tmp_path) -> None:
    from PIL import Image

    image = tmp_path / "candidate.png"
    Image.new("RGB", (512, 512), "white").save(image)
    ref = tmp_path / "shared.png"
    Image.new("RGB", (512, 512), "white").save(ref)
    output = tmp_path / "evaluation.json"

    with pytest.raises(SystemExit) as exc:
        bench.main(
            [
                "evaluate",
                "--scenario",
                "D.side_by_side",
                "--image",
                str(image),
                "--output",
                str(output),
                "--assignment-reference",
                f"james:left_slot:left:{ref}",
                "--assignment-reference",
                f"arlo:right_slot:right:{ref}",
            ]
        )

    assert exc.value.code == 2
    assert not output.exists()


def test_evaluate_cli_scores_stage_d_two_character_scenario(tmp_path, monkeypatch) -> None:
    from PIL import Image

    import gateway.image_scorers as production_scorers
    from gateway.image_evaluation import ScorerResult as EvalScorerResult
    from mcp.imagen.face_match import FaceScore, MultiFaceAssignmentEvidence

    image = tmp_path / "candidate.png"
    pixels = Image.new("RGB", (512, 512))
    for y in range(512):
        for x in range(512):
            pixels.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))
    pixels.save(image)
    identity_reference = tmp_path / "identity.png"
    Image.new("RGB", (512, 512), "white").save(identity_reference)
    left_ref = tmp_path / "left.png"
    Image.new("RGB", (512, 512), "white").save(left_ref)
    right_ref = tmp_path / "right.png"
    Image.new("RGB", (512, 512), "white").save(right_ref)
    output = tmp_path / "evaluation.json"

    class FakeFaceMatcher:
        def __init__(self, _path):
            pass

        def score(self, _data):
            return FaceScore(similarity=0.9, reference_faces=1, candidate_faces=1)

    assignment_result = EvalScorerResult(
        passed=True,
        score={"expected_subjects": 2, "detected_subjects": 2, "matches": []},
        version="identity-assignment@1",
        labels=[],
    )
    evidence = MultiFaceAssignmentEvidence(
        character_ids=("james", "arlo"),
        detected=(),
        detected_cast_slots=("left_slot", "right_slot"),
        reference_similarity_matrix=((0.9, 0.1), (0.1, 0.9)),
        character_similarity_matrix=((0.9, 0.1), (0.1, 0.9)),
        assignment=assignment_result,
    )

    class FakeMultiFaceMatcher:
        def __init__(self, _references):
            pass

        def score_assignment(self, _data, *, min_similarity, min_margin):
            return evidence

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "YES"}

    class TagsResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "models": [
                    {
                        "name": "qwen2.5-vl:7b",
                        "model": "qwen2.5-vl:7b",
                        "digest": "sha256:abc123",
                    }
                ]
            }

    monkeypatch.setattr(production_scorers, "FaceMatcher", FakeFaceMatcher)
    monkeypatch.setattr(production_scorers, "MultiFaceMatcher", FakeMultiFaceMatcher)
    monkeypatch.setattr(production_scorers.httpx, "get", lambda *args, **kwargs: TagsResponse())
    monkeypatch.setattr(production_scorers.httpx, "post", lambda *args, **kwargs: Response())

    rc = bench.main(
        [
            "evaluate",
            "--scenario",
            "D.side_by_side",
            "--image",
            str(image),
            "--output",
            str(output),
            "--identity-reference",
            str(identity_reference),
            "--assignment-reference",
            f"james:left_slot:left:{left_ref}",
            "--assignment-reference",
            f"arlo:right_slot:right:{right_ref}",
            "--vlm-model",
            "qwen2.5-vl:7b",
            "--vlm-model-revision",
            "sha256:abc123",
        ]
    )

    payload = __import__("json").loads(output.read_text(encoding="utf-8"))
    assert rc == 0
    assert payload["passed"] is True
    assert payload["scorer_versions"]["assignment"] == "assignment-insightface-buffalo_l@1"
    assert payload["dimensions"]["assignment"]["detected_cast_slots"] == [
        "left_slot",
        "right_slot",
    ]


def test_direct_script_evaluate_entrypoint_reaches_fail_closed_scorer_gate(tmp_path) -> None:
    import os
    import subprocess
    import sys

    from PIL import Image

    image = tmp_path / "candidate.png"
    Image.new("RGB", (512, 512), "white").save(image)
    output = tmp_path / "evaluation.json"
    env = os.environ.copy()
    # Keep the child-process safety bootstrap while excluding the repo root:
    # the script must still add its own checkout to sys.path.
    env["PYTHONPATH"] = str(
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "tests"
        / "python_startup"
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/image_lab_benchmark.py",
            "evaluate",
            "--scenario",
            "A.natural_daylight_portrait",
            "--image",
            str(image),
            "--output",
            str(output),
        ],
        cwd=__import__("pathlib").Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 2
    assert "required scorers unavailable: photorealism" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert not output.exists()
