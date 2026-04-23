"""
DuckDB client for hardware component and BOM data storage.
"""

import json
import logging
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


class DuckDBClient:
    """Client for interacting with DuckDB database for hardware BOM data."""

    def __init__(self, db_path: str = None, read_only: bool = False):
        """Initialize DuckDB connection.

        Args:
            db_path: Path to DuckDB database file. If None, uses in-memory database.
            read_only: If True, open in read-only mode to avoid lock conflicts.
        """
        if db_path is None:
            # Default to a file in the project directory
            project_dir = Path(__file__).parent.parent.parent
            db_path = str(project_dir / "data" / "hardware_bom.db")

        self.db_path = db_path
        self.read_only = read_only
        self._conn = None
        self._connect()
        self._setup_tables()

    def _connect(self):
        """Establish database connection with retry logic."""
        import time

        max_retries = 3
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                if self.read_only:
                    self._conn = duckdb.connect(self.db_path, read_only=True)
                else:
                    self._conn = duckdb.connect(self.db_path)
                return
            except Exception as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                raise

    @property
    def conn(self):
        """Get connection, reconnect if needed."""
        if self._conn is None:
            self._connect()
        return self._conn

    def close(self):
        """Close connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _setup_tables(self):
        """Create necessary tables if they don't exist."""
        # BOM components table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bom_components (
                id INTEGER PRIMARY KEY,
                project TEXT NOT NULL,
                designator TEXT NOT NULL,
                value TEXT,
                type TEXT,
                quantity INTEGER DEFAULT 1,
                description TEXT,
                manufacturer TEXT,
                part_number TEXT,
                price DECIMAL(10, 2),
                supplier TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index for faster queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bom_project
            ON bom_components(project, designator)
        """)

        # Hardware entities table (from schematic analysis)
        # Create sequence for auto-increment
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS hardware_entities_id_seq START 1
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS hardware_entities (
                id INTEGER PRIMARY KEY DEFAULT nextval('hardware_entities_id_seq'),
                project TEXT NOT NULL,
                designator TEXT NOT NULL,
                value TEXT,
                type TEXT,
                coordinates JSON,
                confidence DECIMAL(5, 4),
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Datasheet specs table for extracted component specifications
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS datasheet_specs (
                id INTEGER PRIMARY KEY,
                part_number TEXT NOT NULL,
                manufacturer TEXT,
                description TEXT,
                specs JSON,                -- All extracted specifications
                pinout JSON,               -- Pin configuration for ICs
                pdf_path TEXT,             -- Local path to downloaded PDF
                source_url TEXT,           -- Original datasheet URL
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Component datasheet linkage table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS component_datasheets (
                id INTEGER PRIMARY KEY,
                project TEXT NOT NULL,
                designator TEXT NOT NULL,
                part_number TEXT NOT NULL,
                datasheet_id INTEGER,
                auto_fetched BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (datasheet_id) REFERENCES datasheet_specs(id)
            )
        """)

        # Cross-reference cache table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cross_references (
                id INTEGER PRIMARY KEY,
                original_part TEXT NOT NULL,
                equivalent_part TEXT NOT NULL,
                manufacturer TEXT,
                compatibility_type TEXT,   -- 'direct', 'functional', 'upgrade'
                confidence DECIMAL(3, 2),
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes for faster queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_datasheet_part
            ON datasheet_specs(part_number)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_component_datasheets
            ON component_datasheets(project, designator)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cross_ref
            ON cross_references(original_part)
        """)

    def execute(self, query: str, params: tuple = None):
        """Execute a SQL query with optional parameters."""
        if params:
            return self.conn.execute(query, params)
        else:
            return self.conn.execute(query)

    def add_bom_component(self, project: str, component: dict[str, Any]) -> int:
        """Add a component to the BOM for a project."""
        query = """
            INSERT INTO bom_components
            (project, designator, value, type, quantity, description,
             manufacturer, part_number, price, supplier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """

        result = self.execute(
            query,
            (
                project,
                component.get("designator", ""),
                component.get("value", ""),
                component.get("type", ""),
                component.get("quantity", 1),
                component.get("description", ""),
                component.get("manufacturer", ""),
                component.get("part_number", ""),
                component.get("price", 0.0),
                component.get("supplier", ""),
            ),
        ).fetchone()

        return result[0] if result else None

    def get_bom_for_project(self, project: str) -> list[dict[str, Any]]:
        """Get all BOM components for a project."""
        query = """
            SELECT designator, value, type, quantity, description,
                   manufacturer, part_number, price, supplier
            FROM bom_components
            WHERE project = ?
            ORDER BY
                CASE
                    WHEN type = 'ic' THEN 1
                    WHEN type = 'transistor' THEN 2
                    WHEN type = 'diode' THEN 3
                    WHEN type = 'capacitor' THEN 4
                    WHEN type = 'resistor' THEN 5
                    WHEN type = 'inductor' THEN 6
                    WHEN type = 'connector' THEN 7
                    ELSE 8
                END,
                designator
        """

        cursor = self.execute(query, (project,))
        columns = [desc[0] for desc in cursor.description]

        results = []
        for row in cursor.fetchall():
            result = dict(zip(columns, row))
            # Convert decimal to float for JSON serialization
            if "price" in result and result["price"] is not None:
                result["price"] = float(result["price"])
            results.append(result)

        return results

    def import_from_hardware_analysis(self, project: str, entities: list[dict[str, Any]]):
        """Import hardware entities from schematic analysis into BOM."""
        for entity in entities:
            properties = entity.get("properties", {})
            designator = properties.get("designator", "")
            value = properties.get("value", "")
            type_ = entity.get("type", "unknown")

            if designator:  # Only add if we have a designator
                component = {
                    "designator": designator,
                    "value": value,
                    "type": type_,
                    "quantity": 1,
                    "description": f"{type_} component from schematic analysis",
                    "manufacturer": "",
                    "part_number": "",
                    "price": 0.0,
                    "supplier": "",
                }
                self.add_bom_component(project, component)

    def export_to_csv(self, project: str, filepath: str = None) -> str:
        """Export BOM for a project to CSV file.

        Args:
            project: Project name
            filepath: Output file path. If None, returns CSV as string.

        Returns:
            CSV content if filepath is None, otherwise filepath
        """
        bom_data = self.get_bom_for_project(project)

        if not bom_data:
            return "" if filepath is None else filepath

        import csv
        import io

        if filepath is None:
            # Return as string
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=bom_data[0].keys())
            writer.writeheader()
            writer.writerows(bom_data)
            return output.getvalue()
        else:
            # Write to file
            with open(filepath, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=bom_data[0].keys())
                writer.writeheader()
                writer.writerows(bom_data)
            return filepath

    def export_bom(
        self,
        project: str,
        format: str = "csv",
        filepath: str = None,
        include_datasheets: bool = False,
    ) -> str:
        """
        Export Bill of Materials for a project in specified format.

        Args:
            project: Project name
            format: Export format ('csv' or 'json')
            filepath: Optional output file path. If None, returns content as string.
            include_datasheets: Whether to include datasheet information

        Returns:
            File path if filepath provided, otherwise content string
        """
        # Get BOM data
        bom_data = self.get_bom_for_project(project)

        if not bom_data:
            logger.warning(f"No BOM data found for project: {project}")
            return "" if filepath is None else filepath

        # CSV export with enhanced columns
        if format.lower() == "csv":
            return self._export_bom_csv(project, bom_data, filepath, include_datasheets)

        # JSON export
        elif format.lower() == "json":
            return self._export_bom_json(project, bom_data, filepath, include_datasheets)

        else:
            raise ValueError(f"Unsupported format: {format}. Use 'csv' or 'json'.")

    def _export_bom_csv(
        self,
        project: str,
        bom_data: list[dict[str, Any]],
        filepath: str = None,
        include_datasheets: bool = False,
    ) -> str:
        """Export BOM as CSV with proper escaping and formatting."""
        import csv
        import io

        # Define CSV columns
        base_columns = [
            "designator",
            "value",
            "type",
            "quantity",
            "description",
            "manufacturer",
            "part_number",
            "price",
            "supplier",
        ]

        # Add datasheet columns if requested
        if include_datasheets:
            base_columns.extend(["datasheet_url", "datasheet_path"])

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=base_columns, extrasaction="ignore")

        # Write header
        writer.writeheader()

        # Write data rows
        for item in bom_data:
            row = {col: item.get(col, "") for col in base_columns}

            # Format price with 2 decimal places
            if row.get("price") is not None:
                row["price"] = f"{float(row['price']):.2f}"

            # Add datasheet info if requested
            if include_datasheets:
                designator = item.get("designator", "")
                datasheet_info = self.get_component_datasheet(project, designator)
                if datasheet_info:
                    row["datasheet_url"] = datasheet_info.get("source_url", "")
                    row["datasheet_path"] = datasheet_info.get("pdf_path", "")
                else:
                    row["datasheet_url"] = ""
                    row["datasheet_path"] = ""

            writer.writerow(row)

        csv_content = output.getvalue()

        if filepath:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                f.write(csv_content)
            return filepath

        return csv_content

    def _export_bom_json(
        self,
        project: str,
        bom_data: list[dict[str, Any]],
        filepath: str = None,
        include_datasheets: bool = False,
    ) -> str:
        """Export BOM as JSON with optional datasheet information."""
        export_data = {
            "project": project,
            "export_timestamp": str(Path().cwd()),
            "total_components": len(bom_data),
            "components": [],
        }

        # Group by type for summary
        type_summary = {}
        for item in bom_data:
            comp_type = item.get("type", "unknown")
            if comp_type not in type_summary:
                type_summary[comp_type] = 0
            type_summary[comp_type] += item.get("quantity", 1)

        export_data["summary"] = {
            "by_type": type_summary,
            "total_unique": len(bom_data),
        }

        # Build component list
        for item in bom_data:
            comp_entry = {
                "designator": item.get("designator", ""),
                "value": item.get("value", ""),
                "type": item.get("type", "unknown"),
                "quantity": item.get("quantity", 1),
                "description": item.get("description", ""),
                "manufacturer": item.get("manufacturer", ""),
                "part_number": item.get("part_number", ""),
                "price": float(item["price"]) if item.get("price") is not None else None,
                "supplier": item.get("supplier", ""),
            }

            # Add datasheet info if requested
            if include_datasheets:
                designator = item.get("designator", "")
                datasheet_info = self.get_component_datasheet(project, designator)
                if datasheet_info:
                    comp_entry["datasheet"] = {
                        "source_url": datasheet_info.get("source_url", ""),
                        "pdf_path": datasheet_info.get("pdf_path", ""),
                        "specs": datasheet_info.get("specs"),
                        "pinout": datasheet_info.get("pinout"),
                    }

            export_data["components"].append(comp_entry)

        json_content = json.dumps(export_data, indent=2, default=str)

        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_content)
            return filepath

        return json_content

    # ============== DATASHEET METHODS ==============

    def save_datasheet_specs(
        self, part_number: str, specs: dict[str, Any], manufacturer: str | None = None
    ) -> int:
        """Save extracted datasheet specifications to database.

        Args:
            part_number: Component part number
            specs: Dictionary of specifications
            manufacturer: Component manufacturer

        Returns:
            ID of the inserted/updated record
        """
        query = """
            INSERT INTO datasheet_specs
            (part_number, manufacturer, description, specs, pinout, pdf_path, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                specs = EXCLUDED.specs,
                pinout = EXCLUDED.pinout,
                pdf_path = EXCLUDED.pdf_path,
                source_url = EXCLUDED.source_url,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """

        result = self.execute(
            query,
            (
                part_number,
                manufacturer,
                specs.get("description", ""),
                json.dumps(specs.get("specs", {})),
                json.dumps(specs.get("pinout", {})),
                specs.get("pdf_path", ""),
                specs.get("source_url", ""),
            ),
        ).fetchone()

        return result[0] if result else None

    def get_datasheet_specs(self, part_number: str) -> dict[str, Any] | None:
        """Get datasheet specifications for a part number.

        Args:
            part_number: Component part number

        Returns:
            Dictionary of specs or None if not found
        """
        query = """
            SELECT part_number, manufacturer, description, specs, pinout,
                   pdf_path, source_url, created_at, updated_at
            FROM datasheet_specs
            WHERE UPPER(part_number) = UPPER(?)
            ORDER BY updated_at DESC
            LIMIT 1
        """

        cursor = self.execute(query, (part_number,))
        row = cursor.fetchone()

        if row:
            columns = [desc[0] for desc in cursor.description]
            result = dict(zip(columns, row))
            # Parse JSON fields
            if result.get("specs"):
                result["specs"] = json.loads(result["specs"])
            if result.get("pinout"):
                result["pinout"] = json.loads(result["pinout"])
            return result
        return None

    def link_component_to_datasheet(
        self,
        project: str,
        designator: str,
        part_number: str,
        datasheet_id: int | None = None,
        auto_fetched: bool = False,
    ) -> int:
        """Link a schematic component to its datasheet.

        Args:
            project: Project name
            designator: Component designator (e.g., "R101")
            part_number: Component part number
            datasheet_id: Optional datasheet_specs ID
            auto_fetched: Whether this was auto-fetched

        Returns:
            ID of the linkage record
        """
        query = """
            INSERT INTO component_datasheets
            (project, designator, part_number, datasheet_id, auto_fetched)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id
        """

        result = self.execute(
            query,
            (project, designator, part_number, datasheet_id, auto_fetched),
        ).fetchone()

        return result[0] if result else None

    def get_component_datasheet(self, project: str, designator: str) -> dict[str, Any] | None:
        """Get datasheet info for a specific component.

        Args:
            project: Project name
            designator: Component designator (e.g., "R101")

        Returns:
            Dictionary with datasheet info or None
        """
        query = """
            SELECT cd.*, ds.specs, ds.pinout, ds.pdf_path, ds.source_url
            FROM component_datasheets cd
            LEFT JOIN datasheet_specs ds ON cd.datasheet_id = ds.id
            WHERE cd.project = ? AND cd.designator = ?
            ORDER BY cd.created_at DESC
            LIMIT 1
        """

        cursor = self.execute(query, (project, designator))
        row = cursor.fetchone()

        if row:
            columns = [desc[0] for desc in cursor.description]
            result = dict(zip(columns, row))
            # Parse JSON fields
            if result.get("specs"):
                result["specs"] = json.loads(result["specs"])
            if result.get("pinout"):
                result["pinout"] = json.loads(result["pinout"])
            return result
        return None

    def save_cross_reference(
        self,
        original_part: str,
        equivalent_part: str,
        manufacturer: str | None = None,
        compatibility_type: str = "direct",
        confidence: float = 0.9,
        notes: str = "",
    ) -> int:
        """Save a cross-reference relationship.

        Args:
            original_part: Original part number
            equivalent_part: Equivalent part number
            manufacturer: Manufacturer of equivalent
            compatibility_type: Type of compatibility
            confidence: Confidence score (0-1)
            notes: Additional notes

        Returns:
            ID of the record
        """
        query = """
            INSERT INTO cross_references
            (original_part, equivalent_part, manufacturer, compatibility_type, confidence, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                confidence = EXCLUDED.confidence,
                notes = EXCLUDED.notes
            RETURNING id
        """

        result = self.execute(
            query,
            (original_part, equivalent_part, manufacturer, compatibility_type, confidence, notes),
        ).fetchone()

        return result[0] if result else None

    def get_cross_references(self, part_number: str) -> list[dict[str, Any]]:
        """Get all cross-references for a part.

        Args:
            part_number: Part to find equivalents for

        Returns:
            List of equivalent parts
        """
        query = """
            SELECT equivalent_part, manufacturer, compatibility_type, confidence, notes
            FROM cross_references
            WHERE UPPER(original_part) = UPPER(?)
            ORDER BY confidence DESC
        """

        cursor = self.execute(query, (part_number,))
        columns = [desc[0] for desc in cursor.description]

        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))

        return results

    def find_equivalents(
        self,
        part_type: str,
        value: str,
        manufacturer: str | None = None,
        supplier: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search for equivalent components by type and value.

        Args:
            part_type: Component type (e.g., 'resistor', 'capacitor', 'inductor')
            value: Component value (e.g., '10k', '100nF', '1uH')
            manufacturer: Optional manufacturer filter
            supplier: Optional supplier filter
            limit: Maximum number of results

        Returns:
            List of equivalent parts sorted by availability and price
        """
        try:
            conditions = ["LOWER(type) = LOWER(?)"]
            params: list[Any] = [part_type]

            # Add value filter (fuzzy match)
            if value:
                # Normalize the value for comparison
                value.replace(" ", "").replace("Ω", "").upper()
                conditions.append("""
                    (LOWER(value) = LOWER(?)
                     OR REPLACE(REPLACE(LOWER(value), ' ', ''), 'Ω', '') LIKE REPLACE(REPLACE(LOWER(?), ' ', ''), 'Ω', '')
                     OR REPLACE(REPLACE(LOWER(value), ' ', ''), 'Ω', '') LIKE '%' || REPLACE(REPLACE(LOWER(?), ' ', ''), 'Ω', '') || '%')
                """)
                params.extend([value, value, value])

            if manufacturer:
                conditions.append("LOWER(manufacturer) LIKE LOWER(?)")
                params.append(f"%{manufacturer}%")

            if supplier:
                conditions.append("LOWER(supplier) LIKE LOWER(?)")
                params.append(f"%{supplier}%")

            where_clause = " AND ".join(conditions)

            query = f"""
                SELECT
                    designator,
                    value,
                    type,
                    quantity,
                    description,
                    manufacturer,
                    part_number,
                    price,
                    supplier
                FROM bom_components
                WHERE {where_clause}
                ORDER BY
                    CASE WHEN price > 0 THEN 0 ELSE 1 END,  -- Prefer parts with known price
                    price ASC,  -- Sort by price
                    manufacturer ASC  -- Then by manufacturer
                LIMIT ?
            """
            params.append(limit)

            cursor = self.execute(query, tuple(params))
            columns = [desc[0] for desc in cursor.description]

            results = []
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                # Convert decimal to float for JSON serialization
                if result.get("price") is not None:
                    result["price"] = float(result["price"])
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Failed to find equivalents: {e}")
            return []

    def find_equivalents_by_part_number(
        self,
        part_number: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Find equivalent parts for a specific part number.

        First checks the cross_references table, then falls back to searching
        by extracted type and value.

        Args:
            part_number: Original part number to find equivalents for
            limit: Maximum number of results

        Returns:
            List of equivalent parts with source information
        """
        results = []
        seen_part_numbers = {part_number.upper()}

        # First, check cross_references table
        cross_refs = self.get_cross_references(part_number)
        for ref in cross_refs[:limit]:
            equiv_part = ref.get("equivalent_part", "")
            if equiv_part.upper() not in seen_part_numbers:
                results.append(
                    {
                        "part_number": equiv_part,
                        "manufacturer": ref.get("manufacturer"),
                        "compatibility_type": ref.get("compatibility_type", "cross_reference"),
                        "confidence": ref.get("confidence", 0.9),
                        "notes": ref.get("notes", ""),
                        "source": "cross_reference_table",
                    }
                )
                seen_part_numbers.add(equiv_part.upper())

        # If we need more results, search by part type and value
        if len(results) < limit:
            # Try to extract type and value from part number
            part_type, value = self._parse_part_number_for_search(part_number)

            if part_type and value:
                # Find parts with same type and similar value
                equivalents = self.find_equivalents(
                    part_type=part_type,
                    value=value,
                    limit=limit - len(results),
                )

                for equiv in equivalents:
                    pn = equiv.get("part_number", "")
                    if pn.upper() not in seen_part_numbers:
                        results.append(
                            {
                                "part_number": pn,
                                "manufacturer": equiv.get("manufacturer"),
                                "value": equiv.get("value"),
                                "type": equiv.get("type"),
                                "price": equiv.get("price"),
                                "supplier": equiv.get("supplier"),
                                "compatibility_type": "functional_equivalent",
                                "confidence": 0.7,
                                "source": "functional_search",
                            }
                        )
                        seen_part_numbers.add(pn.upper())

        return results[:limit]

    def _parse_part_number_for_search(
        self, part_number: str
    ) -> tuple[str | None, str | None]:
        """
        Parse a part number to extract type and value for searching.

        Args:
            part_number: Part number to parse

        Returns:
            Tuple of (component_type, value) or (None, None)
        """
        import re

        part = part_number.upper().strip()

        # Resistor patterns: 10R, 10K, 10KΩ, 1K5, 10MEG
        resistor_patterns = [
            r"^(\d+[RKMT])\d*$",  # e.g., 10K, 10K5, 1M
            r"^(\d+\.?\d*[RKMT]\d*)$",  # e.g., 4.7K
            r"^(\d+)R(\d*)$",  # e.g., 10R5 = 10.5R
            r"^(\d+)MEG$",  # e.g., 10MEG
        ]
        for pattern in resistor_patterns:
            match = re.match(pattern, part)
            if match:
                return ("resistor", match.group(1))

        # Capacitor patterns: 100n, 100nF, 10uF, 10pF, 104
        capacitor_patterns = [
            r"^(\d+[nu]F?)$",  # e.g., 100n, 100nF, 10uF
            r"^(\d+)PF?$",  # e.g., 100pF
            r"^(\d{3})PF?$",  # e.g., 104 = 100nF (capacitor code)
            r"^(\d+\.?\d*[uUnN]F?)$",  # e.g., 10.5uF
        ]
        for pattern in capacitor_patterns:
            match = re.match(pattern, part)
            if match:
                return ("capacitor", match.group(1))

        # Inductor patterns: 10uH, 10mH
        inductor_patterns = [
            r"^(\d+\.?\d*[uUmM]H)$",  # e.g., 10uH, 10mH
        ]
        for pattern in inductor_patterns:
            match = re.match(pattern, part)
            if match:
                return ("inductor", match.group(1))

        return (None, None)


# Lazy global — only connects when first accessed, so test collection doesn't
# trigger a lock on the live server's database.
class _LazyDB:
    _instance = None
    def __getattr__(self, name):
        if self._instance is None:
            self._instance = DuckDBClient()
        return getattr(self._instance, name)

db = _LazyDB()
