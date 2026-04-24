"""Phase 4: Reliability + Eval Platform tests.

Primary test command:
    /opt/homebrew/bin/python3.12 -m pytest tests/test_reliability_platform.py -q
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


# ── Task 1: Eval Domain Model ─────────────────────────────────────────────────

class TestEvalDomainModel:
    def test_unique_run_ids(self):
        from src.core.eval_domain import EvalRun
        r1 = EvalRun.start("smoke")
        r2 = EvalRun.start("smoke")
        assert r1.run_id != r2.run_id

    def test_run_has_suite_and_timestamp(self):
        from src.core.eval_domain import EvalRun
        run = EvalRun.start("smoke")
        assert run.suite == "smoke"
        assert run.started_at > 0

    def test_check_record_pass(self):
        from src.core.eval_domain import EvalCheck
        check = EvalCheck.record("capabilities_200", True)
        assert check.passed is True
        assert check.name == "capabilities_200"

    def test_check_record_fail_with_reason(self):
        from src.core.eval_domain import EvalCheck
        check = EvalCheck.record("capabilities_200", False, "got 500")
        assert check.passed is False
        assert check.reason == "got 500"

    def test_score_rate(self):
        from src.core.eval_domain import EvalScore
        score = EvalScore(passed=4, total=5)
        assert score.rate == pytest.approx(0.8)

    def test_score_meets_baseline(self):
        from src.core.eval_domain import EvalScore
        score = EvalScore(passed=5, total=5)
        assert score.meets_baseline(0.95) is True

    def test_score_fails_baseline(self):
        from src.core.eval_domain import EvalScore
        score = EvalScore(passed=4, total=5)
        assert score.meets_baseline(0.95) is False

    def test_score_zero_total_is_zero(self):
        from src.core.eval_domain import EvalScore
        assert EvalScore(passed=0, total=0).rate == 0.0

    def test_result_to_dict_is_json_serializable(self):
        from src.core.eval_domain import EvalCheck, EvalResult, EvalRun, EvalScore
        run = EvalRun.start("smoke")
        checks = [EvalCheck.record("ok", True)]
        result = EvalResult(run=run, checks=checks, scores={"smoke": EvalScore(1, 1)})
        d = result.to_dict()
        json.dumps(d)  # must not raise
        assert d["run_id"] == run.run_id
        assert d["suite"] == "smoke"
        assert d["scores"]["smoke"]["rate"] == pytest.approx(1.0)
        assert len(d["checks"]) == 1


# ── Task 2: Smoke Suite ───────────────────────────────────────────────────────

class TestSmokeSuite:
    def test_smoke_suite_runs_without_network(self, app):
        from evals.smoke_suite import run_smoke_suite
        result = run_smoke_suite(app, baseline=0.0)
        assert result is not None
        assert "smoke" in result.scores

    def test_smoke_suite_writes_exactly_one_artifact(self, app):
        from evals.smoke_suite import run_smoke_suite
        with tempfile.TemporaryDirectory() as tmp:
            run_smoke_suite(app, artifact_dir=Path(tmp), baseline=0.0)
            artifacts = list(Path(tmp).glob("*.json"))
            assert len(artifacts) == 1

    def test_artifact_matches_expected_shape(self, app):
        from evals.smoke_suite import run_smoke_suite
        with tempfile.TemporaryDirectory() as tmp:
            result = run_smoke_suite(app, artifact_dir=Path(tmp), baseline=0.0)
            artifact = next(Path(tmp).glob("*.json"))
            data = json.loads(artifact.read_text())
            assert "run_id" in data
            assert "suite" in data
            assert "scores" in data
            assert "checks" in data
            assert data["run_id"] == result.run.run_id

    def test_smoke_suite_raises_below_baseline(self, app):
        from evals.smoke_suite import SmokeBaselineError, run_smoke_suite
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(SmokeBaselineError):
                run_smoke_suite(app, baseline=1.1, artifact_dir=Path(tmp))


# ── Task 3: Regression Detection ─────────────────────────────────────────────

class TestRegressionDetection:
    def test_score_drop_above_threshold_is_regression(self, tmp_path):
        from evals.compare_runs import detect_regression
        prev = {"suite": "smoke", "run_id": "abc", "scores": {"smoke": {"rate": 1.0}}}
        (tmp_path / "abc_smoke.json").write_text(json.dumps(prev))
        result = detect_regression(tmp_path, {"smoke": 0.8}, suite="smoke", threshold=0.05)
        assert result["is_regression"] is True
        assert result["delta"] == pytest.approx(-0.2)
        assert "prev_run_id" in result

    def test_score_drop_at_or_below_threshold_is_not_regression(self, tmp_path):
        from evals.compare_runs import detect_regression
        prev = {"suite": "smoke", "run_id": "abc", "scores": {"smoke": {"rate": 0.95}}}
        (tmp_path / "abc_smoke.json").write_text(json.dumps(prev))
        result = detect_regression(tmp_path, {"smoke": 0.91}, suite="smoke", threshold=0.05)
        assert result["is_regression"] is False

    def test_no_prior_artifact_is_not_regression(self, tmp_path):
        from evals.compare_runs import detect_regression
        result = detect_regression(tmp_path, {"smoke": 0.9}, suite="smoke")
        assert result["is_regression"] is False
        assert "reason" in result


# ── Task 4: Eval Trigger Route ────────────────────────────────────────────────

class TestEvalRoute:
    def test_smoke_run_returns_score_payload(self, client):
        resp = client.post("/api/eval/run", json={"suite": "smoke"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "run_id" in data
        assert "score" in data
        assert "rate" in data["score"]

    def test_unknown_suite_returns_400(self, client):
        resp = client.post("/api/eval/run", json={"suite": "nonexistent"})
        assert resp.status_code == 400

    def test_missing_suite_returns_400(self, client):
        resp = client.post("/api/eval/run", json={})
        assert resp.status_code == 400

    def test_baseline_failure_returns_422(self, client_broken):
        resp = client_broken.post("/api/eval/run", json={"suite": "smoke"})
        assert resp.status_code == 422


# ── Task 5: Persona Fixtures + Daily Summary ──────────────────────────────────

class TestPersonaSuite:
    def test_persona_fixture_loads(self):
        from evals.persona_suite import load_personas
        personas = load_personas()
        assert len(personas) >= 2
        for p in personas:
            assert "id" in p
            assert "prompt" in p

    def test_persona_suite_produces_structured_results(self, app):
        from evals.persona_suite import run_persona_suite
        results = run_persona_suite(app)
        assert len(results) >= 1
        for r in results:
            assert "persona_id" in r
            assert "passed" in r
            assert "run_id" in r
            assert "prompt" in r

    def test_daily_summary_returns_path(self, tmp_path, app):
        from evals.persona_suite import generate_daily_summary
        result = generate_daily_summary(app, report_dir=tmp_path)
        assert result is not None


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def app():
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from web import create_app
    flask_app, _ = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def app_broken():
    from web import create_app
    flask_app, _ = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["EVAL_BASELINE"] = 1.1  # impossible threshold → always 422
    return flask_app


@pytest.fixture
def client_broken(app_broken):
    return app_broken.test_client()
