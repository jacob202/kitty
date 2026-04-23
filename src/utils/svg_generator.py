import io
import re
from enum import Enum


class ComponentType(str, Enum):
    """Classification of electronic component types."""
    RESISTOR = "resistor"
    CAPACITOR = "capacitor"
    INDUCTOR = "inductor"
    DIODE = "diode"
    TRANSISTOR = "transistor"
    IC = "ic"
    CONNECTOR = "connector"
    NET = "net"
    UNKNOWN = "unknown"

# Color scheme for different component types
COLOR_SCHEMES = {
    ComponentType.RESISTOR: {"fill": "rgba(255, 99, 71, 0.2)", "stroke": "#ff6347"},
    ComponentType.CAPACITOR: {"fill": "rgba(100, 149, 237, 0.2)", "stroke": "#6495ed"},
    ComponentType.INDUCTOR: {"fill": "rgba(152, 251, 152, 0.2)", "stroke": "#98fb98"},
    ComponentType.DIODE: {"fill": "rgba(255, 215, 0, 0.2)", "stroke": "#ffd700"},
    ComponentType.TRANSISTOR: {"fill": "rgba(138, 43, 226, 0.2)", "stroke": "#8a2be2"},
    ComponentType.IC: {"fill": "rgba(220, 20, 60, 0.2)", "stroke": "#dc143c"},
    ComponentType.CONNECTOR: {"fill": "rgba(169, 169, 169, 0.2)", "stroke": "#a9a9a9"},
    ComponentType.NET: {"fill": "none", "stroke": "#4682b4", "stroke-dasharray": "5,5"},
    ComponentType.UNKNOWN: {"fill": "rgba(255, 165, 0, 0.2)", "stroke": "#ffa500"}
}

def determine_component_type(designator: str) -> ComponentType:
    """Classify component based on designator prefix."""
    if not designator:
        return ComponentType.UNKNOWN

    # Use regex for more robust designator matching
    if re.match(r'^R', designator, re.I): return ComponentType.RESISTOR
    if re.match(r'^C', designator, re.I): return ComponentType.CAPACITOR
    if re.match(r'^L', designator, re.I): return ComponentType.INDUCTOR
    if re.match(r'^D', designator, re.I): return ComponentType.DIODE
    if re.match(r'^(TR|Q)', designator, re.I): return ComponentType.TRANSISTOR
    if re.match(r'^(U|IC)', designator, re.I): return ComponentType.IC
    if re.match(r'^(J|P)', designator, re.I): return ComponentType.CONNECTOR
    if re.match(r'^N', designator, re.I): return ComponentType.NET

    return ComponentType.UNKNOWN

def generate_svg_overlay(
    components: list[dict],
    width: int = 1000,
    height: int = 1000,
    show_labels: bool = True,
    show_connections: bool = True,
    layers: dict[str, bool] = None
) -> str:
    """Generate interactive SVG overlay with semantic coloring. Optimized for memory usage."""
    if layers is None:
        layers = {"components": True, "annotations": True, "connections": True}

    buffer = io.StringIO()

    # Write SVG header with proper structure
    buffer.write(f'''<svg id="schematic-svg" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"
                 style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;">
        <style>
            .component {{
                pointer-events: all;
                transition: all 0.2s ease;
                cursor: pointer;
            }}
            .component:hover {{
                opacity: 0.8;
                stroke-width: 2.5;
            }}
            .component-label {{
                pointer-events: none;
                font-weight: bold;
                font-size: 10px;
                fill: #333;
            }}
            .connection {{
                stroke: #4682b4;
                stroke-width: 1;
                stroke-dasharray: 5,5;
                fill: none;
                pointer-events: none;
            }}
        </style>
        <rect width="100%" height="100%" fill="#f8f8f8"/>
        <g id="schematic-content">
    ''')

    # Process components directly without intermediate lists
    for comp in components:
        coords = comp.get("coordinates")
        if not coords:
            continue

        d = comp.get("designator", "unknown")
        v = comp.get("value", "")
        comp_type = determine_component_type(d)
        colors = COLOR_SCHEMES.get(comp_type, COLOR_SCHEMES[ComponentType.UNKNOWN])

        # Add component rectangle
        if layers.get("components", True):
            buffer.write(f'''
            <rect id="comp-{d}"
                  x="{coords["x"]}" y="{coords["y"]}"
                  width="{coords.get("width", 20)}" height="{coords.get("height", 20)}"
                  fill="{colors["fill"]}" stroke="{colors["stroke"]}"
                  stroke-width="1.5" rx="2"
                  class="component {comp_type.value}"
                  data-designator="{d}">
                <title>{d}: {v}</title>
            </rect>
            ''')

        # Add label if enabled
        if show_labels and layers.get("annotations", True):
            buffer.write(f'''
            <text x="{coords["x"] + 5}" y="{coords["y"] + 15}"
                  class="component-label" data-designator="{d}">
                {d}
            </text>
            ''')

    # Add connections if enabled
    if show_connections and layers.get("connections", True):
        # This is a placeholder for actual connection logic
        # In a real implementation, you would process connection data here
        pass

    # Close SVG
    buffer.write('''
        </g>
    </svg>''')

    return buffer.getvalue()
