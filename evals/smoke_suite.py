"""Smoke eval suite — Flask test client only, no external dependencies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from flask import Flask

from src.core.eval_domain import EvalCheck, EvalResult, EvalRun, EvalScore

BASELINE = 0.95
_DEFAULT_ARTIFACT_DIR = Path(__file__).parent / "artifacts"

KNOWN_SUITES = {"smoke"}


class SmokeBaselineError(Exception):
    """Raised when the smoke suite score drops below the baseline threshold."""


def run_smoke_suite(
    app: Flask,
    *,
    artifact_dir: Optional[Path] = None,
    baseline: float = BASELINE,
) -> EvalResult:
    """Run all smoke checks against the app and write an append-only artifact.

    Raises SmokeBaselineError if the pass rate is below *baseline*.
    Pass baseline=0.0 in tests that just want to exercise the suite without
    risking an error.
    """
    artifact_dir = artifact_dir or _DEFAULT_ARTIFACT_DIR
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    run = EvalRun.start("smoke")
    client = app.test_client()
    checks: list[EvalCheck] = []

    # 1. /api/capabilities returns 200 with non-empty shape
    resp = client.get("/api/capabilities")
    ok = resp.status_code == 200
    try:
        data = resp.get_json() or {}
        has_shape = isinstance(data, dict) and len(data) > 0
    except Exception:
        has_shape = False
    checks.append(EvalCheck.record(
        "capabilities_200",
        ok and has_shape,
        "" if (ok and has_shape) else f"status={resp.status_code}",
    ))

    # 2. /api/transcribe returns 400 for missing file, not 500
    resp = client.post("/api/transcribe", data={})
    ok = resp.status_code == 400
    checks.append(EvalCheck.record(
        "transcribe_400_on_missing_file",
        ok,
        "" if ok else f"status={resp.status_code}",
    ))

    # 3. / loads and contains voice/mic element
    resp = client.get("/")
    body = resp.data.decode("utf-8", errors="replace") if resp.status_code == 200 else ""
    has_voice = "voice" in body.lower() or "mic" in body.lower()
    checks.append(EvalCheck.record(
        "index_has_voice_button",
        resp.status_code == 200 and has_voice,
        "" if has_voice else "voice/mic not found in index page",
    ))

    # 4. / does not reference the removed /voice_poll endpoint
    no_poll = "/voice_poll" not in body
    checks.append(EvalCheck.record(
        "index_no_voice_poll",
        no_poll,
        "" if no_poll else "/voice_poll reference found in index",
    ))

    # 5. /api/chat is reachable and does not return 500 or 503
    resp = client.post("/api/chat", json={"message": "hi"})
    ok = resp.status_code not in (500, 503)
    checks.append(EvalCheck.record(
        "chat_not_500",
        ok,
        "" if ok else f"status={resp.status_code}",
    ))

    passed = sum(1 for c in checks if c.passed)
    total = len(checks)
    score = EvalScore(passed=passed, total=total)
    result = EvalResult(run=run, checks=checks, scores={"smoke": score})

    # Write artifact — never overwrite (run_id is unique)
    artifact_path = artifact_dir / f"{run.run_id}_smoke.json"
    artifact_path.write_text(json.dumps(result.to_dict(), indent=2))

    if not score.meets_baseline(baseline):
        raise SmokeBaselineError(
            f"Smoke suite below baseline: {score.rate:.0%} < {baseline:.0%} "
            f"({passed}/{total} checks passed)"
        )

    return result
