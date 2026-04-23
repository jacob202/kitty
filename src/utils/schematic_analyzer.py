"""
Kitty Module: Schematic Analyzer
Handles local vision processing for electronics schematics and PCB photos.
Integrates with Ollama (llava:13b) and Gemini Vision.
"""

import base64
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Import datasheet intelligence
try:
    from src.utils.datasheet_intelligence import CrossReferenceEngine, DatasheetFetcher

    DATASHEET_INTELLIGENCE_AVAILABLE = True
except ImportError:
    DATASHEET_INTELLIGENCE_AVAILABLE = False
    logger.warning("Datasheet intelligence module not available")

# Real-ESRGAN binary path (relative to workspace root)
REALESRGAN_BINARY = "/Users/jacobbrizinski/AgentCompany/tools/realesrgan-ncnn-vulkan"


class SchematicAnalyzer:
    def __init__(self, config: dict[str, Any] | None = None, db_client=None):
        self.config = config or {}
        self.ollama_url = "http://localhost:11434/api/generate"
        self.local_vision_model = self.config.get("local_vision_model", "llava:13b")
        self.db_client = db_client

        # Initialize datasheet intelligence if available
        self.datasheet_fetcher = None
        self.cross_ref_engine = None
        if DATASHEET_INTELLIGENCE_AVAILABLE:
            try:
                self.datasheet_fetcher = DatasheetFetcher()
                self.cross_ref_engine = CrossReferenceEngine()
                logger.info("Datasheet intelligence initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize datasheet intelligence: {e}")

    def analyze(
        self, image_path: str, query: str | None = None, upscale: bool = True
    ) -> dict[str, Any]:
        """
        Perform a high-level analysis of a schematic or PCB image.

        Args:
            image_path: Path to the image file
            query: Custom query for the analysis
            upscale: Whether to upscale the image before analysis (default: True)
        """
        if not Path(image_path).exists():
            return {"error": f"Image not found: {image_path}"}

        prompt = (
            query
            or "Analyze this electronics schematic. Identify key sections (power supply, amplifier, protection) and any visible component designators."
        )

        # Auto-upscale if enabled and binary available
        analysis_image_path = image_path
        upscaled_path = None
        if upscale:
            upscaled_path = self.upscale_image(image_path)
            if upscaled_path != image_path:
                analysis_image_path = upscaled_path
                logger.info(f"Using upscaled image: {upscaled_path}")

        # 1. Try Local Vision first if enabled
        if self._check_ollama():
            try:
                result = self._call_local_vision(analysis_image_path, prompt)
                return {
                    "source": "local_llava",
                    "analysis": result,
                    "image_used": analysis_image_path,
                    "upscaled": analysis_image_path != image_path,
                }
            except Exception as e:
                logger.warning(f"Local vision failed: {e}")

        # 2. Fallback to Gemini (via Supervisor's analyze_image or direct API)
        return {
            "source": "fallback_needed",
            "status": "Local vision unavailable or failed",
            "image_used": analysis_image_path,
            "upscaled": analysis_image_path != image_path,
        }

    def identify_components(
        self, image_path: str, project: str = "default", upscale: bool = True
    ) -> list[dict[str, Any]]:
        """
        Detect and list components (Resistors, Capacitors, etc.) found in the image.
        Stores identified components in the database if db_client is available.

        Args:
            image_path: Path to the schematic/PCB image
            project: Project name for database organization
            upscale: Whether to upscale image before analysis (default: True)

        Returns:
            List of component dictionaries with designator, type, value, location, confidence
        """
        prompt = """List all electronic components visible in this schematic/PCB image.
        Format as a JSON list of objects with these exact keys:
        - 'designator': Component reference (e.g., 'R101', 'C205', 'Q1')
        - 'type': Component type (e.g., 'resistor', 'capacitor', 'transistor')
        - 'value': Component value if visible (e.g., '10k', '100nF', '2N2222')
        - 'x': X coordinate in pixels (or 0 if unknown)
        - 'y': Y coordinate in pixels (or 0 if unknown)
        - 'confidence': Detection confidence from 0.0 to 1.0

        Example: [{"designator": "R1", "type": "resistor", "value": "10k", "x": 150, "y": 200, "confidence": 0.95}]
        """

        components = []

        # Auto-upscale if enabled
        analysis_image_path = image_path
        if upscale:
            upscaled_path = self.upscale_image(image_path)
            if upscaled_path != image_path:
                analysis_image_path = upscaled_path
                logger.info(f"Using upscaled image for component detection: {upscaled_path}")

        # In a real implementation, we'd use a fine-tuned detector or strong vision LLM
        # For now, we'll use the vision LLM to extract this data
        try:
            raw_result = self._call_local_vision(analysis_image_path, prompt)
            # Try to parse JSON from response
            import re

            json_match = re.search(r"\[.*\]", raw_result, re.DOTALL)
            if json_match:
                components = json.loads(json_match.group())

                # Store components in database if client is available
                if self.db_client and components:
                    for component in components:
                        self.store_component(project, component)

                        # Auto-fetch datasheet for identified components
                        if self.datasheet_fetcher:
                            try:
                                self._auto_fetch_datasheet(project, component)
                            except Exception as e:
                                logger.debug(
                                    f"Auto-fetch datasheet failed for {component.get('designator')}: {e}"
                                )
        except Exception as e:
            logger.warning(f"Failed to identify or store components: {e}")

        return components

    def _auto_fetch_datasheet(self, project: str, component: dict[str, Any]):
        """Automatically fetch and store datasheet for a component.

        Args:
            project: Project name
            component: Component dictionary with designator, type, value
        """
        if not self.datasheet_fetcher or not self.db_client:
            return

        designator = component.get("designator", "")
        value = component.get("value", "")
        comp_type = component.get("type", "unknown")

        # Try to extract part number from value or designator
        part_number = self._extract_part_number(value, comp_type)

        if not part_number:
            logger.debug(f"Could not extract part number for {designator}")
            return

        # Check if we already have this datasheet
        existing = self.db_client.get_datasheet_specs(part_number)
        if existing:
            # Link component to existing datasheet
            self.db_client.link_component_to_datasheet(
                project, designator, part_number, datasheet_id=existing.get("id"), auto_fetched=True
            )
            logger.info(f"Linked {designator} to existing datasheet for {part_number}")
            return

        # Fetch new datasheet
        logger.info(f"Auto-fetching datasheet for {designator} ({part_number})")
        result = self.datasheet_fetcher.fetch_datasheet(part_number)

        if result.get("success"):
            # Extract specs
            try:
                specs = self.datasheet_fetcher.extract_specs(result["pdf_path"])
                specs_data = specs.to_dict()
                specs_data["source_url"] = result.get("url", "")

                # Save to database
                datasheet_id = self.db_client.save_datasheet_specs(
                    part_number,
                    specs_data,
                    manufacturer=result.get("metadata", {}).get("manufacturer"),
                )

                # Link component
                self.db_client.link_component_to_datasheet(
                    project, designator, part_number, datasheet_id=datasheet_id, auto_fetched=True
                )

                logger.info(f"Datasheet fetched and saved for {designator} ({part_number})")
            except Exception as e:
                logger.warning(f"Failed to extract/save datasheet specs for {part_number}: {e}")
        else:
            logger.debug(f"Could not fetch datasheet for {part_number}: {result.get('error')}")

    def _extract_part_number(self, value: str, comp_type: str) -> str | None:
        """Extract part number from component value.

        Args:
            value: Component value string
            comp_type: Component type

        Returns:
            Part number or None
        """
        if not value:
            return None

        import re

        value = value.strip()

        # Common patterns for part numbers
        # ICs: alphanumeric with numbers (LM358, 2N2222, etc.)
        ic_pattern = r"^([A-Z]{1,4}\d{2,}[A-Z0-9]*)$"
        match = re.match(ic_pattern, value.upper())
        if match:
            return match.group(1)

        # Transistors: 2N, PN, BC, BD prefix
        transistor_pattern = r"^(2N|PN|BC|BD|BF|BU|2S[ACJ]|MPS[A-Z]?)(\d{3,}[A-Z]*)$"
        match = re.match(transistor_pattern, value.upper())
        if match:
            return match.group(0)

        # Voltage regulators: 78xx, 79xx, LM317, etc.
        regulator_pattern = r"^(LM?\d{2,4}[A-Z]?|78[LM]?\d{2}|79[LM]?\d{2})$"
        match = re.match(regulator_pattern, value.upper())
        if match:
            return match.group(1)

        # Op-amps: LM358, TL072, NE5532, etc.
        opamp_pattern = r"^(LM|TL|NE|MC|CA|RC|AD)(\d{3,4}[A-Z]*)$"
        match = re.match(opamp_pattern, value.upper())
        if match:
            return match.group(0)

        return None

    def get_component_datasheet(self, project: str, designator: str) -> dict[str, Any] | None:
        """Get datasheet information for a component.

        Args:
            project: Project name
            designator: Component designator (e.g., "R101")

        Returns:
            Datasheet info or None
        """
        if not self.db_client:
            return None

        return self.db_client.get_component_datasheet(project, designator)

    def get_equivalent_parts(self, part_number: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get equivalent parts for a part number.

        Args:
            part_number: Part number to find equivalents for
            limit: Maximum results

        Returns:
            List of equivalent parts
        """
        if not self.cross_ref_engine:
            return []

        return self.cross_ref_engine.find_equivalent_parts(part_number, limit=limit)

    def store_component(self, project: str, component: dict[str, Any]) -> int | None:
        """
        Store a single component in the database.

        Args:
            project: Project name for organization
            component: Dict with keys: designator, type, value, x, y, confidence

        Returns:
            ID of the inserted record, or None if db_client not available
        """
        if not self.db_client:
            logger.warning("No database client available for component storage")
            return None

        try:
            # Extract location coordinates
            x = component.get("x", 0)
            y = component.get("y", 0)
            coordinates = json.dumps({"x": x, "y": y})

            query = """
                INSERT INTO hardware_entities
                (project, designator, value, type, coordinates, confidence, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """

            result = self.db_client.execute(
                query,
                (
                    project,
                    component.get("designator", ""),
                    component.get("value", ""),
                    component.get("type", "unknown"),
                    coordinates,
                    float(component.get("confidence", 1.0)),
                    "schematic_analysis",
                ),
            ).fetchone()

            return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to store component: {e}")
            return None

    def lookup_component(self, project: str, designator: str) -> dict[str, Any] | None:
        """
        Look up a component by its designator in a specific project.

        Args:
            project: Project name
            designator: Component designator (e.g., 'R101', 'C205')

        Returns:
            Component dict or None if not found
        """
        if not self.db_client:
            logger.warning("No database client available for component lookup")
            return None

        try:
            query = """
                SELECT project, designator, value, type, coordinates, confidence, source, created_at
                FROM hardware_entities
                WHERE project = ? AND designator = ?
                ORDER BY created_at DESC
                LIMIT 1
            """

            cursor = self.db_client.execute(query, (project, designator))
            row = cursor.fetchone()

            if row:
                columns = [desc[0] for desc in cursor.description]
                result = dict(zip(columns, row))
                # Parse coordinates JSON
                if result.get("coordinates"):
                    coords = json.loads(result["coordinates"])
                    result["x"] = coords.get("x", 0)
                    result["y"] = coords.get("y", 0)
                return result
            return None
        except Exception as e:
            logger.error(f"Failed to lookup component: {e}")
            return None

    def lookup_components(
        self, project: str, vision_output: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Look up components from vision model output and enrich with database records.

        Takes raw vision model output (list of detected components) and queries the
        database for each component, adding additional data like datasheets,
        cross-references, and specifications.

        Args:
            project: Project name
            vision_output: List of component dicts from vision model with keys:
                - designator: Component reference (e.g., 'R101', 'C205')
                - type: Component type (e.g., 'resistor', 'capacitor')
                - value: Component value if visible
                - x, y: Coordinates (optional)
                - confidence: Detection confidence

        Returns:
            List of enriched component dicts with database records merged in.
            Each dict includes original vision data plus:
                - found_in_db: Whether component was in database
                - datasheet: Datasheet info if available
                - equivalents: Cross-reference parts if available
        """
        if not self.db_client:
            logger.warning("No database client available for component lookup")
            return vision_output

        enriched_components = []

        for component in vision_output:
            designator = component.get("designator", "")
            if not designator:
                # Skip components without designators
                component["found_in_db"] = False
                enriched_components.append(component)
                continue

            try:
                # Look up in database
                db_record = self.lookup_component(project, designator)

                if db_record:
                    # Merge database record with vision output
                    enriched = {**component}
                    enriched["found_in_db"] = True
                    enriched["db_id"] = db_record.get("id")

                    # Add database values (prefer vision output if different)
                    if not enriched.get("value") and db_record.get("value"):
                        enriched["value"] = db_record.get("value")
                    if not enriched.get("type") and db_record.get("type"):
                        enriched["type"] = db_record.get("type")

                    # Add coordinates if not in vision output
                    if enriched.get("x", 0) == 0 and db_record.get("x"):
                        enriched["x"] = db_record.get("x")
                    if enriched.get("y", 0) == 0 and db_record.get("y"):
                        enriched["y"] = db_record.get("y")

                    # Add confidence from database if higher
                    db_conf = float(db_record.get("confidence", 0))
                    vision_conf = float(enriched.get("confidence", 0))
                    if db_conf > vision_conf:
                        enriched["confidence"] = db_conf
                        enriched["confidence_source"] = "database"
                    else:
                        enriched["confidence_source"] = "vision"

                    # Get datasheet info
                    try:
                        datasheet = self.db_client.get_component_datasheet(project, designator)
                        if datasheet:
                            enriched["datasheet"] = {
                                "specs": datasheet.get("specs"),
                                "pinout": datasheet.get("pinout"),
                                "pdf_path": datasheet.get("pdf_path"),
                                "source_url": datasheet.get("source_url"),
                            }
                    except Exception as e:
                        logger.debug(f"Failed to get datasheet for {designator}: {e}")

                    # Get cross-reference equivalents
                    part_number = self._extract_part_number(
                        enriched.get("value", ""), enriched.get("type", "")
                    )
                    if part_number:
                        try:
                            cross_refs = self.db_client.get_cross_references(part_number)
                            if cross_refs:
                                enriched["equivalents"] = cross_refs
                        except Exception as e:
                            logger.debug(f"Failed to get cross-references for {part_number}: {e}")

                    enriched_components.append(enriched)
                else:
                    # Component not found in database
                    component["found_in_db"] = False
                    enriched_components.append(component)

            except Exception as e:
                logger.error(f"Error enriching component {designator}: {e}")
                component["found_in_db"] = False
                component["enrichment_error"] = str(e)
                enriched_components.append(component)

        logger.info(f"Enriched {len(enriched_components)} components from vision output")
        return enriched_components

    def search_components(
        self, project: str, component_type: str | None = None, value: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Search for components by type or value in a project.

        Args:
            project: Project name
            component_type: Filter by component type (e.g., 'resistor', 'capacitor')
            value: Filter by component value (e.g., '10k', '100nF')

        Returns:
            List of matching component dictionaries
        """
        if not self.db_client:
            logger.warning("No database client available for component search")
            return []

        try:
            conditions = ["project = ?"]
            params = [project]

            if component_type:
                conditions.append("LOWER(type) = LOWER(?)")
                params.append(component_type)

            if value:
                conditions.append("LOWER(value) LIKE LOWER(?)")
                params.append(f"%{value}%")

            where_clause = " AND ".join(conditions)

            query = f"""
                SELECT project, designator, value, type, coordinates, confidence, source, created_at
                FROM hardware_entities
                WHERE {where_clause}
                ORDER BY type, designator
            """

            cursor = self.db_client.execute(query, tuple(params))
            columns = [desc[0] for desc in cursor.description]

            results = []
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                # Parse coordinates JSON
                if result.get("coordinates"):
                    coords = json.loads(result["coordinates"])
                    result["x"] = coords.get("x", 0)
                    result["y"] = coords.get("y", 0)
                results.append(result)

            return results
        except Exception as e:
            logger.error(f"Failed to search components: {e}")
            return []

    def get_schematic_components(self, project: str) -> list[dict[str, Any]]:
        """
        Retrieve all components for a schematic project.

        Args:
            project: Project name

        Returns:
            List of all component dictionaries for the project
        """
        if not self.db_client:
            logger.warning("No database client available")
            return []

        try:
            query = """
                SELECT project, designator, value, type, coordinates, confidence, source, created_at
                FROM hardware_entities
                WHERE project = ?
                ORDER BY
                    CASE
                        WHEN LOWER(type) = 'ic' THEN 1
                        WHEN LOWER(type) = 'transistor' THEN 2
                        WHEN LOWER(type) = 'diode' THEN 3
                        WHEN LOWER(type) = 'capacitor' THEN 4
                        WHEN LOWER(type) = 'resistor' THEN 5
                        WHEN LOWER(type) = 'inductor' THEN 6
                        WHEN LOWER(type) = 'connector' THEN 7
                        ELSE 8
                    END,
                    designator
            """

            cursor = self.db_client.execute(query, (project,))
            columns = [desc[0] for desc in cursor.description]

            results = []
            for row in cursor.fetchall():
                result = dict(zip(columns, row))
                # Parse coordinates JSON
                if result.get("coordinates"):
                    coords = json.loads(result["coordinates"])
                    result["x"] = coords.get("x", 0)
                    result["y"] = coords.get("y", 0)
                results.append(result)

            return results
        except Exception as e:
            logger.error(f"Failed to get schematic components: {e}")
            return []

    def upscale_image(
        self, image_path: str, model: str = "realesrgan-x4plus", output_path: str | None = None
    ) -> str:
        """
        Upscale the image using Real-ESRGAN binary.

        Args:
            image_path: Path to the input image
            model: Model to use (default: realesrgan-x4plus)
            output_path: Optional output path (default: input.upscaled.png)

        Returns:
            Path to upscaled image on success, original path on failure
        """
        # Validate input path
        if not Path(image_path).exists():
            logger.error(f"Input image not found: {image_path}")
            return image_path

        # Generate output path if not provided
        if output_path is None:
            input_path = Path(image_path)
            output_path = str(input_path.with_suffix(".upscaled.png"))

        # Check if binary exists
        if not Path(REALESRGAN_BINARY).exists():
            logger.warning(
                f"Real-ESRGAN binary not found at: {REALESRGAN_BINARY}. Falling back to PIL upscaling."
            )
            return self._upscale_with_pil(image_path, output_path)

        # Check if binary is executable
        if not os.access(REALESRGAN_BINARY, os.X_OK):
            logger.warning(
                f"Real-ESRGAN binary is not executable: {REALESRGAN_BINARY}. Falling back to PIL upscaling."
            )
            return self._upscale_with_pil(image_path, output_path)

        try:
            # Build command
            cmd = [REALESRGAN_BINARY, "-i", image_path, "-o", output_path, "-n", model]

            logger.info(f"Upscaling image: {image_path} -> {output_path} (model: {model})")

            # Run upscaling with timeout
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=True,
            )

            # Verify output was created
            if not Path(output_path).exists():
                logger.error(f"Upscaled image was not created: {output_path}")
                return self._upscale_with_pil(image_path, output_path)

            # Check output file size
            output_size = Path(output_path).stat().st_size
            if output_size == 0:
                logger.error(f"Upscaled image is empty: {output_path}")
                os.remove(output_path)
                return self._upscale_with_pil(image_path, output_path)

            logger.info(f"Upscaling successful: {output_path} ({output_size} bytes)")
            return output_path

        except subprocess.CalledProcessError as e:
            # Handle non-zero exit code from Real-ESRGAN
            logger.warning(f"Real-ESRGAN failed with exit code {e.returncode}")
            logger.warning(f"  stdout: {e.stdout[:500] if e.stdout else 'empty'}")
            logger.warning(f"  stderr: {e.stderr[:500] if e.stderr else 'empty'}")
            logger.info(f"Gracefully falling back to PIL upscaling for {image_path}")
            # Clean up partial output
            if Path(output_path).exists():
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            return self._upscale_with_pil(image_path, output_path)

        except FileNotFoundError as e:
            # Handle missing binary or input file
            logger.warning(f"File not found during upscaling: {e}")
            logger.warning(f"Binary: {REALESRGAN_BINARY}")
            logger.info(f"Gracefully falling back to PIL upscaling for {image_path}")
            return self._upscale_with_pil(image_path, output_path)

        except subprocess.TimeoutExpired:
            logger.warning(f"Real-ESRGAN upscaling timed out after 5 minutes for: {image_path}")
            logger.info("Falling back to PIL upscaling")
            # Clean up partial output
            if Path(output_path).exists():
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            return self._upscale_with_pil(image_path, output_path)

        except PermissionError as e:
            # Handle permission denied errors
            logger.warning(f"Permission denied running Real-ESRGAN: {e}")
            logger.warning(f"Binary: {REALESRGAN_BINARY}")
            logger.info(f"Gracefully falling back to PIL upscaling for {image_path}")
            return self._upscale_with_pil(image_path, output_path)

        except Exception as e:
            # Catch-all for any other unexpected errors
            logger.error(f"Unexpected error during Real-ESRGAN upscaling: {type(e).__name__}: {e}")
            logger.info(f"Gracefully falling back to PIL upscaling for {image_path}")
            # Clean up partial output
            if Path(output_path).exists():
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            return self._upscale_with_pil(image_path, output_path)

    def _upscale_with_pil(self, image_path: str, output_path: str, scale: int = 4) -> str:
        """
        Fallback upscaling using PIL/Pillow.
        Uses Lanczos resampling for quality.

        Args:
            image_path: Path to input image
            output_path: Path for output image
            scale: Upscaling factor (default 4x)

        Returns:
            Path to upscaled image
        """
        try:
            from PIL import Image

            logger.info(f"Using PIL fallback upscaling: {image_path}")

            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                # Calculate new size
                new_width = img.width * scale
                new_height = img.height * scale

                # Upscale using high-quality resampling
                # Use the appropriate constant based on PIL version
                if hasattr(Image, "Resampling"):
                    resampling_filter = Image.Resampling.LANCZOS
                else:
                    # For older PIL versions, use the direct constant value (LANCZOS=1)
                    resampling_filter = 1  # LANCZOS constant
                upscaled = img.resize((new_width, new_height), resampling_filter)

                # Save as PNG
                upscaled.save(output_path, "PNG", quality=95)

                logger.info(f"PIL upscaling successful: {output_path} ({new_width}x{new_height})")
                return output_path

        except ImportError:
            logger.error("PIL/Pillow not available for fallback upscaling")
            return image_path
        except Exception as e:
            logger.error(f"PIL upscaling failed: {type(e).__name__}: {e}")
            return image_path

    def _check_ollama(self) -> bool:
        try:
            import requests

            r = requests.get("http://localhost:11434/api/tags", timeout=1)
            return r.status_code == 200
        except Exception:
            return False

    def _call_local_vision(self, image_path: str, prompt: str) -> str:
        import requests

        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()

        payload = {
            "model": self.local_vision_model,
            "prompt": prompt,
            "images": [img_data],
            "stream": False,
        }

        response = requests.post(self.ollama_url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "")


# Module integration helper
def get_analyzer(config: dict[str, Any] | None = None, db_client=None) -> SchematicAnalyzer:
    return SchematicAnalyzer(config, db_client)
