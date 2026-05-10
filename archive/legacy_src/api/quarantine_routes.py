# src/api/quarantine_routes.py
from flask import Blueprint, jsonify, request
from src.memory.quarantine_repo import get_pending_items, update_item_status

quarantine_bp = Blueprint('quarantine', __name__, url_prefix='/api/quarantine')

@quarantine_bp.route('', methods=['GET'])
def list_quarantine():
    items = get_pending_items()
    return jsonify(items)

@quarantine_bp.route('/<int:item_id>', methods=['POST'])
def update_quarantine(item_id):
    data = request.get_json() or {}
    status = data.get("status")
    if status not in ['approved', 'rejected']:
        return jsonify({"error": "Invalid status"}), 400
    
    success = update_item_status(item_id, status)
    return jsonify({"success": success})
