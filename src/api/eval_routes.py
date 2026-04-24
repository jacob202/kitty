"""Eval trigger routes — POST /api/eval/run."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from evals.smoke_suite import BASELINE, KNOWN_SUITES, SmokeBaselineError, run_smoke_suite

eval_bp = Blueprint("eval", __name__)


@eval_bp.route("/api/eval/run", methods=["POST"])
def run_eval():
    """Trigger an eval suite and return structured results.

    Request body: {"suite": "smoke"}

    Responses:
        200  — suite passed baseline
        400  — unknown or missing suite
        422  — suite ran but failed baseline
        500  — unexpected execution error
    """
    body = request.get_json(silent=True) or {}
    suite = (body.get("suite") or "").strip()

    if not suite or suite not in KNOWN_SUITES:
        return jsonify({"ok": False, "error": f"Unknown suite: {suite!r}. Known: {sorted(KNOWN_SUITES)}"}), 400

    baseline = float(current_app.config.get("EVAL_BASELINE", BASELINE))

    try:
        result = run_smoke_suite(current_app._get_current_object(), baseline=baseline)
    except SmokeBaselineError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 422
    except Exception:
        current_app.logger.exception("Unexpected error in eval runner")
        return jsonify({"ok": False, "error": "Eval runner failed unexpectedly"}), 500

    smoke_score = result.scores.get("smoke")
    return jsonify({
        "ok": True,
        "run_id": result.run.run_id,
        "score": {
            "passed": smoke_score.passed,
            "total": smoke_score.total,
            "rate": smoke_score.rate,
        },
    })
