"""BOM (Bill of Materials) API routes."""

import logging
import os
import tempfile
import time

from flask import Blueprint, Response, jsonify, request

logger = logging.getLogger(__name__)

bom_bp = Blueprint("bom", __name__)


@bom_bp.route("/api/bom/export", methods=["GET"])
def export_bom():
    try:
        project = request.args.get("project", "default")
        format_type = request.args.get("format", "csv")

        sup = getattr(request.app, "supervisor", None)
        if not sup:
            return jsonify({"error": "Supervisor unavailable"}), 503

        bom_data = sup.get_bom_data(project)

        if format_type.lower() == "csv":
            import csv
            import io

            if not bom_data:
                return jsonify({"error": "No BOM data available"}), 404

            output = io.StringIO()
            if bom_data:
                headers = bom_data[0].keys()
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writeheader()
                writer.writerows(bom_data)

            response = Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={
                    "Content-Disposition": f"attachment;filename=bom_{project}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
                },
            )
            return response
        else:
            return jsonify(bom_data)

    except Exception as e:
        logger.error("BOM export error: %s", e)
        return jsonify({"error": "Failed to export BOM"}), 500


@bom_bp.route("/api/bom/<project_id>/export", methods=["GET"])
def api_bom_export(project_id):
    try:
        from src.utils.bom_manager import BOMManager

        format_type = request.args.get("format", "csv").lower()
        include_pricing = request.args.get("pricing", "false").lower() == "true"
        supplier = request.args.get("supplier", "digikey").lower()

        bom_mgr = BOMManager()

        if format_type == "excel":
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                output_path = bom_mgr.export_to_excel(
                    project_id, tmp.name, include_pricing, supplier
                )

                with open(output_path, "rb") as f:
                    data = f.read()

                os.unlink(output_path)

                return Response(
                    data,
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={
                        "Content-Disposition": f"attachment; filename=bom_{project_id}_{int(time.time())}.xlsx"
                    },
                )
        else:
            with tempfile.NamedTemporaryFile(
                suffix=".csv", delete=False, mode="w", encoding="utf-8"
            ) as tmp:
                output_path = bom_mgr.export_to_csv(
                    project_id, tmp.name, include_pricing, supplier
                )

                with open(output_path, encoding="utf-8") as f:
                    data = f.read()

                os.unlink(output_path)

                return Response(
                    data,
                    mimetype="text/csv",
                    headers={
                        "Content-Disposition": f"attachment; filename=bom_{project_id}_{int(time.time())}.csv"
                    },
                )

    except Exception as e:
        logger.error("BOM Export error: %s", e)
        return jsonify({"error": "Failed to export BOM"}), 500


@bom_bp.route("/api/bom/<project_id>/pricing", methods=["GET"])
def api_bom_pricing(project_id):
    try:
        from src.utils.bom_manager import BOMManager

        supplier = request.args.get("supplier", "digikey").lower()

        bom_mgr = BOMManager()
        shopping_list = bom_mgr.create_shopping_list(project_id, supplier)

        return jsonify(
            {
                "project_id": project_id,
                "supplier": supplier,
                "items": shopping_list["items"],
                "unavailable": shopping_list["unavailable"],
                "total_cost": shopping_list["total_cost"],
                "total_items": shopping_list["total_items"],
                "generated_at": shopping_list["generated_at"],
            }
        )

    except Exception as e:
        logger.error("BOM Pricing error: %s", e)
        return jsonify({"error": "Failed to retrieve pricing"}), 500


@bom_bp.route("/api/bom/<project_id>/shopping-list", methods=["GET"])
def api_bom_shopping_list(project_id):
    try:
        from src.utils.bom_manager import BOMManager

        supplier = request.args.get("supplier", "digikey").lower()
        format_type = request.args.get("format", "json").lower()

        bom_mgr = BOMManager()

        if format_type == "csv":
            with tempfile.NamedTemporaryFile(
                suffix=".csv", delete=False, mode="w", encoding="utf-8"
            ) as tmp:
                output_path = bom_mgr.export_shopping_list_to_csv(
                    project_id, tmp.name, supplier
                )

                with open(output_path, encoding="utf-8") as f:
                    data = f.read()

                os.unlink(output_path)

                return Response(
                    data,
                    mimetype="text/csv",
                    headers={
                        "Content-Disposition": f"attachment; filename=shopping_list_{project_id}_{int(time.time())}.csv"
                    },
                )
        else:
            shopping_list = bom_mgr.create_shopping_list(project_id, supplier)
            return jsonify(shopping_list)

    except Exception as e:
        logger.error("Shopping List error: %s", e)
        return jsonify({"error": "Failed to generate shopping list"}), 500


@bom_bp.route("/api/bom/<project_id>/summary", methods=["GET"])
def api_bom_summary(project_id):
    try:
        from src.utils.bom_manager import BOMManager

        bom_mgr = BOMManager()
        summary = bom_mgr.get_bom_summary(project_id)

        return jsonify(summary.to_dict())

    except Exception as e:
        logger.error("BOM Summary error: %s", e)
        return jsonify({"error": "Failed to retrieve BOM summary"}), 500


@bom_bp.route("/api/bom/compare", methods=["GET"])
def api_bom_compare():
    try:
        from src.utils.bom_manager import BOMManager

        project_id_v1 = request.args.get("v1")
        project_id_v2 = request.args.get("v2")

        if not project_id_v1 or not project_id_v2:
            return jsonify({"error": "Both v1 and v2 project IDs are required"}), 400

        bom_mgr = BOMManager()
        result = bom_mgr.compare_boms(project_id_v1, project_id_v2)

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error("BOM Compare error: %s", e)
        return jsonify({"error": "Failed to compare BOMs"}), 500


@bom_bp.route("/api/bom/part/search", methods=["GET"])
def api_bom_part_search():
    try:
        from src.utils.bom_manager import BOMManager

        part_number = request.args.get("part_number")
        supplier = request.args.get("supplier", "digikey").lower()

        if not part_number:
            return jsonify({"error": "part_number is required"}), 400

        bom_mgr = BOMManager()
        part_info = bom_mgr.search_part(part_number, supplier)

        if part_info:
            return jsonify(
                {
                    "part_number": part_info.part_number,
                    "manufacturer": part_info.manufacturer,
                    "description": part_info.description,
                    "availability": part_info.availability,
                    "pricing": part_info.pricing,
                    "datasheet_url": part_info.datasheet_url,
                    "image_url": part_info.image_url,
                    "lead_time": part_info.lead_time,
                    "supplier": part_info.supplier,
                }
            )
        else:
            return jsonify({"error": "Part not found"}), 404

    except Exception as e:
        logger.error("Part Search error: %s", e)
        return jsonify({"error": "Failed to search parts"}), 500
