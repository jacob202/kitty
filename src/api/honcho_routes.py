"""Honcho psychological model routes."""

import logging

from flask import Blueprint, jsonify, request

from src.api.shared import honcho_rate_limiter
from src.space_kitty.honcho import Honcho

logger = logging.getLogger(__name__)

honcho_bp = Blueprint('honcho', __name__)


@honcho_bp.route("/api/honcho/state", methods=["GET"])
def api_honcho_state():
    """Current psychological model — mood, energy, patterns."""
    client_ip = request.remote_addr or "default"
    if not honcho_rate_limiter.is_allowed(client_ip):
        return jsonify({"ok": False, "error": "Rate limited"}), 429

    try:
        h = Honcho()
        return jsonify({
            "ok": True,
            "state": h.get_current_state(),
            "approach": h.get_approach_recommendation(),
        })
    except Exception as e:
        logger.error("Honcho state error: %s", e)
        return jsonify({"ok": False, "error": "Honcho state unavailable"}), 500

@honcho_bp.route("/api/honcho/observations", methods=["GET"])
def api_honcho_observations():
    """Recent psychological observations."""
    try:
        hours = int(request.args.get("hours", 24))
        limit = int(request.args.get("limit", 50))
        h = Honcho()
        return jsonify({
            "ok": True,
            "observations": h.get_recent_observations(hours=hours, limit=limit),
        })
    except Exception as e:
        logger.error("Honcho observations error: %s", e)
        return jsonify({"ok": False, "error": "Failed to retrieve observations"}), 500

@honcho_bp.route("/api/honcho/opener", methods=["GET"])
def api_honcho_opener():
    """Get a welcome opener."""
    try:
        h = Honcho()
        should_show, opener_text = h.get_opener()
        return jsonify({"ok": True, "opener": opener_text if should_show else None})
    except Exception as e:
        logger.error("Honcho opener error: %s", e)
        return jsonify({"ok": False, "error": "Failed to retrieve opener"}), 500

@honcho_bp.route("/api/jacob_proxy/decide", methods=["POST"])
def api_jacob_proxy_decide():
    """Ask the Jacob proxy what to do next."""
    try:
        from tests.swarms.jacob_proxy import JacobProxy
    except ImportError:
        return jsonify({"ok": False, "error": "Jacob proxy not available"}), 503

    try:
        data = request.get_json(force=True) or {}
        situation = data.get("situation", "").strip()
        options = data.get("options") or []
        if not situation:
            return jsonify({"ok": False, "error": "situation required"}), 400
        p = JacobProxy()
        decision = p.decide(situation, options or None)
        return jsonify({
            "ok": True,
            "action": decision.action,
            "rationale": decision.rationale,
            "blockers": decision.blockers,
            "next_step": decision.next_step,
        })
    except Exception as e:
        logger.error("Jacob proxy decide error: %s", e)
        return jsonify({"ok": False, "error": "Failed to process decision"}), 500

@honcho_bp.route("/api/jacob_proxy/unblock", methods=["POST"])
def api_jacob_proxy_unblock():
    """Agent is stuck. Get the workaround."""
    try:
        from tests.swarms.jacob_proxy import JacobProxy
    except ImportError:
        return jsonify({"ok": False, "error": "Jacob proxy not available"}), 503

    try:
        data = request.get_json(force=True) or {}
        task = data.get("task", "").strip()
        reason = data.get("reason", "").strip()
        if not task or not reason:
            return jsonify({"ok": False, "error": "task and reason required"}), 400
        p = JacobProxy()
        return jsonify({"ok": True, "workaround": p.unblock(task, reason)})
    except Exception as e:
        logger.error("Jacob proxy unblock error: %s", e)
        return jsonify({"ok": False, "error": "Failed to process unblock request"}), 500
