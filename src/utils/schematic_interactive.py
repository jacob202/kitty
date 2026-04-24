"""
SchematicInteractive - Interactive component hotspot functionality for schematic viewer.

Provides clickable hotspots, tooltips, event handling, and JavaScript generation
for frontend integration with the schematic overlay system.

Usage:
    ComponentHotspot, HotspotManager are exported from this module

    # Create hotspots for components
    manager = HotspotManager()

    for component in components:
        hotspot = ComponentHotspot(
            designator=component.designator,
            component_type=component.type,
            x=component.x,
            y=component.y,
            metadata={"value": "10k", "package": "0805"}
        )
        hotspot.add_tooltip(f"{component.designator}: {component.type}")
        manager.add_hotspot(hotspot)

    # Generate JavaScript for frontend
    js_code = manager.generate_js_handlers()

    # Export to JSON for frontend frameworks
    json_data = manager.to_json()
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class HotspotEvent(Enum):
    """Event types for hotspot interactions."""

    CLICK = "click"
    HOVER = "hover"
    SELECT = "select"
    DESELECT = "deselect"
    DOUBLE_CLICK = "dblclick"
    CONTEXT_MENU = "contextmenu"


@dataclass
class TooltipConfig:
    """Configuration for hotspot tooltips."""

    content: str = ""
    position: str = "top"  # top, bottom, left, right
    delay: int = 200  # ms delay before showing
    duration: int | None = None  # ms before auto-hiding (None = persistent on hover)
    css_class: str = "schematic-tooltip"
    show_on_hover: bool = True
    show_on_click: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "content": self.content,
            "position": self.position,
            "delay": self.delay,
            "duration": self.duration,
            "cssClass": self.css_class,
            "showOnHover": self.show_on_hover,
            "showOnClick": self.show_on_click,
        }


@dataclass
class ComponentHotspot:
    """
    Represents an interactive hotspot for a schematic component.

    Attributes:
        designator: Component designator (e.g., "R101")
        component_type: Component type (e.g., "Resistor")
        x: X coordinate in schematic
        y: Y coordinate in schematic
        width: Hotspot width (default: 20)
        height: Hotspot height (default: 20)
        metadata: Additional component data (value, package, etc.)
        tooltip: Tooltip configuration
        selected: Current selection state
        enabled: Whether hotspot is interactive
    """

    designator: str
    component_type: str
    x: float
    y: float
    width: float = 20.0
    height: float = 20.0
    metadata: dict[str, Any] = field(default_factory=dict)
    tooltip: TooltipConfig = field(default_factory=TooltipConfig)
    selected: bool = False
    enabled: bool = True

    # Event handlers (stored as callable references)
    _on_click: Callable[["ComponentHotspot"], None] | None = field(default=None, repr=False)
    _on_hover: Callable[["ComponentHotspot", bool], None] | None = field(
        default=None, repr=False
    )
    _on_select: Callable[["ComponentHotspot", bool], None] | None = field(
        default=None, repr=False
    )

    def __post_init__(self):
        """Initialize default tooltip if not provided."""
        if not self.tooltip.content:
            self.tooltip.content = f"{self.designator} ({self.component_type})"

    def add_tooltip(self, content: str, position: str = "top", **kwargs) -> "ComponentHotspot":
        """
        Add or update tooltip content.

        Args:
            content: Tooltip text/HTML content
            position: Tooltip position (top, bottom, left, right)
            **kwargs: Additional tooltip options (delay, duration, etc.)

        Returns:
            Self for method chaining
        """
        self.tooltip.content = content
        self.tooltip.position = position
        for key, value in kwargs.items():
            if hasattr(self.tooltip, key):
                setattr(self.tooltip, key, value)
        return self

    def on_click(self, callback: Callable[["ComponentHotspot"], None]) -> "ComponentHotspot":
        """
        Register click handler.

        Args:
            callback: Function to call when hotspot is clicked

        Returns:
            Self for method chaining
        """
        self._on_click = callback
        return self

    def on_hover(self, callback: Callable[["ComponentHotspot", bool], None]) -> "ComponentHotspot":
        """
        Register hover handler.

        Args:
            callback: Function to call when hover state changes (hotspot, is_hovering)

        Returns:
            Self for method chaining
        """
        self._on_hover = callback
        return self

    def on_select(self, callback: Callable[["ComponentHotspot", bool], None]) -> "ComponentHotspot":
        """
        Register selection handler.

        Args:
            callback: Function to call when selection state changes (hotspot, is_selected)

        Returns:
            Self for method chaining
        """
        self._on_select = callback
        return self

    def select(self) -> "ComponentHotspot":
        """Select this hotspot and trigger callback."""
        self.selected = True
        if self._on_select:
            self._on_select(self, True)
        return self

    def deselect(self) -> "ComponentHotspot":
        """Deselect this hotspot and trigger callback."""
        self.selected = False
        if self._on_select:
            self._on_select(self, False)
        return self

    def toggle_selection(self) -> "ComponentHotspot":
        """Toggle selection state."""
        if self.selected:
            self.deselect()
        else:
            self.select()
        return self

    def trigger_click(self) -> "ComponentHotspot":
        """Trigger click event manually."""
        if self.enabled and self._on_click:
            self._on_click(self)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert hotspot to dictionary for JSON export."""
        return {
            "designator": self.designator,
            "type": self.component_type,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "metadata": self.metadata,
            "tooltip": self.tooltip.to_dict(),
            "selected": self.selected,
            "enabled": self.enabled,
        }

    def get_data_attributes(self) -> dict[str, str]:
        """Generate data attributes for SVG element."""
        attrs = {
            "data-designator": self.designator,
            "data-type": self.component_type,
            "data-x": str(self.x),
            "data-y": str(self.y),
            "data-enabled": str(self.enabled).lower(),
        }

        # Add metadata as data attributes
        for key, value in self.metadata.items():
            attrs[f"data-{key}"] = str(value)

        return attrs

    @classmethod
    def from_component(cls, component, **kwargs) -> "ComponentHotspot":
        """
        Create hotspot from schematic_overlay.Component.

        Args:
            component: Component instance from schematic_overlay
            **kwargs: Additional hotspot attributes

        Returns:
            New ComponentHotspot instance
        """
        return cls(
            designator=component.designator,
            component_type=component.type,
            x=component.x,
            y=component.y,
            width=getattr(component, "width", 20.0),
            height=getattr(component, "height", 20.0),
            **kwargs,
        )


