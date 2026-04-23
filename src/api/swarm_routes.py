"""Swarm API routes."""

import logging

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

swarm_bp = Blueprint("swarm", __name__)


@swarm_bp.route("/api/swarm/test", methods=["POST"])
def api_swarm_test():
    try:
        from src.swarm.executor import run_swarm_test

        data = request.get_json(silent=True) or {}
        scenario = data.get("scenario", "")
        tester_filter = data.get("filter")
        max_workers = data.get("workers", 4)

        if not scenario:
            return jsonify({"error": "scenario is required"}), 400

        result = run_swarm_test(scenario, tester_filter=tester_filter, max_workers=max_workers)
        return jsonify(result)

    except ImportError:
        return jsonify({"error": "Swarm module not available"}), 503
    except Exception as e:
        logger.error("Swarm test error: %s", e)
        return jsonify({"error": "Failed to run swarm test"}), 500


@swarm_bp.route("/api/swarm/roster", methods=["GET"])
def api_swarm_roster():
    try:
        from src.swarm.core import generate_initial_roster

        testers = generate_initial_roster()
        return jsonify({
            "testers": [
                {
                    "id": t.id,
                    "name": t.name,
                    "archetype": t.archetype.value,
                    "technical_competence": t.technical_competence,
                    "target_component": t.target_component,
                }
                for t in testers
            ]
        })

    except ImportError:
        return jsonify({"error": "Swarm module not available"}), 503
    except Exception as e:
        logger.error("Swarm roster error: %s", e)
        return jsonify({"error": "Failed to retrieve swarm roster"}), 500


@swarm_bp.route("/api/swarm/persona", methods=["POST"])
def api_swarm_persona():
    try:
        from src.swarm.executor import load_persona_cases, run_persona_swarm

        data = request.get_json(silent=True) or {}
        output_path = data.get("output_path")

        cases = load_persona_cases()
        result = run_persona_swarm(cases=cases, output_path=output_path)
        return jsonify(result)

    except ImportError:
        return jsonify({"error": "Swarm module not available"}), 503
    except FileNotFoundError:
        return jsonify({"error": "Persona cases file not found"}), 404
    except Exception as e:
        logger.error("Swarm persona error: %s", e)
        return jsonify({"error": "Failed to run persona swarm"}), 500
