"""SocketIO event handlers for Project Kitty."""

import json
import logging
from pathlib import Path

from flask_socketio import emit

logger = logging.getLogger("kitty.api.socket")

_active_nodes = {}
_node_history = []
_MAX_HISTORY = 100


def register_socket_handlers(socketio):
    """Register all SocketIO event handlers."""

    @socketio.on("connect")
    def handle_connect():
        emit("connected", {"message": "Connected to Agent Status Dashboard"})
        for node_name, data in _active_nodes.items():
            emit("node_status", data)
        for event in _node_history[-20:]:
            emit("node_status", event)

        recent_logs = []
        try:
            log_path = Path("data/logs/canonical_log.jsonl")
            if log_path.exists():
                with open(log_path) as f:
                    lines = f.readlines()
                    recent_logs = [json.loads(line) for line in lines[-10:] if line.strip()]
        except Exception as e:
            logger.error(f"Error reading canonical log: {e}")

        emit("sync_state", {"recent_logs": recent_logs, "active_nodes": _active_nodes})

        from src.api.emitters import emit_system_health
        emit_system_health()

    @socketio.on("disconnect")
    def handle_disconnect():
        pass

    @socketio.on("request_history")
    def handle_history_request():
        emit("node_history", _node_history[-50:])

    @socketio.on("command_palette_search")
    def handle_command_search(data):
        query = data.get("query", "").lower()
        suggestions = []

        if query:
            if "hardware" in query or "schematic" in query:
                suggestions = [
                    {"command": "/analyze schematic", "description": "Analyze hardware schematic"},
                    {"command": "/bench hardware", "description": "Switch to hardware mode"},
                    {"command": "/process-pdf", "description": "Process PDF schematic"},
                ]
            elif "investigate" in query or "research" in query:
                suggestions = [
                    {"command": "/deepsearch", "description": "Deep web research"},
                    {"command": "/investigate", "description": "Investigative analysis"},
                    {"command": "/scrape", "description": "Scrape webpage"},
                ]
            elif "self" in query or "improve" in query:
                suggestions = [
                    {"command": "/vibe", "description": "Check current vibe"},
                    {"command": "/stuck", "description": "ADHD rescue"},
                    {"command": "/brief", "description": "Morning brief"},
                ]
            else:
                suggestions = [
                    {"command": "/help", "description": "Show all commands"},
                    {"command": "/status", "description": "System status"},
                    {"command": "/clear", "description": "Clear history"},
                ]

        emit("command_suggestions", suggestions)


def emit_psychological_state(socketio):
    """Broadcast current psychological model from Honcho to all clients."""
    try:
        from src.space_kitty.honcho import Honcho
        from datetime import datetime

        honcho = Honcho()
        state = honcho.get_current_state()
        approach = honcho.get_approach_recommendation()

        socketio.emit("psych_state", {
            "state": state,
            "approach": approach,
            "timestamp": datetime.now().isoformat()
        }, namespace="/")
    except Exception as e:
        logger.error(f"Error emitting psychological state: {e}")


def record_node_event(event_data):
    """Utility to record a LangGraph node event and broadcast it."""
    global _node_history
    _node_history.append(event_data)
    if len(_node_history) > _MAX_HISTORY:
        _node_history.pop(0)

    node_name = event_data.get("node")
    if node_name:
        if event_data.get("status") == "active":
            _active_nodes[node_name] = event_data
        else:
            _active_nodes.pop(node_name, None)

    emit("node_status", event_data, broadcast=True, namespace="/")