class HotspotManager:
    """
    Manages multiple component hotspots and generates frontend integration code.

    Features:
    - Add/remove hotspots
    - Group management
    - Selection management (single/multi-select)
    - JavaScript generation for frontend
    - JSON export for frontend frameworks
    """

    def __init__(self, allow_multi_select: bool = False):
        """
        Initialize hotspot manager.

        Args:
            allow_multi_select: Allow multiple simultaneous selections
        """
        self._hotspots: dict[str, ComponentHotspot] = {}
        self._selected: set = set()
        self._groups: dict[str, list[str]] = {}
        self._allow_multi_select = allow_multi_select

        # Global event handlers
        self._global_handlers: dict[HotspotEvent, list[Callable]] = {
            event: [] for event in HotspotEvent
        }

    def add_hotspot(
        self, hotspot: ComponentHotspot, group: str | None = None
    ) -> "HotspotManager":
        """
        Add a hotspot to the manager.

        Args:
            hotspot: ComponentHotspot instance
            group: Optional group name for organizing hotspots

        Returns:
            Self for method chaining
        """
        self._hotspots[hotspot.designator] = hotspot

        # Wire up event handlers to emit global events
        hotspot.on_click(self._on_hotspot_click)
        hotspot.on_select(self._on_hotspot_select)

        if group:
            if group not in self._groups:
                self._groups[group] = []
            self._groups[group].append(hotspot.designator)

        return self

    def remove_hotspot(self, designator: str) -> "HotspotManager":
        """
        Remove a hotspot by designator.

        Args:
            designator: Component designator to remove

        Returns:
            Self for method chaining
        """
        if designator in self._hotspots:
            del self._hotspots[designator]
            self._selected.discard(designator)

            # Remove from groups
            for group in self._groups.values():
                if designator in group:
                    group.remove(designator)

        return self

    def get_hotspot(self, designator: str) -> ComponentHotspot | None:
        """Get hotspot by designator."""
        return self._hotspots.get(designator)

    def get_all_hotspots(self) -> list[ComponentHotspot]:
        """Get all hotspots."""
        return list(self._hotspots.values())

    def get_selected(self) -> list[ComponentHotspot]:
        """Get all selected hotspots."""
        return [self._hotspots[d] for d in self._selected if d in self._hotspots]

    def select(self, designator: str) -> "HotspotManager":
        """
        Select a hotspot by designator.

        Args:
            designator: Component designator to select

        Returns:
            Self for method chaining
        """
        if not self._allow_multi_select:
            # Deselect all others
            for d in list(self._selected):
                if d in self._hotspots:
                    self._hotspots[d].deselect()
            self._selected.clear()

        if designator in self._hotspots:
            self._hotspots[designator].select()
            self._selected.add(designator)

        return self

    def deselect(self, designator: str) -> "HotspotManager":
        """Deselect a hotspot."""
        if designator in self._hotspots:
            self._hotspots[designator].deselect()
        self._selected.discard(designator)
        return self

    def deselect_all(self) -> "HotspotManager":
        """Deselect all hotspots."""
        for d in list(self._selected):
            if d in self._hotspots:
                self._hotspots[d].deselect()
        self._selected.clear()
        return self

    def select_group(self, group_name: str) -> "HotspotManager":
        """Select all hotspots in a group."""
        if group_name in self._groups:
            for designator in self._groups[group_name]:
                self.select(designator)
        return self

    def on_event(self, event: HotspotEvent, callback: Callable) -> "HotspotManager":
        """
        Register global event handler.

        Args:
            event: Event type to listen for
            callback: Function to call when event occurs

        Returns:
            Self for method chaining
        """
        self._global_handlers[event].append(callback)
        return self

    def _on_hotspot_click(self, hotspot: ComponentHotspot):
        """Internal handler for hotspot clicks."""
        self._emit_event(HotspotEvent.CLICK, hotspot)

    def _on_hotspot_select(self, hotspot: ComponentHotspot, is_selected: bool):
        """Internal handler for hotspot selection."""
        event = HotspotEvent.SELECT if is_selected else HotspotEvent.DESELECT
        self._emit_event(event, hotspot, is_selected)

    def _emit_event(self, event: HotspotEvent, hotspot: ComponentHotspot, *args):
        """Emit event to all registered handlers."""
        for handler in self._global_handlers[event]:
            try:
                handler(hotspot, *args)
            except Exception as e:
                print(f"Error in event handler for {event.value}: {e}")

    def to_json(self) -> str:
        """
        Export all hotspots to JSON string.

        Returns:
            JSON string with hotspot data
        """
        data = {
            "hotspots": [h.to_dict() for h in self._hotspots.values()],
            "groups": self._groups,
            "config": {
                "multiSelect": self._allow_multi_select,
                "totalHotspots": len(self._hotspots),
            },
        }
        return json.dumps(data, indent=2)

    def to_dict(self) -> dict[str, Any]:
        """Export to dictionary for frontend frameworks."""
        return {
            "hotspots": [h.to_dict() for h in self._hotspots.values()],
            "groups": self._groups,
            "config": {
                "multiSelect": self._allow_multi_select,
                "totalHotspots": len(self._hotspots),
            },
        }

    def generate_js_handlers(self, container_selector: str = ".schematic-overlay") -> str:
        """
        Generate JavaScript code for frontend interaction handling.

        Args:
            container_selector: CSS selector for the SVG container

        Returns:
            JavaScript code string
        """
        return f"""
// Schematic Hotspot Manager - Auto-generated
// Container: {container_selector}

class SchematicHotspotManager {{
  constructor(containerSelector = "{container_selector}") {{
    this.container = document.querySelector(containerSelector);
    this.hotspots = new Map();
    this.selected = new Set();
    this.allowMultiSelect = {str(self._allow_multi_select).lower()};
    this.eventListeners = new Map();
    this.tooltip = null;
    this.tooltipTimeout = null;

    this.init();
  }}

  init() {{
    if (!this.container) {{
      console.error('Schematic container not found:', '{container_selector}');
      return;
    }}

    this.setupEventListeners();
    this.createTooltipElement();
    this.scanHotspots();
  }}

  scanHotspots() {{
    // Scan for component markers in the SVG
    const markers = this.container.querySelectorAll('.component-marker');
    markers.forEach(marker => {{
      const designator = marker.getAttribute('data-designator');
      if (designator) {{
        this.registerHotspot(designator, marker);
      }}
    }});

    console.log(`SchematicHotspotManager: ${{this.hotspots.size}} hotspots registered`);
  }}

  registerHotspot(designator, element) {{
    this.hotspots.set(designator, {{
      element: element,
      designator: designator,
      type: element.getAttribute('data-type'),
      x: parseFloat(element.getAttribute('data-x')),
      y: parseFloat(element.getAttribute('data-y')),
      selected: false
    }});

    // Add click handler
    element.addEventListener('click', (e) => this.handleClick(e, designator));

    // Add hover handlers for tooltip
    element.addEventListener('mouseenter', (e) => this.handleHover(e, designator, true));
    element.addEventListener('mouseleave', (e) => this.handleHover(e, designator, false));

    // Add double-click handler
    element.addEventListener('dblclick', (e) => this.handleDoubleClick(e, designator));
  }}

  setupEventListeners() {{
    // Click outside to deselect
    document.addEventListener('click', (e) => {{
      if (!e.target.closest('.component-marker')) {{
        this.deselectAll();
      }}
    }});
  }}

  createTooltipElement() {{
    this.tooltip = document.createElement('div');
    this.tooltip.className = 'schematic-tooltip';
    this.tooltip.style.cssText = `
      position: absolute;
      background: rgba(0, 0, 0, 0.9);
      color: #fff;
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-family: system-ui, -apple-system, sans-serif;
      pointer-events: none;
      z-index: 10000;
      opacity: 0;
      transition: opacity 0.2s;
      max-width: 250px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      border: 1px solid rgba(255,255,255,0.1);
    `;
    document.body.appendChild(this.tooltip);
  }}

  handleClick(e, designator) {{
    e.stopPropagation();
    e.preventDefault();

    const hotspot = this.hotspots.get(designator);
    if (!hotspot) return;

    // Toggle selection
    if (this.selected.has(designator)) {{
      this.deselect(designator);
    }} else {{
      this.select(designator);
    }}

    // Emit event
    this.emit('click', {{ designator, hotspot, event: e }});

    // Fetch component details from backend
    this.fetchComponentDetails(designator);
  }}

  handleDoubleClick(e, designator) {{
    e.stopPropagation();
    this.emit('dblclick', {{ designator, event: e }});
  }}

  handleHover(e, designator, isHovering) {{
    const hotspot = this.hotspots.get(designator);
    if (!hotspot) return;

    if (isHovering) {{
      // Show tooltip with delay
      this.tooltipTimeout = setTimeout(() => {{
        this.showTooltip(designator, e);
      }}, 200);

      // Highlight effect
      hotspot.element.style.filter = 'brightness(1.3)';
    }} else {{
      // Hide tooltip
      clearTimeout(this.tooltipTimeout);
      this.hideTooltip();

      // Remove highlight
      hotspot.element.style.filter = '';
    }}

    this.emit('hover', {{ designator, isHovering, hotspot }});
  }}

  showTooltip(designator, e) {{
    const hotspot = this.hotspots.get(designator);
    if (!hotspot) return;

    const title = hotspot.element.querySelector('title');
    const content = title ? title.textContent : `${{designator}} (${{hotspot.type}})`;

    this.tooltip.innerHTML = content;
    this.tooltip.style.opacity = '1';

    // Position tooltip
    const rect = hotspot.element.getBoundingClientRect();
    this.tooltip.style.left = `${{rect.left + rect.width/2 - this.tooltip.offsetWidth/2}}px`;
    this.tooltip.style.top = `${{rect.top - this.tooltip.offsetHeight - 10}}px`;
  }}

  hideTooltip() {{
    this.tooltip.style.opacity = '0';
  }}

  select(designator) {{
    if (!this.allowMultiSelect && this.selected.size > 0) {{
      this.deselectAll();
    }}

    const hotspot = this.hotspots.get(designator);
    if (!hotspot) return;

    hotspot.selected = true;
    hotspot.element.classList.add('selected');
    this.selected.add(designator);

    this.emit('select', {{ designator, hotspot }});
  }}

  deselect(designator) {{
    const hotspot = this.hotspots.get(designator);
    if (!hotspot) return;

    hotspot.selected = false;
    hotspot.element.classList.remove('selected');
    this.selected.delete(designator);

    this.emit('deselect', {{ designator, hotspot }});
  }}

  deselectAll() {{
    const toDeselect = Array.from(this.selected);
    toDeselect.forEach(d => this.deselect(d));
  }}

  async fetchComponentDetails(designator) {{
    try {{
      const response = await fetch(`/api/component/${{encodeURIComponent(designator)}}`);
      if (response.ok) {{
        const data = await response.json();
        this.emit('componentData', {{ designator, data }});
        this.updateTooltip(designator, data);
      }}
    }} catch (err) {{
      console.warn('Failed to fetch component details:', err);
    }}
  }}

  updateTooltip(designator, data) {{
    // Update tooltip with fetched data
    const hotspot = this.hotspots.get(designator);
    if (!hotspot) return;

    const titleEl = hotspot.element.querySelector('title');
    if (titleEl) {{
      const details = Object.entries(data)
        .filter(([k, v]) => v && !k.startsWith('_'))
        .map(([k, v]) => `${{k}}: ${{v}}`)
        .join('\\n');

      if (details) {{
        titleEl.textContent = `${{designator}}\\n${{details}}`;
      }}
    }}
  }}

  highlightByType(type) {{
    this.hotspots.forEach((hotspot, designator) => {{
      if (hotspot.type === type) {{
        hotspot.element.style.filter = 'brightness(1.5) drop-shadow(0 0 8px #ff5f1f)';
      }} else {{
        hotspot.element.style.opacity = '0.3';
      }}
    }});
  }}

  clearHighlight() {{
    this.hotspots.forEach((hotspot) => {{
      hotspot.element.style.filter = '';
      hotspot.element.style.opacity = '';
    }});
  }}

  // Event system
  on(event, callback) {{
    if (!this.eventListeners.has(event)) {{
      this.eventListeners.set(event, []);
    }}
    this.eventListeners.get(event).push(callback);
  }}

  off(event, callback) {{
    const listeners = this.eventListeners.get(event);
    if (listeners) {{
      const idx = listeners.indexOf(callback);
      if (idx > -1) listeners.splice(idx, 1);
    }}
  }}

  emit(event, data) {{
    const listeners = this.eventListeners.get(event);
    if (listeners) {{
      listeners.forEach(cb => cb(data));
    }}
  }}

  // Getters
  getSelected() {{
    return Array.from(this.selected).map(d => this.hotspots.get(d)).filter(Boolean);
  }}

  getHotspot(designator) {{
    return this.hotspots.get(designator);
  }}

  getAllHotspots() {{
    return Array.from(this.hotspots.values());
  }}
}}

// Initialize on DOM ready
if (document.readyState === 'loading') {{
  document.addEventListener('DOMContentLoaded', () => {{
    window.schematicHotspotManager = new SchematicHotspotManager('{container_selector}');
  }});
}} else {{
  window.schematicHotspotManager = new SchematicHotspotManager('{container_selector}');
}}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {{
  module.exports = SchematicHotspotManager;
}}
"""

    def generate_css(self) -> str:
        """
        Generate CSS styles for hotspot interactions.

        Returns:
            CSS code string
        """
        return """
/* Schematic Hotspot Styles */

.component-marker {
  cursor: pointer;
  transition: all 0.2s ease;
}

.component-marker:hover .marker-shape {
  fill: rgba(255, 95, 31, 0.9);
  stroke: #ff5f1f;
  stroke-width: 3;
  filter: brightness(1.2);
}

.component-marker.selected .marker-shape {
  fill: rgba(255, 95, 31, 0.95);
  stroke: #ff5f1f;
  stroke-width: 3;
  filter: drop-shadow(0 0 8px rgba(255, 95, 31, 0.6));
}

.component-marker.selected .marker-label {
  opacity: 1;
  font-weight: 700;
}

.component-marker.disabled {
  pointer-events: none;
  opacity: 0.3;
}

.schematic-tooltip {
  position: absolute;
  background: rgba(17, 17, 17, 0.95);
  color: #e0e0e0;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  pointer-events: none;
  z-index: 10000;
  opacity: 0;
  transition: opacity 0.2s ease, transform 0.2s ease;
  max-width: 280px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 95, 31, 0.3);
  backdrop-filter: blur(10px);
}

.schematic-tooltip.visible {
  opacity: 1;
  transform: translateY(-4px);
}

.schematic-tooltip::after {
  content: '';
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  border-width: 6px 6px 0;
  border-style: solid;
  border-color: rgba(17, 17, 17, 0.95) transparent transparent transparent;
}

.schematic-tooltip .tooltip-title {
  font-weight: 700;
  color: #ff5f1f;
  margin-bottom: 4px;
  font-size: 13px;
}

.schematic-tooltip .tooltip-detail {
  color: #aaa;
  font-size: 11px;
  line-height: 1.4;
}

/* Selection highlight animation */
@keyframes selectionPulse {
  0%, 100% { stroke-width: 3; }
  50% { stroke-width: 5; }
}

.component-marker.selected .marker-shape {
  animation: selectionPulse 1.5s ease-in-out infinite;
}

/* Hover state for trace paths */
.component-marker:hover ~ .trace-path,
.component-marker:hover + .trace-path {
  stroke-opacity: 1;
  stroke-width: 4;
}
"""

    def generate_html_example(self, svg_content: str, title: str = "Schematic Viewer") -> str:
        """
        Generate a complete HTML example with interactive hotspots.

        Args:
            svg_content: SVG markup string
            title: Page title

        Returns:
            Complete HTML document string
        """
        js_code = self.generate_js_handlers()
        css_code = self.generate_css()
        json_data = self.to_json()

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg-color: #080808;
            --panel-bg: #111111;
            --text-color: #e0e0e0;
            --accent-color: #ff5f1f;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: system-ui, -apple-system, sans-serif;
            background: var(--bg-color);
            color: var(--text-color);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        header {{
            background: var(--panel-bg);
            padding: 16px 24px;
            border-bottom: 1px solid #1a1a1a;
            display: flex;
            align-items: center;
            gap: 16px;
        }}

        header h1 {{
            font-size: 18px;
            color: var(--accent-color);
        }}

        .schematic-container {{
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 24px;
            position: relative;
            overflow: auto;
        }}

        .schematic-wrapper {{
            position: relative;
            background: #0d0d0d;
            border: 1px solid #1a1a1a;
            border-radius: 8px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
        }}

        {css_code}

        .info-panel {{
            position: fixed;
            right: 24px;
            top: 80px;
            width: 280px;
            background: var(--panel-bg);
            border: 1px solid #1a1a1a;
            border-radius: 8px;
            padding: 16px;
            display: none;
        }}

        .info-panel.active {{
            display: block;
        }}

        .info-panel h3 {{
            color: var(--accent-color);
            font-size: 14px;
            margin-bottom: 12px;
        }}

        .info-panel .detail {{
            font-size: 12px;
            color: #888;
            margin-bottom: 8px;
        }}

        .info-panel .detail strong {{
            color: #ccc;
        }}
    </style>
