"""Memory and journal routes."""

import logging
from pathlib import Path

from flask import Blueprint, jsonify, request

from src.api.shared import get_pka_db, memory_rate_limiter

logger = logging.getLogger(__name__)

memory_bp = Blueprint('memory', __name__)


@memory_bp.route("/api/journal/entries", methods=["GET"])
def get_journal_entries():
    client_ip = request.remote_addr or "default"
    if not memory_rate_limiter.is_allowed(client_ip):
        return jsonify({"error": "Rate limited"}), 429

    pka_db = get_pka_db()
    if not pka_db:
        return jsonify([])
    return jsonify(pka_db.get_entries())

@memory_bp.route("/api/journal/search", methods=["GET"])
def search_journal():
    pka_db = get_pka_db()
    if not pka_db:
        return jsonify({"error": "PKA Database not available"}), 500

    query = request.args.get("query")
    if not query:
        return jsonify({"error": "No query provided"}), 400

    results = pka_db.hybrid_search(query)
    return jsonify(results)

@memory_bp.route("/api/journal/add", methods=["POST"])
def add_journal_entry():
    pka_db = get_pka_db()
    if not pka_db:
        return jsonify({"error": "PKA Database not available"}), 500

    data = request.json
    content = data.get("content")
    entry_type = data.get("type", "journal")
    mood = data.get("mood")
    energy = data.get("energy")

    row_id = pka_db.add_entry(content, entry_type=entry_type, mood=mood, energy=energy)
    if row_id:
        return jsonify({"status": "success", "id": row_id})
    return jsonify({"error": "Failed to save entry"}), 500

@memory_bp.route("/api/memory/library", methods=["GET"])
def get_library():
    """List all ingested documents in the knowledge base."""
    processed_path = Path("data/vector_store/chroma_db/processed_files.txt")
    if not processed_path.exists():
        return jsonify({"documents": [], "count": 0})

    try:
        with open(processed_path) as f:
            docs = [line.strip() for line in f.readlines() if line.strip()]

        # Sort alphabetically
        docs.sort()

        return jsonify({
            "documents": docs,
            "count": len(docs)
        })
    except Exception as e:
        from src.core.exceptions import handle_exception
        handle_exception(e, context="memory.get_library")
        logger.error("Memory library error: %s", e)
        return jsonify({"error": "Library unavailable"}), 500

@memory_bp.route("/api/memory/feedback", methods=["POST"])
def add_feedback():
    """Submit human feedback for a response to improve future behavior via Memory Weave."""
    try:
        from src.memory.memory_weave import get_weave
        data = request.get_json() or {}

        entity = data.get("entity")
        relation = data.get("relation", "response_quality")
        value = data.get("feedback")
        source = "user_ui_feedback"

        if not entity or not value:
            return jsonify({"error": "entity and feedback are required"}), 400

        weave = get_weave()

        is_correction = data.get("is_correction", False)
        if is_correction:
            edge_id = weave.correct(entity, relation, value, source=source)
        else:
            confidence = 0.95 if value == "correct" or value == "helpful" else 0.1
            edge_id = weave.fact(entity, relation, value, source=source, source_type="user_correction", confidence=confidence)

        return jsonify({"status": "success", "edge_id": edge_id})
    except Exception as e:
        from src.core.exceptions import handle_exception
        handle_exception(e, context="memory.add_feedback")
        logger.error("Memory feedback error: %s", e)
        return jsonify({"error": "Failed to process feedback"}), 500
