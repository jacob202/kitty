"""AI Development Dashboard - API routes for the monitoring dashboard."""

import logging
from flask import Blueprint, jsonify, render_template, request
from src.services.ai_dev_monitor import get_monitor

logger = logging.getLogger(__name__)

ai_dev_bp = Blueprint("ai_dev", __name__, template_folder="../templates")


@ai_dev_bp.route("/ai-dev")
def ai_dev_dashboard():
    """Render the AI Development Dashboard page."""
    return render_template("ai_dashboard.html")


@ai_dev_bp.route("/api/ai-dev/items")
def ai_dev_items():
    """Return monitored AI development items."""
    tag = request.args.get("tag")
    limit = int(request.args.get("limit", 20))
    monitor = get_monitor()
    items = monitor.get_items(tag=tag, limit=limit)
    summary = monitor.get_summary()
    return jsonify({
        "items": [i.to_dict() for i in items],
        "summary": summary,
    })


@ai_dev_bp.route("/api/ai-dev/refresh", methods=["POST"])
def ai_dev_refresh():
    """Trigger a fresh fetch of AI developments."""
    monitor = get_monitor()
    try:
        items = monitor.fetch()
        return jsonify({"ok": True, "count": len(items), "items": [i.to_dict() for i in items[:5]]})
    except Exception as e:
        logger.error(f"AI Dev refresh failed: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