</head>
<body>
    <header>
        <h1>🔧 {title}</h1>
        <span style="color: #666; font-size: 12px;">Click components to select • Hover for details</span>
    </header>

    <div class="schematic-container">
        <div class="schematic-wrapper">
            {svg_content}
        </div>
    </div>

    <div class="info-panel" id="infoPanel">
        <h3 id="infoTitle">Component Info</h3>
        <div id="infoContent"></div>
    </div>

    <script>
        {js_code}

        // Custom event handlers for this example
        if (window.schematicHotspotManager) {{
            // Handle selection events
            window.schematicHotspotManager.on('select', (data) => {{
                console.log('Selected:', data.designator);
                updateInfoPanel(data.hotspot);
            }});

            window.schematicHotspotManager.on('deselect', () => {{
                document.getElementById('infoPanel').classList.remove('active');
            }});

            // Handle component data loaded from backend
            window.schematicHotspotManager.on('componentData', (data) => {{
                console.log('Component data:', data);
                updateInfoPanel(data.data);
            }});
        }}

        function updateInfoPanel(data) {{
            const panel = document.getElementById('infoPanel');
            const title = document.getElementById('infoTitle');
            const content = document.getElementById('infoContent');

            panel.classList.add('active');

            if (data.designator || data.Designator) {{
                const des = data.designator || data.Designator;
                const type = data.type || data.Type || data.component_type || 'Unknown';
                title.textContent = `${{des}} (${{type}})`;
            }}

            // Build detail HTML
            let html = '';
            const skipFields = ['designator', 'type', 'x', 'y', '_id'];

            Object.entries(data).forEach(([key, value]) => {{
                if (!skipFields.includes(key) && value !== null && value !== undefined) {{
                    html += `<div class="detail"><strong>${{key}}:</strong> ${{value}}</div>`;
                }}
            }});

            content.innerHTML = html || '<div class="detail">No additional details</div>';
        }}

        // Load hotspot data from embedded JSON
        const hotspotData = {json_data};
        console.log('Hotspot data loaded:', hotspotData);
    </script>
