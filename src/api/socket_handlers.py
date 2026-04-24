"""SocketIO event handlers for Project Kitty."""

import json
import logging
import threading
from pathlib import Path

from flask import current_app, request
from flask_socketio import emit

from src.api.emitters import get_active_nodes, get_node_history, _MAX_HISTORY
from src.core.capabilities import command_palette_suggestions, record_invocation

logger = logging.getLogger("kitty.api.socket")


def register_socket_handlers(socketio):
    """Register all SocketIO event handlers."""

    @socketio.on("connect")
    def handle_connect():
        emit("connected", {"message": "Connected to Agent Status Dashboard"})
        for node_name, data in get_active_nodes().items():
            emit("node_status", data)
        for event in get_node_history()[-20:]:
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

        emit("sync_state", {"recent_logs": recent_logs, "active_nodes": get_active_nodes()})

        from src.api.emitters import emit_system_health
        emit_system_health()

    @socketio.on("disconnect")
    def handle_disconnect():
        pass

    @socketio.on("request_history")
    def handle_history_request():
        emit("node_history", get_node_history()[-50:])

    @socketio.on("command_palette_search")
    def handle_command_search(data):
        query = data.get("query", "").lower()
        suggestions = command_palette_suggestions(query)
        for suggestion in suggestions:
            record_invocation(suggestion["command"], outcome="suggested")
        emit("command_suggestions", suggestions)

    @socketio.on("send_message")
    def handle_send_message(data):
        message = data.get("text", "").strip()
        mode = data.get("mode", "fast")
        model_target = data.get("modelTarget", "free")
        reasoning = data.get("reasoning", False)
        sid = request.sid
        if not message:
            return

        from src.api.dispatcher import dispatch
        sup = current_app.supervisor
        orch = current_app.orchestrator
        fallback = getattr(current_app, "web_llm", None)
        busy = getattr(current_app, "_busy_lock", None)

        def run():
            try:
                if message.startswith("/"):
                    if busy:
                        with busy:
                            response = dispatch(
                                message,
                                sup=sup,
                                orch=orch,
                                fallback_chat=fallback.chat if fallback else None,
                                fallback_stream=True,
                            )
                    else:
                        response = dispatch(
                            message,
                            sup=sup,
                            orch=orch,
                            fallback_chat=fallback.chat if fallback else None,
                            fallback_stream=True,
                        )
                    if response and getattr(response, "content", None):
                        socketio.emit("token", {"text": response.content}, to=sid, namespace="/")
                    return

                from src.api.web_orchestrator import stream_response

                if busy:
                    with busy:
                        response = stream_response(
                            message,
                            sid,
                            mode=mode,
                            reasoning=reasoning,
                            model_target=model_target,
                        )
                else:
                    response = stream_response(
                        message,
                        sid,
                        mode=mode,
                        reasoning=reasoning,
                        model_target=model_target,
                    )
                if response:
                    socketio.emit("token", {"text": response}, to=sid, namespace="/")
            except Exception as e:
                socketio.emit("error", {"text": f"Error: {e}"}, to=sid, namespace="/")
            finally:
                socketio.emit("done", {"specialist": ""}, to=sid, namespace="/")

        app = current_app._get_current_object()
        threading.Thread(target=_run_with_app_context, args=(app, run), daemon=True).start()


def _run_with_app_context(app, func):
    with app.app_context():
        func()


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
    from src.api.emitters import _node_history, _active_nodes, _MAX_HISTORY
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
