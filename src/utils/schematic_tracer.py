"""
SchematicTracer - Trace path visualization for schematic viewer with signal flow.

Provides trace routing, visualization, animation, and database storage for
signal paths between schematic components.

Usage:
    TracePath, TraceRouter, TraceManager are exported from this module

    # Create trace paths
    trace = TracePath(
        trace_id="T001",
        start_component="R101",
        end_component="C203",
        signal_type=SignalType.SIGNAL
    )

    # Route trace between components
    router = TraceRouter(grid_size=10)
    path_points = router.route_between(start_component, end_component, obstacles)
    trace.set_path_points(path_points)

    # Manage traces with database storage
    manager = TraceManager(db_path="traces.db")
    manager.add_trace(trace)
    manager.save_to_database()

    # Generate SVG visualization
    svg_elements = manager.generate_svg_traces()

    # Link to interactive hotspots
    manager.link_to_hotspots(hotspot_manager, highlight_on_click=True)

Database Schema:
    traces (
        id VARCHAR PRIMARY KEY,
        start_component VARCHAR,
        end_component VARCHAR,
        path_points JSON,
        signal_type VARCHAR,
        metadata JSON,
        created_at TIMESTAMP
    )
"""

import heapq
import json
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of signals for color coding and categorization."""

    POWER = "power"
    SIGNAL = "signal"
    GROUND = "ground"
    CLOCK = "clock"
    DATA = "data"
    ANALOG = "analog"

    @property
    def color(self) -> str:
        """Get the color associated with this signal type."""
        colors = {
            SignalType.POWER: "#ef4444",  # Red
            SignalType.SIGNAL: "#3b82f6",  # Blue
            SignalType.GROUND: "#1f2937",  # Black/Dark gray
            SignalType.CLOCK: "#f59e0b",  # Amber
            SignalType.DATA: "#10b981",  # Emerald
            SignalType.ANALOG: "#8b5cf6",  # Violet
        }
        return colors.get(self, "#6b7280")

    @property
    def stroke_width(self) -> float:
        """Get the stroke width for this signal type."""
        widths = {
            SignalType.POWER: 4.0,
            SignalType.SIGNAL: 2.5,
            SignalType.GROUND: 3.0,
            SignalType.CLOCK: 2.5,
            SignalType.DATA: 2.0,
            SignalType.ANALOG: 2.5,
        }
        return widths.get(self, 2.5)


class TraceStyle(Enum):
    """Visual styles for trace rendering."""

    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
    ANIMATED = "animated"


@dataclass
class TracePath:
    """
    Represents a trace path between two components.

    Attributes:
        trace_id: Unique identifier for the trace
        start_component: Designator of the starting component
        end_component: Designator of the ending component
        path_points: List of (x, y) coordinate tuples forming the path
        signal_type: Type of signal (power, signal, ground, etc.)
        style: Visual style for rendering
        metadata: Additional trace data (name, layer, width, etc.)
        selected: Current selection state
        visible: Whether the trace is visible
        animated: Whether to show signal flow animation
    """

    trace_id: str
    start_component: str
    end_component: str
    path_points: list[tuple[float, float]] = field(default_factory=list)
    signal_type: SignalType = SignalType.SIGNAL
    style: TraceStyle = TraceStyle.ANIMATED
    metadata: dict[str, Any] = field(default_factory=dict)
    selected: bool = False
    visible: bool = True
    animated: bool = True
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Initialize default metadata if not provided."""
        if not self.metadata:
            self.metadata = {
                "name": f"Trace {self.trace_id}",
                "layer": "top",
                "width": self.signal_type.stroke_width,
            }

    def set_path_points(self, points: list[tuple[float, float]]) -> "TracePath":
        """Set the path points for this trace."""
        self.path_points = points
        return self

    def add_point(self, x: float, y: float) -> "TracePath":
        """Add a point to the path."""
        self.path_points.append((x, y))
        return self

    def get_length(self) -> float:
        """Calculate the total length of the trace path."""
        if len(self.path_points) < 2:
            return 0.0

        length = 0.0
        for i in range(1, len(self.path_points)):
            x1, y1 = self.path_points[i - 1]
            x2, y2 = self.path_points[i]
            length += math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        return length

    def get_direction_at_point(self, index: int) -> tuple[float, float]:
        """Get the direction vector at a specific point index."""
        if len(self.path_points) < 2 or index >= len(self.path_points):
            return (0.0, 0.0)

        if index == 0:
            x1, y1 = self.path_points[0]
            x2, y2 = self.path_points[1]
        elif index == len(self.path_points) - 1:
            x1, y1 = self.path_points[-2]
            x2, y2 = self.path_points[-1]
        else:
            x1, y1 = self.path_points[index - 1]
            x2, y2 = self.path_points[index + 1]

        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx**2 + dy**2)

        if length > 0:
            return (dx / length, dy / length)
        return (0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        """Convert trace to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "start_component": self.start_component,
            "end_component": self.end_component,
            "path_points": self.path_points,
            "signal_type": self.signal_type.value,
            "style": self.style.value,
            "metadata": self.metadata,
            "selected": self.selected,
            "visible": self.visible,
            "animated": self.animated,
            "created_at": self.created_at.isoformat(),
            "length": self.get_length(),
        }

    def to_svg_path_data(self) -> str:
        """Generate SVG path data string from path points."""
        if len(self.path_points) < 2:
            return ""

        # Start with move command
        path_data = f"M {self.path_points[0][0]} {self.path_points[0][1]}"

        # Add line commands for each subsequent point
        for point in self.path_points[1:]:
            path_data += f" L {point[0]} {point[1]}"

        return path_data

    def to_svg_element(self, include_animation: bool = True) -> dict[str, Any]:
        """Generate SVG element dictionary for this trace."""
        if len(self.path_points) < 2:
            return {}

        element = {
            "type": "path",
            "attributes": {
                "id": f"trace-{self.trace_id}",
                "class": f"trace-path trace-{self.signal_type.value}",
                "d": self.to_svg_path_data(),
                "stroke": self.signal_type.color,
                "stroke-width": self.signal_type.stroke_width,
                "fill": "none",
                "stroke-linecap": "round",
                "stroke-linejoin": "round",
                "data-trace-id": self.trace_id,
                "data-start-component": self.start_component,
                "data-end-component": self.end_component,
                "data-signal-type": self.signal_type.value,
            },
        }

        # Add style-specific attributes
        if self.style == TraceStyle.DASHED:
            element["attributes"]["stroke-dasharray"] = "10,5"
        elif self.style == TraceStyle.DOTTED:
            element["attributes"]["stroke-dasharray"] = "2,4"
        elif self.style == TraceStyle.ANIMATED and self.animated and include_animation:
            element["attributes"]["stroke-dasharray"] = "10,5"
            element["attributes"]["class"] += " trace-animated"

        if not self.visible:
            element["attributes"]["display"] = "none"

        if self.selected:
            element["attributes"]["class"] += " trace-selected"
            element["attributes"]["stroke-width"] = str(self.signal_type.stroke_width + 2)

        return element

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TracePath":
        """Create TracePath from dictionary."""
        return cls(
            trace_id=data["trace_id"],
            start_component=data["start_component"],
            end_component=data["end_component"],
            path_points=[tuple(p) for p in data.get("path_points", [])],
            signal_type=SignalType(data.get("signal_type", "signal")),
            style=TraceStyle(data.get("style", "animated")),
            metadata=data.get("metadata", {}),
            selected=data.get("selected", False),
            visible=data.get("visible", True),
            animated=data.get("animated", True),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat()))
            if "created_at" in data
            else datetime.now(),
        )


@dataclass
class ComponentBounds:
    """Represents component boundaries for obstacle avoidance."""

    designator: str
    x: float
    y: float
    width: float
    height: float

    def contains_point(self, x: float, y: float, margin: float = 5.0) -> bool:
        """Check if a point is within the component bounds (with margin)."""
        half_w = self.width / 2 + margin
        half_h = self.height / 2 + margin
        return self.x - half_w <= x <= self.x + half_w and self.y - half_h <= y <= self.y + half_h

    def to_rect(self) -> tuple[float, float, float, float]:
        """Get rectangle as (x1, y1, x2, y2)."""
        half_w = self.width / 2
        half_h = self.height / 2
        return (self.x - half_w, self.y - half_h, self.x + half_w, self.y + half_h)


class TraceRouter:
    """
    Routes traces between components avoiding obstacles.

    Implements A* pathfinding algorithm for efficient trace routing
    with support for orthogonal (Manhattan) routing.

    Features:
    - A* pathfinding for optimal routes
    - Obstacle avoidance with component bounds
    - Orthogonal routing preference (horizontal/vertical lines)
    - Configurable grid size and margin
    """

    def __init__(self, grid_size: float = 10.0, margin: float = 10.0):
        """
        Initialize the trace router.

        Args:
            grid_size: Grid size for pathfinding (smaller = more precise but slower)
            margin: Minimum distance to maintain from obstacles
        """
        self.grid_size = grid_size
        self.margin = margin
        self.obstacles: list[ComponentBounds] = []

    def add_obstacle(self, component: ComponentBounds) -> "TraceRouter":
        """Add a component as an obstacle to avoid."""
        self.obstacles.append(component)
        return self

    def clear_obstacles(self) -> "TraceRouter":
        """Clear all obstacles."""
        self.obstacles.clear()
        return self

    def is_point_valid(
        self,
        x: float,
        y: float,
        start_component: ComponentBounds | None = None,
        end_component: ComponentBounds | None = None,
    ) -> bool:
        """Check if a point is valid (not inside an obstacle)."""
        for obstacle in self.obstacles:
            # Allow points inside start/end components
            if start_component and obstacle.designator == start_component.designator:
                continue
            if end_component and obstacle.designator == end_component.designator:
                continue

            if obstacle.contains_point(x, y, self.margin):
                return False
        return True

    def route_between(
        self,
        start: ComponentBounds | tuple[float, float],
        end: ComponentBounds | tuple[float, float],
        orthogonal: bool = True,
    ) -> list[tuple[float, float]]:
        """
        Calculate a route between two points/components.

        Args:
            start: Starting component or (x, y) coordinates
            end: Ending component or (x, y) coordinates
            orthogonal: Prefer orthogonal (horizontal/vertical) routing

        Returns:
            List of (x, y) coordinate tuples forming the path
        """
        # Extract coordinates
        if isinstance(start, ComponentBounds):
            start_pos = (start.x, start.y)
            start_component = start
        else:
            start_pos = start
            start_component = None

        if isinstance(end, ComponentBounds):
            end_pos = (end.x, end.y)
            end_component = end
        else:
            end_pos = end
            end_component = None

        # If orthogonal routing requested, use manhattan route
        if orthogonal:
            return self._manhattan_route(start_pos, end_pos, start_component, end_component)

        # Otherwise use A* for direct path
        return self._astar_route(start_pos, end_pos, start_component, end_component)

    def _manhattan_route(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        start_component: ComponentBounds | None = None,
        end_component: ComponentBounds | None = None,
    ) -> list[tuple[float, float]]:
        """
        Create a Manhattan (L-shaped) route with obstacle avoidance.

        Tries both horizontal-first and vertical-first routes,
        selecting the one that avoids obstacles or has shorter length.
        """
        x1, y1 = start
        x2, y2 = end

        # Try horizontal-first route: (x1,y1) -> (x2,y1) -> (x2,y2)
        route_h_first = [(x1, y1), (x2, y1), (x2, y2)]
        h_first_valid = all(
            self.is_point_valid(p[0], p[1], start_component, end_component) for p in route_h_first
        )

        # Try vertical-first route: (x1,y1) -> (x1,y2) -> (x2,y2)
        route_v_first = [(x1, y1), (x1, y2), (x2, y2)]
        v_first_valid = all(
            self.is_point_valid(p[0], p[1], start_component, end_component) for p in route_v_first
        )

        # Select best route
        if h_first_valid and v_first_valid:
            # Both valid, choose shorter one
            abs(x2 - x1) + abs(y2 - y1)
            abs(x2 - x1) + abs(y2 - y1)  # Same for Manhattan
            # Prefer horizontal-first by default
            return route_h_first
        elif h_first_valid:
            return route_h_first
        elif v_first_valid:
            return route_v_first
        else:
            # Neither simple route works, try A*
            return self._astar_route(start, end, start_component, end_component)

    def _astar_route(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        start_component: ComponentBounds | None = None,
        end_component: ComponentBounds | None = None,
    ) -> list[tuple[float, float]]:
        """
        A* pathfinding algorithm for trace routing.

        Uses grid-based pathfinding with diagonal movement disabled
        for orthogonal trace preference.
        """

        # Snap to grid
        def snap_to_grid(x: float, y: float) -> tuple[int, int]:
            return (round(x / self.grid_size), round(y / self.grid_size))

        start_grid = snap_to_grid(start[0], start[1])
        end_grid = snap_to_grid(end[0], end[1])

        if start_grid == end_grid:
            return [start, end]

        # A* implementation
        def heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
            return abs(a[0] - b[0]) + abs(a[1] - b[1])  # Manhattan distance

        # Priority queue: (f_score, counter, position)
        counter = 0
        open_set = [(heuristic(start_grid, end_grid), counter, start_grid)]
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        g_score: dict[tuple[int, int], float] = {start_grid: 0}
        f_score: dict[tuple[int, int], float] = {start_grid: heuristic(start_grid, end_grid)}

        while open_set:
            _, _, current = heapq.heappop(open_set)

            if current == end_grid:
                # Reconstruct path
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start_grid)
                path.reverse()

                # Convert back to world coordinates
                world_path = [(p[0] * self.grid_size, p[1] * self.grid_size) for p in path]

                # Add end point if not already included
                if world_path[-1] != end:
                    world_path.append(end)

                return self._simplify_path(world_path)

            # Check neighbors (4-directional for orthogonal traces)
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                neighbor = (current[0] + dx, current[1] + dy)
                neighbor_world = (neighbor[0] * self.grid_size, neighbor[1] * self.grid_size)

                if not self.is_point_valid(
                    neighbor_world[0], neighbor_world[1], start_component, end_component
                ):
                    continue

                tentative_g = g_score[current] + 1

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + heuristic(neighbor, end_grid)
                    counter += 1
                    heapq.heappush(open_set, (f_score[neighbor], counter, neighbor))

        # No path found, return direct line
        return [start, end]

    def _simplify_path(self, path: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Simplify path by removing unnecessary intermediate points."""
        if len(path) <= 2:
            return path

        simplified = [path[0]]

        for i in range(1, len(path) - 1):
            prev = simplified[-1]
            curr = path[i]
            next_p = path[i + 1]

            # Check if current point is collinear with prev and next
            # (same x or same y for orthogonal routing)
            if not (
                (abs(prev[0] - curr[0]) < 0.01 and abs(curr[0] - next_p[0]) < 0.01)
                or (abs(prev[1] - curr[1]) < 0.01 and abs(curr[1] - next_p[1]) < 0.01)
            ):
                simplified.append(curr)

        simplified.append(path[-1])
        return simplified

    def route_multi_point(
        self, points: list[tuple[float, float]], orthogonal: bool = True
    ) -> list[tuple[float, float]]:
        """
        Route through multiple points (for net routing).

        Args:
            points: List of (x, y) coordinates to route through
            orthogonal: Use orthogonal routing

        Returns:
            Combined path through all points
        """
        if len(points) < 2:
            return points

        full_path = []
        for i in range(len(points) - 1):
            segment = self.route_between(points[i], points[i + 1], orthogonal)
            if i > 0:
                # Remove duplicate point at segment boundary
                segment = segment[1:]
            full_path.extend(segment)

        return full_path


class TraceManager:
    """
    Manages multiple trace paths with database integration.

    Features:
    - Add/remove traces
    - Highlight traces on component selection
    - Generate SVG elements for all traces
    - Store/retrieve traces from DuckDB
    - Link to interactive hotspots
    """

    def __init__(self, db_path: str | None = None):
        """
        Initialize the trace manager.

        Args:
            db_path: Path to DuckDB database (None for in-memory only)
        """
        self._traces: dict[str, TracePath] = {}
        self._traces_by_component: dict[str, set[str]] = {}  # component -> trace_ids
        self.db_path = db_path
        self.router = TraceRouter()
        self._highlight_callbacks: list[Callable] = []

        if db_path:
            self._init_database()

    def _init_database(self):
        """Initialize database schema."""
        try:
            import duckdb

            conn = duckdb.connect(self.db_path)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    id VARCHAR PRIMARY KEY,
                    start_component VARCHAR,
                    end_component VARCHAR,
                    path_points JSON,
                    signal_type VARCHAR,
                    style VARCHAR,
                    metadata JSON,
                    selected BOOLEAN DEFAULT FALSE,
                    visible BOOLEAN DEFAULT TRUE,
                    animated BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for component lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_start_component
                ON traces(start_component)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_end_component
                ON traces(end_component)
            """)

            conn.close()
        except ImportError:
            logger.warning("duckdb not installed, database features disabled")

    def add_trace(self, trace: TracePath) -> "TraceManager":
        """Add a trace to the manager."""
        self._traces[trace.trace_id] = trace

        # Update component index
        for component in [trace.start_component, trace.end_component]:
            if component not in self._traces_by_component:
                self._traces_by_component[component] = set()
            self._traces_by_component[component].add(trace.trace_id)

        return self

    def remove_trace(self, trace_id: str) -> "TraceManager":
        """Remove a trace by ID."""
        if trace_id in self._traces:
            trace = self._traces[trace_id]

            # Remove from component index
            for component in [trace.start_component, trace.end_component]:
                if component in self._traces_by_component:
                    self._traces_by_component[component].discard(trace_id)

            del self._traces[trace_id]

        return self

    def get_trace(self, trace_id: str) -> TracePath | None:
        """Get a trace by ID."""
        return self._traces.get(trace_id)

    def get_traces_for_component(self, designator: str) -> list[TracePath]:
        """Get all traces connected to a component."""
        trace_ids = self._traces_by_component.get(designator, set())
        return [self._traces[tid] for tid in trace_ids if tid in self._traces]

    def get_all_traces(self) -> list[TracePath]:
        """Get all traces."""
        return list(self._traces.values())

    def select_trace(self, trace_id: str) -> "TraceManager":
        """Select a trace."""
        if trace_id in self._traces:
            self._traces[trace_id].selected = True
        return self

    def deselect_trace(self, trace_id: str) -> "TraceManager":
        """Deselect a trace."""
        if trace_id in self._traces:
            self._traces[trace_id].selected = False
        return self

    def deselect_all(self) -> "TraceManager":
        """Deselect all traces."""
        for trace in self._traces.values():
            trace.selected = False
        return self

    def highlight_component_traces(self, designator: str) -> list[TracePath]:
        """
        Highlight all traces connected to a component.

        Returns:
            List of highlighted traces
        """
        self.deselect_all()
        traces = self.get_traces_for_component(designator)

        for trace in traces:
            trace.selected = True

        # Trigger callbacks
        for callback in self._highlight_callbacks:
            try:
                callback(designator, traces)
            except Exception as e:
                print(f"Error in highlight callback: {e}")

        return traces

    def on_highlight(self, callback: Callable[[str, list[TracePath]], None]) -> "TraceManager":
        """Register a callback for trace highlighting."""
        self._highlight_callbacks.append(callback)
        return self

    def generate_svg_traces(self, include_animation: bool = True) -> list[dict[str, Any]]:
        """Generate SVG elements for all traces."""
        elements = []
        for trace in self._traces.values():
            if trace.visible:
                element = trace.to_svg_element(include_animation)
                if element:
                    elements.append(element)
        return elements

    def generate_svg_animation_css(self) -> str:
        """Generate CSS for trace animations."""
        return """
/* Trace Path Animations */

.trace-path {
    fill: none;
    pointer-events: stroke;
    cursor: pointer;
    transition: stroke-width 0.2s ease, stroke-opacity 0.2s ease;
}

.trace-path:hover {
    stroke-opacity: 1;
    filter: drop-shadow(0 0 4px currentColor);
}

.trace-selected {
    filter: drop-shadow(0 0 8px currentColor);
    animation: tracePulse 1s ease-in-out infinite;
}

/* Signal Flow Animation */
.trace-animated {
    animation: signalFlow 2s linear infinite;
}

@keyframes signalFlow {
    0% {
        stroke-dashoffset: 20;
    }
    100% {
        stroke-dashoffset: 0;
    }
}

@keyframes tracePulse {
    0%, 100% {
        stroke-width: var(--base-width, 2.5);
        opacity: 1;
    }
    50% {
        stroke-width: calc(var(--base-width, 2.5) + 2);
        opacity: 0.8;
    }
}

/* Signal Type Colors */
.trace-power {
    --trace-color: #ef4444;
    --base-width: 4;
}

.trace-signal {
    --trace-color: #3b82f6;
    --base-width: 2.5;
}

.trace-ground {
    --trace-color: #1f2937;
    --base-width: 3;
}

.trace-clock {
    --trace-color: #f59e0b;
    --base-width: 2.5;
}

.trace-data {
    --trace-color: #10b981;
    --base-width: 2;
}

.trace-analog {
    --trace-color: #8b5cf6;
    --base-width: 2.5;
}

/* Trace Labels */
.trace-label {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 10px;
    fill: #666;
    pointer-events: none;
}

/* Connection Points */
.trace-connection-point {
    fill: var(--trace-color, #666);
    stroke: #fff;
    stroke-width: 1;
    r: 3;
}
"""

    def generate_svg_markers(self) -> list[dict[str, Any]]:
        """Generate SVG marker definitions for trace endpoints."""
        markers = []

        for signal_type in SignalType:
            # Arrow marker for signal direction
            marker = {
                "type": "marker",
                "attributes": {
                    "id": f"arrow-{signal_type.value}",
                    "markerWidth": "10",
                    "markerHeight": "10",
                    "refX": "9",
                    "refY": "3",
                    "orient": "auto",
                    "markerUnits": "strokeWidth",
                },
                "children": [
                    {
                        "type": "path",
                        "attributes": {
                            "d": "M0,0 L0,6 L9,3 z",
                            "fill": signal_type.color,
                        },
                    }
                ],
            }
            markers.append(marker)

            # Dot marker for connection points
            dot_marker = {
                "type": "marker",
                "attributes": {
                    "id": f"dot-{signal_type.value}",
                    "markerWidth": "6",
                    "markerHeight": "6",
                    "refX": "3",
                    "refY": "3",
                },
                "children": [
                    {
                        "type": "circle",
                        "attributes": {
                            "cx": "3",
                            "cy": "3",
                            "r": "2",
                            "fill": signal_type.color,
                        },
                    }
                ],
            }
            markers.append(dot_marker)

        return markers

    def link_to_hotspots(self, hotspot_manager, highlight_on_click: bool = True) -> "TraceManager":
        """
        Link traces to interactive hotspots.

        Args:
            hotspot_manager: HotspotManager instance
            highlight_on_click: Highlight traces when component is clicked
        """
        if highlight_on_click:

            def on_hotspot_select(hotspot, is_selected):
                if is_selected:
                    self.highlight_component_traces(hotspot.designator)
                else:
                    self.deselect_all()

            # Register with hotspot manager if it has the method
            if hasattr(hotspot_manager, "on_event"):
                from src.utils.schematic_interactive import HotspotEvent

                hotspot_manager.on_event(HotspotEvent.SELECT, lambda h: on_hotspot_select(h, True))
                hotspot_manager.on_event(
                    HotspotEvent.DESELECT, lambda h: on_hotspot_select(h, False)
                )

        return self

    def save_to_database(self) -> "TraceManager":
        """Save all traces to database."""
        if not self.db_path:
            logger.warning("No database path configured")
            return self

        try:
            import duckdb

            conn = duckdb.connect(self.db_path)

            for trace in self._traces.values():
                conn.execute(
                    """
                    INSERT OR REPLACE INTO traces
                    (id, start_component, end_component, path_points, signal_type,
                     style, metadata, selected, visible, animated, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        trace.trace_id,
                        trace.start_component,
                        trace.end_component,
                        json.dumps(trace.path_points),
                        trace.signal_type.value,
                        trace.style.value,
                        json.dumps(trace.metadata),
                        trace.selected,
                        trace.visible,
                        trace.animated,
                        trace.created_at,
                    ),
                )

            conn.close()
            logger.info(f"Saved {len(self._traces)} traces to database")

        except ImportError:
            logger.warning("duckdb not installed")
        except Exception as e:
            logger.error(f"Error saving to database: {e}")

        return self

    def load_from_database(self) -> "TraceManager":
        """Load traces from database."""
        if not self.db_path:
            logger.warning("No database path configured")
            return self

        try:
            import duckdb

            conn = duckdb.connect(self.db_path)

            result = conn.execute("SELECT * FROM traces").fetchall()

            for row in result:
                trace = TracePath(
                    trace_id=row[0],
                    start_component=row[1],
                    end_component=row[2],
                    path_points=json.loads(row[3]),
                    signal_type=SignalType(row[4]),
                    style=TraceStyle(row[5]),
                    metadata=json.loads(row[6]),
                    selected=row[7],
                    visible=row[8],
                    animated=row[9],
                    created_at=row[10],
                )
                self.add_trace(trace)

            conn.close()
            logger.info(f"Loaded {len(result)} traces from database")

        except ImportError:
            logger.warning("duckdb not installed")
        except Exception as e:
            logger.error(f"Error loading from database: {e}")

        return self

    def to_json(self) -> str:
        """Export all traces to JSON string."""
        data = {
            "traces": [t.to_dict() for t in self._traces.values()],
            "total_count": len(self._traces),
            "by_signal_type": {},
        }

        # Count by signal type
        for signal_type in SignalType:
            count = sum(1 for t in self._traces.values() if t.signal_type == signal_type)
            if count > 0:
                data["by_signal_type"][signal_type.value] = count

        return json.dumps(data, indent=2)

    def export_to_file(self, output_path: str) -> str:
        """Export traces to JSON file."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        json_data = self.to_json()
        path.write_text(json_data, encoding="utf-8")

        return str(path)

    def clear(self) -> "TraceManager":
        """Clear all traces."""
        self._traces.clear()
        self._traces_by_component.clear()
        return self


# Convenience functions for integration with schematic_overlay.py
def create_trace_svg_group(
    traces: list[TracePath], include_markers: bool = True, include_animation: bool = True
) -> str:
    """
    Create SVG group element containing all traces.

    Args:
        traces: List of TracePath objects
        include_markers: Include marker definitions
        include_animation: Include animation CSS

    Returns:
        SVG group element string
    """
    svg_parts = ['<g class="trace-layer">']

    # Add defs if needed
    if include_markers and traces:
        manager = TraceManager()
        for trace in traces:
            manager.add_trace(trace)

        markers = manager.generate_svg_markers()
        if markers:
            svg_parts.append("<defs>")
            for marker in markers:
                attrs = " ".join(f'{k}="{v}"' for k, v in marker["attributes"].items())
                svg_parts.append(f"  <marker {attrs}>")
                for child in marker.get("children", []):
                    child_attrs = " ".join(f'{k}="{v}"' for k, v in child["attributes"].items())
                    svg_parts.append(f"    <{child['type']} {child_attrs}/>")
                svg_parts.append("  </marker>")
            svg_parts.append("</defs>")

    # Add traces
    for trace in traces:
        element = trace.to_svg_element(include_animation)
        if element:
            attrs = " ".join(f'{k}="{v}"' for k, v in element["attributes"].items())
            svg_parts.append(f"  <{element['type']} {attrs}/>")

    svg_parts.append("</g>")

    return "\n".join(svg_parts)


def integrate_with_overlay(overlay_generator, trace_manager: TraceManager):
    """
    Integrate TraceManager with SchematicOverlayGenerator.

    Args:
        overlay_generator: SchematicOverlayGenerator instance
        trace_manager: TraceManager instance
    """
    # Add all trace paths to the overlay
    for trace in trace_manager.get_all_traces():
        if trace.path_points:
            overlay_generator.add_trace_path(trace.path_points)


# Example usage and testing
def example():
    """Example demonstrating TracePath, TraceRouter, and TraceManager usage."""

    print("=" * 60)
    print("Schematic Tracer Example")
    print("=" * 60)

    # Create some example components
    components = {
        "R101": ComponentBounds("R101", 100, 150, 20, 20),
        "C203": ComponentBounds("C203", 300, 150, 20, 20),
        "U1": ComponentBounds("U1", 200, 250, 40, 30),
        "L501": ComponentBounds("L501", 400, 250, 20, 20),
        "GND1": ComponentBounds("GND1", 200, 400, 20, 10),
    }

    # Create router with obstacles
    router = TraceRouter(grid_size=10, margin=15)
    for comp in components.values():
        router.add_obstacle(comp)

    print("\n1. Creating Trace Paths")
    print("-" * 40)

    # Create trace manager
    manager = TraceManager()

    # Route signal trace R101 -> C203
    path1 = router.route_between(components["R101"], components["C203"])
    trace1 = TracePath(
        trace_id="T001",
        start_component="R101",
        end_component="C203",
        signal_type=SignalType.SIGNAL,
        path_points=path1,
        metadata={"name": "Signal path R101-C203", "net": "NET_1"},
    )
    manager.add_trace(trace1)
    print(f"Created trace {trace1.trace_id}: {trace1.start_component} -> {trace1.end_component}")
    print(f"  Length: {trace1.get_length():.1f} px, Points: {len(trace1.path_points)}")

    # Route power trace to U1
    path2 = router.route_between(components["R101"], components["U1"])
    trace2 = TracePath(
        trace_id="T002",
        start_component="R101",
        end_component="U1",
        signal_type=SignalType.POWER,
        path_points=path2,
        metadata={"name": "Power to U1", "voltage": "3.3V"},
    )
    manager.add_trace(trace2)
    print(f"Created trace {trace2.trace_id}: {trace2.start_component} -> {trace2.end_component}")
    print(f"  Length: {trace2.get_length():.1f} px, Type: {trace2.signal_type.value}")

    # Route ground trace
    path3 = router.route_between(components["U1"], components["GND1"])
    trace3 = TracePath(
        trace_id="T003",
        start_component="U1",
        end_component="GND1",
        signal_type=SignalType.GROUND,
        path_points=path3,
        metadata={"name": "Ground connection"},
    )
    manager.add_trace(trace3)
    print(f"Created trace {trace3.trace_id}: {trace3.start_component} -> {trace3.end_component}")
    print(f"  Length: {trace3.get_length():.1f} px, Type: {trace3.signal_type.value}")

    # Route clock trace
    path4 = router.route_between(components["U1"], components["L501"])
    trace4 = TracePath(
        trace_id="T004",
        start_component="U1",
        end_component="L501",
        signal_type=SignalType.CLOCK,
        path_points=path4,
        style=TraceStyle.ANIMATED,
        metadata={"name": "Clock signal", "frequency": "16MHz"},
    )
    manager.add_trace(trace4)
    print(f"Created trace {trace4.trace_id}: {trace4.start_component} -> {trace4.end_component}")
    print(f"  Length: {trace4.get_length():.1f} px, Type: {trace4.signal_type.value}")

    print("\n2. Trace Statistics")
    print("-" * 40)
    print(f"Total traces: {len(manager.get_all_traces())}")
    print(f"Traces connected to U1: {len(manager.get_traces_for_component('U1'))}")

    total_length = sum(t.get_length() for t in manager.get_all_traces())
    print(f"Total trace length: {total_length:.1f} px")

    print("\n3. Component Highlighting")
    print("-" * 40)
    highlighted = manager.highlight_component_traces("U1")
    print(f"Highlighted {len(highlighted)} traces connected to U1:")
    for t in highlighted:
        print(f"  - {t.trace_id} ({t.signal_type.value})")

    print("\n4. SVG Generation")
    print("-" * 40)
    svg_elements = manager.generate_svg_traces()
    print(f"Generated {len(svg_elements)} SVG path elements")

    # Show example SVG
    if svg_elements:
        example = svg_elements[0]
        print(f"\nExample SVG element ({example['attributes']['id']}):")
        print(f"  Path: {example['attributes']['d'][:50]}...")
        print(f"  Color: {example['attributes']['stroke']}")
        print(f"  Width: {example['attributes']['stroke-width']}")

    print("\n5. CSS Animation")
    print("-" * 40)
    print(manager.generate_svg_animation_css()[:500] + "...")

    print("\n6. Database Schema")
    print("-" * 40)
    print("""
    CREATE TABLE traces (
        id VARCHAR PRIMARY KEY,
        start_component VARCHAR,
        end_component VARCHAR,
        path_points JSON,          -- Array of [x, y] coordinates
        signal_type VARCHAR,       -- power|signal|ground|clock|data|analog
        style VARCHAR,             -- solid|dashed|dotted|animated
        metadata JSON,             -- Additional trace properties
        selected BOOLEAN,          -- Highlight state
        visible BOOLEAN,           -- Visibility state
        animated BOOLEAN,          -- Animation enabled
        created_at TIMESTAMP       -- Creation timestamp
    );

    -- Indexes for efficient lookups
    CREATE INDEX idx_start_component ON traces(start_component);
    CREATE INDEX idx_end_component ON traces(end_component);
    """)

    print("\n7. JSON Export")
    print("-" * 40)
    print(manager.to_json()[:800] + "...")

    return manager


if __name__ == "__main__":
    example()
