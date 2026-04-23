"""SocketIO emitter functions and health monitoring."""

import logging
import time
from dataclasses import asdict

logger = logging.getLogger(__name__)

_node_history: list = []
_active_nodes: dict = {}
_MAX_HISTORY = 100

_socketio = None


def init_socketio(sio):
    global _socketio
    _socketio = sio


def emit_node_status(node_name, status, data=None):
    event_data = {
        "node": node_name,
        "status": status,
        "timestamp": time.time(),
        "data": data or {},
    }
    _node_history.append(event_data)
    if len(_node_history) > _MAX_HISTORY:
        _node_history.pop(0)

    if _socketio:
        _socketio.emit("node_status", event_data)

    if status in ["started", "processing"]:
        _active_nodes[node_name] = event_data
    elif status in ["completed", "error"]:
        _active_nodes.pop(node_name, None)


def emit_thinking_bubble(thought, confidence=1.0):
    if _socketio:
        _socketio.emit(
            "thinking_bubble",
            {"thought": thought, "confidence": confidence, "timestamp": time.time()},
        )


def emit_theme_change(theme):
    if _socketio:
        _socketio.emit("theme_change", {"theme": theme, "timestamp": time.time()})


_health_cache = {"data": None, "timestamp": 0}
_HEALTH_CACHE_TTL = 30
_health_checker = None


def _get_health_checker():
    global _health_checker
    if _health_checker is None:
        from src.utils.health_monitor import HealthChecker
        _health_checker = HealthChecker()
    return _health_checker


def emit_system_health(health_data=None):
    global _health_cache
    now = time.time()

    if health_data is None:
        if now - _health_cache["timestamp"] < _HEALTH_CACHE_TTL:
            health_data = _health_cache["data"]
        else:
            try:
                checker = _get_health_checker()
                status = checker.run_all_checks()
                health_data = {
                    "status": status.overall_status,
                    "timestamp": status.timestamp,
                    "ollama": asdict(status.checks[0]) if len(status.checks) > 0 else {"status": "unknown"},
                    "chromadb": asdict(status.checks[1]) if len(status.checks) > 1 else {"status": "unknown"},
                    "summary": status.summary,
                }
                _health_cache = {"data": health_data, "timestamp": now}
            except Exception:
                health_data = {"status": "error", "timestamp": time.time()}

    if _socketio:
        _socketio.emit("system_health", health_data)


def health_background_thread():
    while True:
        emit_system_health()
        if _socketio:
            _socketio.sleep(30)
        else:
            time.sleep(30)


def get_node_history():
    return _node_history


def get_active_nodes():
    return _active_nodes
