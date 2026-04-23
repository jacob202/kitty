"""Settings profile CRUD routes."""

import logging

from flask import Blueprint, jsonify, render_template, request

from src.config.settings_manager import (
    MiddlewareSettings,
    ModelConfig,
    ProfileSettings,
    ToolAvailability,
    settings_manager,
)

logger = logging.getLogger(__name__)

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/api/settings/profiles", methods=["POST"])
def api_create_profile():
    try:
        data = request.json
        if not data or "name" not in data:
            return jsonify({"error": "Profile name required"}), 400

        base_profile = data.get("base_profile")
        if base_profile:
            new_profile = settings_manager.create_profile(data["name"], base_profile)
        else:
            settings_data = data.get("settings", {})
            profile = ProfileSettings(
                name=data["name"],
                description=settings_data.get("description", "Custom profile"),
                system_prompt=settings_data.get(
                    "system_prompt", "You are Kitty, an AI assistant."
                ),
                personality=settings_data.get("personality", "helpful"),
                thinking_style=settings_data.get("thinking_style", "step-by-step"),
                response_format=settings_data.get("response_format", "verbose"),
                ui_theme=settings_data.get("ui_theme", "hardware"),
                animation_speed=settings_data.get("animation_speed", "normal"),
                compact_mode=settings_data.get("compact_mode", False),
                features=settings_data.get("features", {}),
            )

            if "model" in settings_data:
                profile.model = ModelConfig(**settings_data["model"])
            if "tools" in settings_data:
                profile.tools = ToolAvailability(**settings_data["tools"])
            if "middleware" in settings_data:
                profile.middleware = MiddlewareSettings(**settings_data["middleware"])

            settings_manager.save_profile(data["name"], profile)
            new_profile = profile

        return jsonify(
            {
                "status": "success",
                "profile": {
                    "name": new_profile.name,
                    "description": new_profile.description,
                },
            }
        )
    except Exception:
        return jsonify({"error": "Failed to create profile"}), 500


@settings_bp.route("/api/settings/profiles/<profile_name>", methods=["PUT"])
def api_update_profile(profile_name):
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        profile = ProfileSettings(
            name=profile_name,
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            system_prompt=data.get("system_prompt", ""),
            personality=data.get("personality", "helpful"),
            thinking_style=data.get("thinking_style", "step-by-step"),
            response_format=data.get("response_format", "verbose"),
            ui_theme=data.get("ui_theme", "hardware"),
            animation_speed=data.get("animation_speed", "normal"),
            compact_mode=data.get("compact_mode", False),
            features=data.get("features", {}),
        )

        if "model" in data:
            profile.model = ModelConfig(**data["model"])
        if "tools" in data:
            profile.tools = ToolAvailability(**data["tools"])
        if "middleware" in data:
            profile.middleware = MiddlewareSettings(**data["middleware"])

        if settings_manager.save_profile(profile_name, profile):
            return jsonify(
                {"status": "success", "message": f"Updated profile: {profile_name}"}
            )
        else:
            return jsonify({"error": "Failed to save profile"}), 500
    except Exception:
        logger.error("Profile update error")
        return jsonify({"error": "Failed to update profile"}), 500


@settings_bp.route("/api/settings/profiles/<profile_name>", methods=["DELETE"])
def api_delete_profile(profile_name):
    try:
        if settings_manager.delete_profile(profile_name):
            return jsonify(
                {"status": "success", "message": f"Deleted profile: {profile_name}"}
            )
        else:
            return jsonify({"error": "Failed to delete profile"}), 400
    except Exception:
        logger.error("Profile delete error")
        return jsonify({"error": "Failed to delete profile"}), 500


@settings_bp.route("/settings")
def settings_page():
    return render_template("settings.html")
