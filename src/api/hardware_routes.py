"""Hardware, BOM, and schematic routes."""

import logging
import tempfile

from flask import Blueprint, current_app, jsonify, request

logger = logging.getLogger(__name__)

hardware_bp = Blueprint('hardware', __name__)

@hardware_bp.route("/api/schematic/analyze", methods=["POST"])
def schematic_analyze():
    """Trigger schematic analysis on an uploaded image."""
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        file.save(tmp.name)
        img_path = tmp.name

    try:
        sup = getattr(current_app, 'supervisor', None)
        if not sup:
            return jsonify({"error": "Supervisor unavailable"}), 503

        result = sup.schematic_analysis(img_path)
        return jsonify(result)
    except Exception as e:
        logger.error("Schematic analysis error: %s", e)
        return jsonify({"error": "Analysis failed"}), 500
    finally:
        import os
        try:
            os.unlink(img_path)
        except OSError:
            pass

@hardware_bp.route("/api/schematic/<project_id>/components")
def get_schematic_components(project_id):
    """Get all components for a schematic project."""
    try:
        from src.utils.duckdb_client import db
        from src.utils.schematic_analyzer import SchematicAnalyzer

        analyzer = SchematicAnalyzer(db_client=db)
        components = analyzer.get_schematic_components(project_id)
        return jsonify({"components": components})
    except Exception as e:
        logger.error("Schematic components error: %s", e)
        return jsonify({"error": "Failed to retrieve components"}), 500

@hardware_bp.route("/api/schematic/viewer", methods=["GET"])
def get_schematic_viewer():
    """
    Return interactive SVG viewer HTML for a schematic.
    """
    from src.utils.duckdb_client import db
    image_path = request.args.get("image_path", "")
    project_id = request.args.get("project_id", "default")

    if not image_path:
        return jsonify({"error": "image_path is required"}), 400

    # Get components for this project from database
    components = []
    try:
        from src.utils.schematic_analyzer import SchematicAnalyzer

        analyzer = SchematicAnalyzer(db_client=db)
        components = analyzer.get_schematic_components(project_id)
    except Exception as e:
        logger.warning("Schematic components load failed: %s", e)
    image_width = 800
    image_height = 600
    try:
        from pathlib import Path
        img_path = Path(image_path)
        if img_path.exists():
            with open(img_path, "rb") as f:
                header = f.read(32)
                if header.startswith(b"\x89PNG\r\n\x1a\n"):
                    import struct
                    f.seek(16)
                    image_width = struct.unpack(">I", f.read(4))[0]
                    image_height = struct.unpack(">I", f.read(4))[0]
    except Exception as e:
        logger.warning("Image dimension read failed: %s", e)
    overlay_svg = ""
    try:
        from src.utils.schematic_overlay import Component, SchematicOverlayGenerator

        generator = SchematicOverlayGenerator()
        components_for_overlay = [
            Component(
                designator=c.get("designator", ""),
                type=c.get("type", "unknown"),
                x=float(c.get("x", 0)),
                y=float(c.get("y", 0)),
            )
            for c in components
        ]
        overlay_svg = generator.generate_overlay(
            image_path, components_for_overlay, image_width, image_height
        )
    except Exception as e:
        logger.warning("SVG overlay generation failed: %s", e)

    return jsonify(
        {
            "image_path": image_path,
            "project_id": project_id,
            "components": components,
            "image_width": image_width,
            "image_height": image_height,
            "overlay_svg": overlay_svg,
        }
    )

@hardware_bp.route("/api/schematic/components/list", methods=["GET"])
def get_schematic_components_list():
    """Get all components for a project."""
    project_id = request.args.get("project_id", "default")
    try:
        from src.utils.duckdb_client import db
        from src.utils.schematic_analyzer import SchematicAnalyzer
        analyzer = SchematicAnalyzer(db_client=db)
        components = analyzer.get_schematic_components(project_id)
        return jsonify({"project_id": project_id, "components": components})
    except Exception as e:
        logger.error("Schematic components list error: %s", e)
        return jsonify({"error": "Failed to retrieve components"}), 500

@hardware_bp.route("/api/schematic/component/<designator>", methods=["GET"])
def get_schematic_component(designator):
    """Get details for a specific component."""
    project_id = request.args.get("project", "default")
    try:
        from src.utils.duckdb_client import db
        from src.utils.schematic_analyzer import SchematicAnalyzer
        analyzer = SchematicAnalyzer(db_client=db)
        component = analyzer.lookup_component(project_id, designator.upper())
        if not component:
            return jsonify({"error": "Component not found"}), 404
        result = {**component}
        result["datasheet"] = db.get_component_datasheet(project_id, designator.upper())
        return jsonify(result)
    except Exception as e:
        logger.error("Schematic component error: %s", e)
        return jsonify({"error": "Failed to retrieve component"}), 500

@hardware_bp.route("/api/schematic/equivalents/<part_number>", methods=["GET"])
def get_component_equivalents(part_number):
    """Get equivalent parts for a component."""
    limit = int(request.args.get("limit", 10))
    try:
        from src.utils.duckdb_client import db
        equivalents = db.find_equivalents_by_part_number(part_number, limit=limit)
        return jsonify({"part_number": part_number, "equivalents": equivalents})
    except Exception as e:
        logger.error("Component equivalents error: %s", e)
        return jsonify({"error": "Failed to retrieve equivalents"}), 500

@hardware_bp.route("/api/datasheet/fetch", methods=["POST"])
def datasheet_fetch():
    """Fetch datasheet for a part number."""
    try:
        from src.utils.datasheet_intelligence import DatasheetFetcher
        data = request.get_json() or {}
        part_number = data.get("part_number")
        if not part_number:
            return jsonify({"error": "part_number required"}), 400
        fetcher = DatasheetFetcher()
        result = fetcher.fetch(part_number)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        logger.error("Datasheet fetch error: %s", e)
        return jsonify({"error": "Failed to fetch datasheet"}), 500

@hardware_bp.route("/api/crossref/<part_number>")
def get_cross_references(part_number):
    """Get cross-references for a part."""
    try:
        from src.utils.datasheet_intelligence import CrossReferenceEngine
        engine = CrossReferenceEngine()
        results = engine.find_equivalents(part_number)
        return jsonify({"part_number": part_number, "equivalents": results})
    except Exception as e:
        logger.error("Cross-reference error: %s", e)
        return jsonify({"error": "Failed to retrieve cross-references"}), 500
