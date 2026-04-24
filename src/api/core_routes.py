"""Core chat and assistant logic."""

import logging

from flask import Blueprint, current_app, jsonify, request

from src.api.shared import core_rate_limiter

logger = logging.getLogger(__name__)

core_bp = Blueprint('core', __name__)


def _dispatch_chat(message: str, domain: str):
    from src.api.dispatcher import dispatch

    fallback = getattr(current_app, "web_llm", None)
    fallback_chat = fallback.chat if fallback else None
    return dispatch(
        message,
        domain=domain,
        sup=getattr(current_app, "supervisor", None),
        orch=getattr(current_app, "orchestrator", None),
        fallback_chat=fallback_chat,
        fallback_stream=False,
    )

@core_bp.route("/api/chat", methods=["POST"])
def api_chat():
    """Synchronous chat endpoint with rate limiting."""
    client_ip = request.remote_addr or "default"

    if not core_rate_limiter.is_allowed(client_ip):
        return jsonify({"ok": False, "error": "Rate limit exceeded. Try again shortly."}), 429

    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    domain = (data.get("domain") or "").strip()

    if not message:
        return jsonify({"ok": False, "error": "No message provided"}), 400

    if len(message) > 10000:
        return jsonify({"ok": False, "error": "Message too long (max 10000 chars)"}), 400

    response = _dispatch_chat(message, domain)
    if response:
        diag = response.diagnostics or {}
        return jsonify({
            "ok": True,
            "response": response.content,
            "confidence": response.confidence,
            "sources": response.sources,
            "safety_warnings": response.safety_warnings,
            "suggested_followups": response.suggested_followups,
            "fallback_used": response.confidence < 0.5,
            "sentiment": diag.get("sentiment", 0.0),
            "specialist": diag.get("specialist"),
            "conversation_id": diag.get("conversation_id"),
        })

    return jsonify({"ok": False, "error": "No web chat backend available"}), 503

@core_bp.route("/api/route", methods=["POST"])
def api_route_preview():
    """Route preview without execution."""
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": "No message provided"}), 400

    orch = getattr(current_app, 'orchestrator', None)
    if orch:
        routing = orch.domain_router.route(message)
        return jsonify({
            "ok": True,
            "specialist": routing.specialist,
            "domain": routing.domain.value,
            "confidence": routing.confidence,
            "reasoning": routing.reasoning,
            "model_route": "local" if routing.domain.value == "general" else "specialist",
        })

    return jsonify({"ok": False, "error": "Orchestrator unavailable"}), 503

@core_bp.route("/api/chatbox/start", methods=["POST"])
def chatbox_start():
    """Start a multi-LLM chatbox session."""
    sup = getattr(current_app, 'supervisor', None)
    if not sup:
        return jsonify({"success": False, "error": "Supervisor unavailable"}), 503
    data = request.json or {}
    models = data.get("models", ["claude", "flash", "local"])
    topic = data.get("topic", "Multi-LLM brainstorming")
    autonomous = data.get("autonomous", False)
    try:
        result = sup.start_chatbox(models=models, topic=topic, autonomous=autonomous)
        return jsonify({"success": True, "message": result})
    except Exception as e:
        logger.error("Chatbox start error: %s", e)
        return jsonify({"success": False, "error": "Failed to start chatbox"}), 500

@core_bp.route("/api/chatbox/stop", methods=["POST"])
def chatbox_stop():
    """Stop the current chatbox session."""
    sup = getattr(current_app, 'supervisor', None)
    if not sup:
        return jsonify({"success": False, "error": "Supervisor unavailable"}), 503
    try:
        result = sup.chatbox_stop()
        return jsonify({"success": True, "message": result})
    except Exception as e:
        logger.error("Chatbox stop error: %s", e)
        return jsonify({"success": False, "error": "Failed to stop chatbox"}), 500
