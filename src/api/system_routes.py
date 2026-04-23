"""System and configuration routes."""

import json
import logging
import threading
import time
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

system_bp = Blueprint('system', __name__)

_HEALTH_CACHE = {"data": None, "timestamp": 0, "lock": threading.Lock()}
_HEALTH_CACHE_TTL = 30  # seconds


def _get_cached_health():
    """Get cached health check result, refreshing if expired."""
    now = time.time()
    with _HEALTH_CACHE["lock"]:
        if now - _HEALTH_CACHE["timestamp"] < _HEALTH_CACHE_TTL and _HEALTH_CACHE["data"]:
            return _HEALTH_CACHE["data"]

        from src.utils.health_monitor import HealthChecker
        checker = HealthChecker()
        status = checker.run_all_checks()
        result = {
            "status": status.overall_status,
            "timestamp": status.timestamp,
            "version": getattr(status, "version", "unknown"),
            "summary": getattr(status, "summary", ""),
        }
        _HEALTH_CACHE["data"] = result
        _HEALTH_CACHE["timestamp"] = now
        return result

@system_bp.route("/api/eval/scorecard", methods=["GET"])
def get_scorecard():
    """Get the latest golden evaluation scorecard."""
    report_path = Path("data/test_results/golden_eval_report.json")
    if not report_path.exists():
        return jsonify({"error": "No scorecard available"}), 404

    try:
        with open(report_path) as f:
            return jsonify(json.load(f))
    except Exception as e:
        logger.error("Scorecard error: %s", e)
        return jsonify({"error": "Scorecard unavailable"}), 500

@system_bp.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint."""
    try:
        result = _get_cached_health()
        if result["status"] == "critical":
            return jsonify({"status": "unhealthy", "timestamp": result["timestamp"]}), 503
        elif result["status"] == "degraded":
            return jsonify({"status": "degraded", "timestamp": result["timestamp"]}), 200
        else:
            return jsonify({"status": "healthy", "timestamp": result["timestamp"]}), 200
    except Exception as e:
        logger.error("Health check error: %s", e)
        return jsonify({"status": "error", "error": "Health check failed"}), 503

@system_bp.route("/api/health", methods=["GET"])
def api_health():
    """Backward compatible health endpoint."""
    try:
        return jsonify(_get_cached_health())
    except Exception as e:
        logger.error("API health error: %s", e)
        return jsonify({"status": "error", "error": "Health check failed"}), 500

@system_bp.route("/api/settings", methods=["GET"])
def get_settings():
    """Get current application settings."""
    sup = getattr(current_app, 'supervisor', None)
    if not sup:
        return jsonify({"error": "Supervisor not initialized"}), 500

    # Map backend config to frontend schema
    settings = {
        "features": {
            "auto_pagination": {
                "enabled": sup.config.get("auto_pagination", True),
                "description": "Automatically paginate long responses",
            },
            "chat_history_profiling": {
                "enabled": sup.config.get("chat_history_profiling", False),
                "description": "Learn from conversation patterns",
            },
            "unhinged_mode": {
                "enabled": sup.config.get("unhinged_mode", False),
                "description": "Allow chaotic personality shifts",
            },
            "voice_input": {
                "enabled": sup.config.get("voice_input", True),
                "description": "SuperWhisper voice integration",
            },
            "screen_watcher": {
                "enabled": sup.config.get("screen_watcher", False),
                "description": "Continuous screen monitoring",
            },
        },
        "models": {
            "primary": sup.config.get("cheap_model", "deepseek/deepseek-chat"),
            "fallback": sup.config.get("flash_model", "deepseek/deepseek-chat"),
            "vision": sup.config.get("hardware_model", "google/gemini-2.0-flash-001"),
        },
    }
    return jsonify(settings)

@system_bp.route("/api/settings/update", methods=["POST"])
def update_settings():
    """Update application settings."""
    sup = getattr(current_app, 'supervisor', None)
    if not sup:
        return jsonify({"error": "Supervisor not initialized"}), 500

    data = request.get_json() or {}

    _ALLOWED_SETTINGS_KEYS = {
        "cheap_model",
        "flash_model",
        "hardware_model",
        "primary",
        "fallback",
        "vision",
    }

    # Update internal config
    for key, value in data.items():
        if key not in _ALLOWED_SETTINGS_KEYS:
            continue
        config_key = key
        if key == "primary":
            config_key = "cheap_model"
        elif key == "fallback":
            config_key = "flash_model"
        elif key == "vision":
            config_key = "hardware_model"

        sup.config[config_key] = value

    # Persist to disk
    if sup.save_config():
        return jsonify({"status": "success"})
    else:
        return jsonify({"error": "Failed to save configuration"}), 500

@system_bp.route("/api/diagnostics", methods=["GET"])
def api_diagnostics():
    """Run full diagnostic suite."""
    try:
        from dataclasses import asdict

        from src.utils.health_monitor import HealthChecker
        from src.utils.resilience import CircuitBreaker

        checker = HealthChecker()
        status = checker.run_all_checks()

        circuit_breakers = {}
        for name, cb in CircuitBreaker._instances.items():
            circuit_breakers[name] = cb.get_state()

        return jsonify({
            "status": status.overall_status,
            "timestamp": status.timestamp,
            "version": status.version,
            "summary": status.summary,
            "checks": [asdict(check) for check in status.checks],
            "circuit_breakers": circuit_breakers,
        })
    except Exception as e:
        logger.error("Diagnostics error: %s", e)
        return jsonify({"status": "error", "error": "Diagnostics unavailable"}), 500

@system_bp.route("/api/resilience/status", methods=["GET"])
def api_resilience_status():
    """Get resilience system status."""
    try:
        from src.utils.resilience import CircuitBreaker
        circuit_breakers = {}
        for name, cb in CircuitBreaker._instances.items():
            circuit_breakers[name] = cb.get_state()

        return jsonify({
            "circuit_breakers": circuit_breakers,
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.error("Resilience status error: %s", e)
        return jsonify({"error": "Resilience status unavailable"}), 500

@system_bp.route("/api/settings/profiles", methods=["GET"])
def api_list_profiles():
    """List all available profiles."""
    try:
        from src.config.settings_manager import settings_manager
        profiles = settings_manager.list_profiles()
        return jsonify(profiles)
    except Exception as e:
        logger.error("List profiles error: %s", e)
        return jsonify({"error": "Profiles unavailable"}), 500

@system_bp.route("/api/settings/profiles/active", methods=["GET"])
def api_get_active_profile():
    """Get the currently active profile."""
    try:
        from src.config.settings_manager import settings_manager
        profile = settings_manager.get_active_profile()
        return jsonify({
            "name": profile.name,
            "settings": profile.__dict__
        })
    except Exception as e:
        logger.error("Active profile error: %s", e)
        return jsonify({"error": "Active profile unavailable"}), 500
