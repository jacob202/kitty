"""
SchematicOverlayGenerator - Generates SVG overlays for schematic images
with clickable component hotspots and trace paths.

Usage:
    generator = SchematicOverlayGenerator()
    svg = generator.generate_overlay("schematic.png", components)
    generator.to_file("overlay.svg")
    base64_svg = generator.to_base64()
"""

import base64
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Component:
    """Represents a schematic component."""

    designator: str  # e.g., "R101"
    type: str  # e.g., "Resistor"
    x: float  # x coordinate
    y: float  # y coordinate
    width: float = 20.0  # marker width
    height: float = 20.0  # marker height
    rotation: float = 0.0  # rotation in degrees


class SchematicOverlayGenerator:
    """
    Generates SVG overlays for schematic images with clickable component hotspots.

    Features:
    - Transparent overlay matching image dimensions
    - Clickable component markers
    - Hover effects with CSS
    - Trace path visualization
    - Export to file or base64
    """

    # Default styling constants
    DEFAULT_MARKER_SIZE = 20
    DEFAULT_MARKER_COLOR = "rgba(59, 130, 246, 0.7)"  # Blue with transparency
    DEFAULT_MARKER_HOVER = "rgba(59, 130, 246, 0.9)"
    DEFAULT_STROKE_COLOR = "rgba(59, 130, 246, 1.0)"
    DEFAULT_TEXT_COLOR = "#1f2937"
    DEFAULT_TRACE_COLOR = "rgba(239, 68, 68, 0.8)"  # Red for traces

    def __init__(self):
        self._svg_root: ET.Element | None = None
        self._image_width: float = 0
        self._image_height: float = 0
        self._image_path: str | None = None
        self._components: list[Component] = []
        self._trace_paths: list[list[tuple[float, float]]] = []

    def generate_overlay(
        self,
        image_path: str,
        components: list[Component],
        image_width: float | None = None,
        image_height: float | None = None,
    ) -> str:
        """
        Generate an SVG overlay for a schematic image.

        Args:
            image_path: Path to the schematic image
            components: List of Component objects to mark
            image_width: Optional image width (auto-detected if not provided)
            image_height: Optional image height (auto-detected if not provided)

        Returns:
            SVG string with transparent overlay and component hotspots
        """
        self._image_path = image_path
        self._components = components

        # Get image dimensions
        if image_width and image_height:
            self._image_width = image_width
            self._image_height = image_height
        else:
            self._image_width, self._image_height = self._detect_image_size(image_path)

        # Create SVG root
        self._svg_root = self._create_svg_root()

        # Add CSS styles
        self._add_styles()

        # Add component markers
        self._add_component_markers()

        # Add trace paths if any
        self._add_trace_paths_to_svg()

        # Convert to string
        return self._to_string()

    def add_trace_path(self, points: list[tuple[float, float]]) -> "SchematicOverlayGenerator":
        """
        Add a trace path connecting multiple points.

        Args:
            points: List of (x, y) coordinate tuples

        Returns:
            Self for method chaining
        """
        self._trace_paths.append(points)

        # If SVG already generated, add the path
        if self._svg_root is not None:
            self._add_single_trace_path(points)

        return self

    def to_file(self, output_path: str) -> str:
        """
        Save the SVG overlay to a file.

        Args:
            output_path: Path to save the SVG file

        Returns:
            Path to the saved file
        """
        if self._svg_root is None:
            raise ValueError("No overlay generated. Call generate_overlay() first.")

        svg_string = self._to_string()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg_string)

        return str(output_path)

    def to_base64(self) -> str:
        """
        Convert the SVG overlay to base64 for embedding.

        Returns:
            Base64 encoded SVG string with data URI prefix
        """
        if self._svg_root is None:
            raise ValueError("No overlay generated. Call generate_overlay() first.")

        svg_string = self._to_string()
        svg_bytes = svg_string.encode("utf-8")
        base64_encoded = base64.b64encode(svg_bytes).decode("utf-8")

        return f"data:image/svg+xml;base64,{base64_encoded}"

    def _create_svg_root(self) -> ET.Element:
        """Create the root SVG element with proper namespace and viewBox."""
        svg = ET.Element("svg")
        svg.set("xmlns", "http://www.w3.org/2000/svg")
        svg.set("xmlns:xlink", "http://www.w3.org/1999/xlink")
        svg.set("viewBox", f"0 0 {self._image_width} {self._image_height}")
        svg.set("width", str(self._image_width))
        svg.set("height", str(self._image_height))
        svg.set("class", "schematic-overlay")

        return svg

    def _add_styles(self) -> None:
        """Add CSS styles for hover effects and component styling."""
        style = ET.SubElement(self._svg_root, "style")
        style.text = """
            .schematic-overlay {
                position: absolute;
                top: 0;
                left: 0;
                pointer-events: auto;
            }

            .component-marker {
                cursor: pointer;
                transition: all 0.2s ease;
            }

            .component-marker:hover .marker-shape {
                fill: var(--marker-hover-color, rgba(59, 130, 246, 0.9));
                stroke-width: 3;
            }

            .component-marker:hover .marker-label {
                opacity: 1;
                transform: translateY(-5px);
            }

            .marker-shape {
                fill: var(--marker-color, rgba(59, 130, 246, 0.7));
                stroke: var(--stroke-color, rgba(59, 130, 246, 1.0));
                stroke-width: 2;
                transition: all 0.2s ease;
            }

            .marker-label {
                font-family: system-ui, -apple-system, sans-serif;
                font-size: 12px;
                font-weight: 600;
                fill: var(--text-color, #1f2937);
                opacity: 0.8;
                text-anchor: middle;
                pointer-events: none;
                transition: all 0.2s ease;
            }

            .trace-path {
                fill: none;
                stroke: var(--trace-color, rgba(239, 68, 68, 0.8));
                stroke-width: 3;
                stroke-linecap: round;
                stroke-linejoin: round;
                pointer-events: none;
                stroke-dasharray: 1000;
                stroke-dashoffset: 1000;
                animation: drawPath 1s ease forwards;
            }

            @keyframes drawPath {
                to {
                    stroke-dashoffset: 0;
                }
            }

            .component-group {
                pointer-events: bounding-box;
            }
        """

    def _add_component_markers(self) -> None:
        """Add clickable component markers to the SVG."""
        for component in self._components:
            self._create_component_group(component)

    def _create_component_group(self, component: Component) -> None:
        """Create a component marker group with shape and label."""
        group = ET.SubElement(self._svg_root, "g")
        group.set("class", "component-marker component-group")
        group.set("data-designator", component.designator)
        group.set("data-type", component.type)
        group.set("data-x", str(component.x))
        group.set("data-y", str(component.y))

        # Calculate marker position (centered on component)
        cx = component.x
        cy = component.y
        half_width = component.width / 2
        half_height = component.height / 2

        # Create marker shape (rectangle by default, can be customized)
        rect = ET.SubElement(group, "rect")
        rect.set("class", "marker-shape")
        rect.set("x", str(cx - half_width))
        rect.set("y", str(cy - half_height))
        rect.set("width", str(component.width))
        rect.set("height", str(component.height))
        rect.set("rx", "4")  # Rounded corners

        if component.rotation != 0:
            rect.set("transform", f"rotate({component.rotation}, {cx}, {cy})")

        # Create label (positioned above the marker)
        label = ET.SubElement(group, "text")
        label.set("class", "marker-label")
        label.set("x", str(cx))
        label.set("y", str(cy - half_height - 5))
        label.text = component.designator

        # Add title for tooltip
        title = ET.SubElement(group, "title")
        title.text = f"{component.designator} ({component.type})"

    def _add_trace_paths_to_svg(self) -> None:
        """Add all stored trace paths to the SVG."""
        for points in self._trace_paths:
            self._add_single_trace_path(points)

    def _add_single_trace_path(self, points: list[tuple[float, float]]) -> None:
        """Add a single trace path to the SVG."""
        if len(points) < 2:
            return

        # Create path data
        path_data = f"M {points[0][0]} {points[0][1]}"
        for point in points[1:]:
            path_data += f" L {point[0]} {point[1]}"

        path = ET.SubElement(self._svg_root, "path")
        path.set("class", "trace-path")
        path.set("d", path_data)

    def _detect_image_size(self, image_path: str) -> tuple[float, float]:
        """
        Detect image dimensions from the file.

        Supports PNG, JPEG, GIF, BMP, and WebP formats.
        Falls back to default dimensions if detection fails.
        """
        path = Path(image_path)

        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        try:
            with open(path, "rb") as f:
                header = f.read(32)

                # PNG
                if header.startswith(b"\x89PNG\r\n\x1a\n"):
                    f.seek(16)
                    width = int.from_bytes(f.read(4), "big")
                    height = int.from_bytes(f.read(4), "big")
                    return float(width), float(height)

                # JPEG
                elif header.startswith(b"\xff\xd8"):
                    return self._get_jpeg_size(f)

                # GIF
                elif header.startswith(b"GIF"):
                    width = int.from_bytes(header[6:8], "little")
                    height = int.from_bytes(header[8:10], "little")
                    return float(width), float(height)

                # BMP
                elif header.startswith(b"BM"):
                    width = int.from_bytes(header[18:22], "little")
                    height = int.from_bytes(header[22:26], "little")
                    return float(width), float(height)

                # WebP
                elif header.startswith(b"RIFF") and header[8:12] == b"WEBP":
                    return self._get_webp_size(f)

        except Exception as e:
            print(f"Warning: Could not detect image size: {e}")

        # Default fallback
        return 800.0, 600.0

    def _get_jpeg_size(self, f) -> tuple[float, float]:
        """Extract dimensions from JPEG file."""
        f.seek(2)
        while True:
            marker = f.read(1)
            if not marker:
                break
            if marker[0] != 0xFF:
                continue

            marker_type = f.read(1)[0]

            # Skip padding
            if marker_type == 0xFF:
                continue

            # SOF markers
            if marker_type in (
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            ):
                f.seek(3, 1)  # Skip length and precision
                height = int.from_bytes(f.read(2), "big")
                width = int.from_bytes(f.read(2), "big")
                return float(width), float(height)

            # Skip segment
            if marker_type not in (
                0x00,
                0x01,
                0xD0,
                0xD1,
                0xD2,
                0xD3,
                0xD4,
                0xD5,
                0xD6,
                0xD7,
                0xD8,
                0xD9,
            ):
                length = int.from_bytes(f.read(2), "big")
                f.seek(length - 2, 1)

        return 800.0, 600.0

    def _get_webp_size(self, f) -> tuple[float, float]:
        """Extract dimensions from WebP file."""
        f.seek(12)  # Skip RIFF header and WEBP signature

        chunk_type = f.read(4)
        if chunk_type == b"VP8 ":
            # Lossy WebP
            f.seek(3, 1)  # Skip sync code
            byte1 = f.read(1)[0]
            byte2 = f.read(1)[0]
            byte3 = f.read(1)[0]

            width = (byte1 | ((byte2 & 0x3F) << 8)) + 1
            height = ((byte3 << 6) | (byte2 >> 6)) + 1
            return float(width), float(height)

        elif chunk_type == b"VP8L":
            # Lossless WebP
            f.seek(1, 1)  # Skip signature byte
            data = f.read(4)

            bits = int.from_bytes(data, "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return float(width), float(height)

        elif chunk_type == b"VP8X":
            # Extended WebP
            f.seek(4, 1)  # Skip flags
            width = int.from_bytes(f.read(3), "little") + 1
            height = int.from_bytes(f.read(3), "little") + 1
            return float(width), float(height)

        return 800.0, 600.0

    def _to_string(self) -> str:
        """Convert SVG ElementTree to formatted string."""
        # Register namespace
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

        # Convert to string
        svg_string = ET.tostring(self._svg_root, encoding="unicode")

        # Add XML declaration
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + svg_string

    @staticmethod
    def create_component(
        designator: str,
        type: str,
        x: float,
        y: float,
        width: float = 20.0,
        height: float = 20.0,
        rotation: float = 0.0,
    ) -> Component:
        """
        Factory method to create a Component instance.

        Args:
            designator: Component designator (e.g., "R101")
            type: Component type (e.g., "Resistor")
            x: X coordinate
            y: Y coordinate
            width: Marker width
            height: Marker height
            rotation: Rotation in degrees

        Returns:
            Component instance
        """
        return Component(
            designator=designator,
            type=type,
            x=x,
            y=y,
            width=width,
            height=height,
            rotation=rotation,
        )


# Example usage and test
def example():
    """Example demonstrating SchematicOverlayGenerator usage."""
    # Create generator
    generator = SchematicOverlayGenerator()

    # Define components
    components = [
        SchematicOverlayGenerator.create_component("R101", "Resistor", 100, 150),
        SchematicOverlayGenerator.create_component("C203", "Capacitor", 200, 150),
        SchematicOverlayGenerator.create_component("U1", "IC", 300, 200, width=40, height=30),
        SchematicOverlayGenerator.create_component("L501", "Inductor", 150, 300),
    ]

    # Generate overlay (use a placeholder image or specify dimensions)
    svg = generator.generate_overlay(
        image_path="schematic.png", components=components, image_width=800, image_height=600
    )

    # Add trace path between components
    generator.add_trace_path(
        [
            (100, 150),  # R101
            (150, 150),  # midpoint
            (200, 150),  # C203
        ]
    )

    # Export
    generator.to_file("output_overlay.svg")
    base64_data = generator.to_base64()

    print(f"SVG generated: {len(svg)} characters")
    print(f"Base64 length: {len(base64_data)} characters")

    return svg


if __name__ == "__main__":
    example()
