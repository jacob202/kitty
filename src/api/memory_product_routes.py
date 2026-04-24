"""User-facing memory controls — what Kitty remembers, why, and how to manage it.

Separate from memory_routes.py (journal/library plumbing) — this is the
product-facing surface built on CorrectionMemory and context snapshots.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)
memory_product_bp = Blueprint("memory_product", __name__)

_VALID_SCOPES = frozenset({"project", "durable"})
_VALID_KINDS = frozenset({"correction", "snapshot"})


def _get_correction_memory():
    from src.memory.correction_memory import CorrectionMemory
    return CorrectionMemory()


@memory_product_bp.route("/api/memory", methods=["GET"])
def list_memory():
    """Return everything Kitty currently remembers, with scope and reason."""
    try:
        cm = _get_correction_memory()

        # Corrections from SQLite — treated as durable
        with cm._lock:
            import sqlite3
            with sqlite3.connect(cm.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT id, correction_text, category FROM corrections ORDER BY timestamp DESC LIMIT 50"
                ).fetchall()

        corrections = [
            {
                "id": row["id"],
                "text": row["correction_text"],
                "category": row["category"],
                "scope": "durable",
                "why": "Saved correction from prior interaction",
            }
            for row in rows
        ]

        # Snapshots from ChromaDB — treated as session scope
        raw_snapshots = cm.get_recent_snapshots(days=30, limit=10)
        snapshots = [
            {
                "timestamp": snap.get("timestamp"),
                "scope": "session",
                "why": "Recent context snapshot",
                "topics": snap.get("topics", []),
                "sentiment": snap.get("sentiment_label", "neutral"),
            }
            for snap in raw_snapshots
        ]

        return jsonify({
            "ok": True,
            "corrections": corrections,
            "snapshots": snapshots,
            "summary": {
                "correction_count": len(corrections),
                "snapshot_count": len(snapshots),
            },
        })

    except Exception as exc:
        logger.exception("Memory list error")
        return jsonify({"ok": False, "error": str(exc)}), 500


@memory_product_bp.route("/api/memory/forget", methods=["POST"])
def forget_memory():
    """Remove a memory item. Corrections are deleted for real; snapshots return 501."""
    body = request.get_json(silent=True) or {}
    kind = body.get("kind", "").strip()
    item_id = body.get("id")

    if kind not in _VALID_KINDS:
        return jsonify({"ok": False, "error": f"kind must be one of {sorted(_VALID_KINDS)}"}), 400
    if item_id is None:
        return jsonify({"ok": False, "error": "id is required"}), 400

    if kind == "snapshot":
        return jsonify({
            "ok": False,
            "error": "Snapshot deletion not yet supported — individual snapshot removal is not safe with the current ChromaDB setup.",
            "code": "not_implemented",
        }), 501

    # kind == "correction"
    try:
        cm = _get_correction_memory()
        with cm._lock:
            import sqlite3
            with sqlite3.connect(cm.db_path) as conn:
                cursor = conn.execute("DELETE FROM corrections WHERE id = ?", (int(item_id),))
                conn.commit()
                deleted = cursor.rowcount

        if deleted:
            return jsonify({"ok": True, "deleted": int(item_id)})
        return jsonify({"ok": False, "error": "Correction not found", "id": item_id}), 404

    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "id must be an integer for corrections"}), 400
    except Exception as exc:
        logger.exception("Memory forget error")
        return jsonify({"ok": False, "error": str(exc)}), 500


@memory_product_bp.route("/api/memory/pin", methods=["POST"])
def pin_memory():
    """Promote a memory item to a higher scope. Returns 501 — scope field not in DB yet."""
    body = request.get_json(silent=True) or {}
    kind = body.get("kind", "").strip()
    scope = body.get("scope", "").strip()

    if kind not in _VALID_KINDS:
        return jsonify({"ok": False, "error": f"kind must be one of {sorted(_VALID_KINDS)}"}), 400
    if scope not in _VALID_SCOPES:
        return jsonify({"ok": False, "error": f"scope must be one of {sorted(_VALID_SCOPES)}"}), 400

    return jsonify({
        "ok": False,
        "error": "Scope promotion not yet supported — corrections DB does not have a scope column yet.",
        "code": "not_implemented",
    }), 501
