"""
Morning brief API handler.
"""
from flask import Blueprint, jsonify, current_app
from src.core.morning_brief import generate_brief, brief_to_text

brief_bp = Blueprint('brief', __name__)

@brief_bp.route('/api/brief', methods=['GET'])
def get_brief():
    """
    Route handler for GET /api/brief.
    Returns JSON-serializable dict.
    """
    b = generate_brief()
    return jsonify({
        "brief": brief_to_text(b),
        "data": b,
    })
