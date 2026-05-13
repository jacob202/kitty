"""Smoke eval suite — FastAPI TestClient only, no LiteLLM or external deps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.eval_domain import EvalCheck, EvalResult, EvalRun, EvalScore
from gateway.paths import DATA_DIR

BASELINE = 0.95
DEFAULT_ARTIFACT_DIR = DATA_DIR / "eval_artifacts"
class SmokeBaselineError(Exception):
    """Raised when the smoke suite score drops below the baseline threshold."""


def run_smoke_suite(
    app: FastAPI,
    *,
    artifact_dir: Optional[Path] = None,
    baseline: float = BASELINE,
) -> EvalResult:
    """Run gateway shape checks and write an append-only JSON artifact.

    Pass *baseline*=0.0 in tests that only exercise the harness.
    Artifact naming matches ``scripts/compare_eval_runs.py`` expectations
    (``*{suite}.json`` in the artifact dir).
    """
    artifact_dir = Path(artifact_dir or DEFAULT_ARTIFACT_DIR)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    run = EvalRun.start("smoke")
    checks: list[EvalCheck] = []

    with TestClient(app) as client:
        resp = client.get("/health")
        ok = resp.status_code == 200
        body: dict = {}
        try:
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        except Exception:
            pass
        shape_ok = body.get("status") == "ok" and body.get("service") == "kitty-gateway"
        checks.append(
            EvalCheck.record(
                "health_200",
                ok and shape_ok,
                "" if (ok and shape_ok) else f"status={resp.status_code} body={body}",
            )
        )

        resp = client.post("/v1/audio/transcriptions")
        ok = resp.status_code in (400, 422)
        checks.append(
            EvalCheck.record(
                "transcribe_rejects_missing_file",
                ok,
                "" if ok else f"status={resp.status_code}",
            )
        )

        resp = client.post("/ask", json={})
        ok = resp.status_code in (400, 422)
        checks.append(
            EvalCheck.record(
                "ask_rejects_missing_message",
                ok,
                "" if ok else f"status={resp.status_code}",
            )
        )

        resp = client.get("/openapi.json")
        openapi_ok = False
        detail = ""
        if resp.status_code == 200:
            try:
                data = resp.json()
                openapi_ok = isinstance(data, dict) and bool(data.get("openapi"))
            except Exception as e:
                detail = str(e)
        else:
            detail = f"status={resp.status_code}"
        checks.append(
            EvalCheck.record(
                "openapi_200",
                openapi_ok,
                "" if openapi_ok else detail,
            )
        )

    passed = sum(1 for c in checks if c.passed)
    total = len(checks)
    score = EvalScore(passed=passed, total=total)
    result = EvalResult(run=run, checks=checks, scores={"smoke": score})

    artifact_path = artifact_dir / f"{run.run_id}_smoke.json"
    artifact_path.write_text(json.dumps(result.to_dict(), indent=2))

    if not score.meets_baseline(baseline):
        raise SmokeBaselineError(
            f"Smoke suite below baseline: {score.rate:.0%} < {baseline:.0%} "
            f"({passed}/{total} checks passed)"
        )

    return result
