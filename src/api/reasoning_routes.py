"""Reasoning trace API routes."""

import logging
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

reasoning_bp = Blueprint("reasoning", __name__)


def _get_reasoning_layer():
    """Get the ReasoningLayer from the app if wired, else return None."""
    # Primary web path: web.py sets app.orchestrator = CoreOrchestrator(...)
    orch = getattr(current_app, "orchestrator", None)
    if orch is not None:
        layer = getattr(orch, "reasoning", None)
        if layer is not None:
            return layer
    # Direct attribute (future: if wired explicitly)
    layer = getattr(current_app, "reasoning_layer", None)
    if layer is not None:
        return layer
    # CLI path: supervisor wraps an orchestrator
    sup = getattr(current_app, "supervisor", None)
    if sup:
        cli_orch = getattr(sup, "orchestrator", None)
        if cli_orch:
            layer = getattr(cli_orch, "reasoning", None)
            if layer is not None:
                return layer
    return None


def _load_last_trace_from_disk() -> dict | None:
    """Read the most recent trace file from data/reasoning_traces/."""
    traces_dir = Path("data/reasoning_traces")
    if not traces_dir.exists():
        return None
    import json
    files = sorted(traces_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files[:1]:
        try:
            return json.loads(f.read_text())
        except Exception:
            continue
    return None


@reasoning_bp.route("/api/reasoning/last", methods=["GET"])
def api_get_last_reasoning_trace():
    """Return the most recent reasoning trace in a UI-safe shape."""
    try:
        layer = _get_reasoning_layer()
        if layer is not None:
            traces = layer.get_recent_traces(limit=1)
            if traces:
                raw = traces[0]
                return jsonify({"trace": _normalize_trace(raw)})

        # Fallback: load from disk
        raw = _load_last_trace_from_disk()
        if raw:
            return jsonify({"trace": _normalize_trace(raw)})

        return jsonify({"trace": None, "note": "No reasoning trace recorded yet."})
    except Exception as e:
        logger.error("Reasoning last trace error: %s", e)
        return jsonify({"trace": None, "note": f"Error retrieving trace: {e}"})


def _normalize_trace(raw: dict) -> dict:
    """Translate a raw trace dict into a UI-safe shape."""
    steps = raw.get("steps", [])
    normalized_steps = []
    for step in steps:
        normalized_steps.append({
            "type": step.get("step_type", step.get("type", "unknown")),
            "content": step.get("content", ""),
            "confidence": step.get("confidence", 0.5),
        })
    return {
        "id": raw.get("id", ""),
        "query": raw.get("query", ""),
        "steps": normalized_steps,
        "conclusion": raw.get("conclusion", ""),
    }


@reasoning_bp.route("/api/reasoning/traces", methods=["GET"])
def api_get_reasoning_traces():
    try:
        limit = int(request.args.get("limit", 10))
        layer = _get_reasoning_layer()
        if layer is None:
            return jsonify({"traces": [], "note": "Reasoning layer not wired in this mode."})
        traces = layer.get_recent_traces(limit=limit)
        return jsonify({"traces": traces})
    except Exception as e:
        logger.error("Reasoning traces API error: %s", e)
        return jsonify({"error": "Failed to retrieve reasoning traces"}), 500


@reasoning_bp.route("/api/reasoning/traces/<trace_id>", methods=["GET"])
def api_get_reasoning_trace(trace_id):
    try:
        layer = _get_reasoning_layer()
        if layer is None:
            return jsonify({"error": "Reasoning layer not available"}), 503
        trace = layer.get_trace(trace_id)
        if trace:
            return jsonify(trace)
        return jsonify({"error": "Trace not found"}), 404
    except Exception as e:
        logger.error("Reasoning trace API error: %s", e)
        return jsonify({"error": "Failed to retrieve trace"}), 500


@reasoning_bp.route("/api/reasoning/traces", methods=["DELETE"])
def api_clear_reasoning_traces():
    try:
        hours = float(request.args.get("older_than_hours", 24))
        layer = _get_reasoning_layer()
        if layer is None:
            return jsonify({"error": "Reasoning layer not available"}), 503
        layer.clear_traces(older_than_hours=hours)
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Reasoning clear API error: %s", e)
        return jsonify({"error": "Failed to clear traces"}), 500
