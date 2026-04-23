"""Reasoning trace API routes."""

import logging

from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

reasoning_bp = Blueprint("reasoning", __name__)


@reasoning_bp.route("/api/reasoning/traces", methods=["GET"])
def api_get_reasoning_traces():
    try:
        limit = int(request.args.get("limit", 10))
        sup = getattr(current_app, "supervisor", None)
        if not sup:
            return jsonify({"error": "Supervisor unavailable"}), 503
        traces = sup.orchestrator.reasoning.get_recent_traces(limit=limit)
        return jsonify({"traces": traces})
    except Exception as e:
        logger.error("Reasoning traces API error: %s", e)
        return jsonify({"error": "Failed to retrieve reasoning traces"}), 500


@reasoning_bp.route("/api/reasoning/traces/<trace_id>", methods=["GET"])
def api_get_reasoning_trace(trace_id):
    try:
        sup = getattr(current_app, "supervisor", None)
        if not sup:
            return jsonify({"error": "Supervisor unavailable"}), 503
        trace = sup.orchestrator.reasoning.get_trace(trace_id)
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
        sup = getattr(current_app, "supervisor", None)
        if not sup:
            return jsonify({"error": "Supervisor unavailable"}), 503
        sup.orchestrator.reasoning.clear_traces(older_than_hours=hours)
        return jsonify({"success": True})
    except Exception as e:
        logger.error("Reasoning clear API error: %s", e)
        return jsonify({"error": "Failed to clear traces"}), 500
