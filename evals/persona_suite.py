"""Persona eval suite — deterministic persona fixtures + daily summary hook."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Flask

from src.core.eval_domain import EvalRun

_PERSONA_DIR = Path(__file__).parent / "personas"
_BASIC_FIXTURE = _PERSONA_DIR / "basic.json"


def load_personas(fixture: Path = _BASIC_FIXTURE) -> list[dict[str, Any]]:
    """Load persona fixtures from a JSON file."""
    return json.loads(Path(fixture).read_text())


def run_persona_suite(
    app: Flask,
    *,
    fixture: Path = _BASIC_FIXTURE,
) -> list[dict[str, Any]]:
    """Run each persona prompt through /api/chat and return structured results.

    Results are NOT written to disk here — callers that want artifacts should
    call generate_daily_summary after collecting results.
    """
    personas = load_personas(fixture)
    run = EvalRun.start("persona")
    client = app.test_client()
    results: list[dict[str, Any]] = []

    for persona in personas:
        resp = client.post("/api/chat", json={"message": persona["prompt"]})
        passed = resp.status_code not in (500, 503)
        try:
            body = resp.get_json() or {}
            has_content = bool(body)
        except Exception:
            has_content = False

        results.append({
            "run_id": run.run_id,
            "persona_id": persona["id"],
            "prompt": persona["prompt"],
            "status_code": resp.status_code,
            "passed": passed and has_content,
            "reason": "" if (passed and has_content) else f"status={resp.status_code}",
        })

    return results


def generate_daily_summary(
    app: Flask,
    *,
    report_dir: Path | None = None,
) -> Path:
    """Generate a daily report and return the path to the output file.

    Uses DashboardGenerator as a reporting helper only.
    """
    from src.utils.performance_monitor import DashboardGenerator

    generator = DashboardGenerator(output_dir=str(report_dir) if report_dir else None)
    report_path_str = generator.generate_daily_report(days=1, format="json")
    return Path(report_path_str)