</body>
</html>"""

    def save_js_file(self, output_path: str) -> str:
        """
        Save JavaScript handlers to a file.

        Args:
            output_path: Path to save the JavaScript file

        Returns:
            Path to saved file
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        js_code = self.generate_js_handlers()
        path.write_text(js_code, encoding="utf-8")

        return str(path)

    def save_css_file(self, output_path: str) -> str:
        """
        Save CSS styles to a file.

        Args:
            output_path: Path to save the CSS file

        Returns:
            Path to saved file
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        css_code = self.generate_css()
        path.write_text(css_code, encoding="utf-8")

        return str(path)

    def save_json_file(self, output_path: str) -> str:
        """
        Save hotspot data to JSON file.

        Args:
            output_path: Path to save the JSON file

        Returns:
            Path to saved file
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        json_data = self.to_json()
        path.write_text(json_data, encoding="utf-8")

        return str(path)

    @classmethod
    def from_components(
        cls, components: list[Any], allow_multi_select: bool = False
    ) -> "HotspotManager":
        """
        Create HotspotManager from list of Component objects.

        Args:
            components: List of Component instances
            allow_multi_select: Allow multiple selections

        Returns:
            Configured HotspotManager instance
        """
        manager = cls(allow_multi_select=allow_multi_select)

        for component in components:
            hotspot = ComponentHotspot.from_component(component)
            manager.add_hotspot(hotspot)

        return manager



