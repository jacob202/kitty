import json
import logging
import os
import time
from typing import Any, TypedDict

import instructor
import numpy as np

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from openai import OpenAI
from pydantic import BaseModel

from src.schemas.hardware import BaseEntity, Edge
from src.utils.canonical_logger import log_canonical, log_quarantine
from src.utils.svg_generator import determine_component_type

try:
    from tools.vision_worker import Florence2Worker
except ImportError:
    Florence2Worker = None

load_dotenv()

# Initialize Instructor client
client = instructor.from_openai(
    OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY")),
    mode=instructor.Mode.JSON,
)


class HardwareState(TypedDict):
    user_input: str
    image_path: str | None
    debug_info: dict[str, Any]  # Added for debugging
    vision_raw: dict | None
    entities: list[dict]
    edges: list[dict]
    quarantine: list[dict]
    trace_result: str
    iterations: int
    metrics: dict[str, Any]  # Track:
    # vision_time: float
    # validation_time: float
    # tracing_time: float
    # component_count: int
    # connection_count: int
    # error_count: int


class ExtractionResult(BaseModel):
    entities: list[BaseEntity]
    edges: list[Edge] = []


from functools import lru_cache


def check_hardware_acceleration():
    """Check available hardware acceleration options."""
    try:
        import torch

        return {
            "cuda": torch.cuda.is_available(),
            "mps": torch.backends.mps.is_available(),
            "cpu_count": os.cpu_count(),
            "enabled": os.getenv("USE_HARDWARE_ACCEL", "True").lower() == "true",
        }
    except ImportError:
        # Torch not installed, use CPU only
        return {"cuda": False, "mps": False, "cpu_count": os.cpu_count(), "enabled": False}


@lru_cache(maxsize=1)
def get_florence_worker():
    """Cache Florence worker initialization with hardware awareness."""
    if Florence2Worker is None:
        raise ImportError("Florence2Worker requires optional vision dependencies")
    hw = check_hardware_acceleration()
    if hw["enabled"]:
        if hw["cuda"]:
            logger.info("Using CUDA acceleration")
        elif hw["mps"]:
            logger.info("Using Metal acceleration (MPS)")
        else:
            logger.info("Using CPU (no hardware acceleration)")
    return Florence2Worker(device="cuda" if hw["cuda"] else "mps" if hw["mps"] else "cpu")


def extract_vision_node(state: HardwareState) -> HardwareState:
    """Tier 2: Extract bounding boxes and OCR text using Florence-2."""
    if not state.get("image_path"):
        return state

    logger.info(f"Extracting vision data from {state['image_path']}...")

    # Emit node status - using a safer approach to avoid circular imports
    try:
        import sys

        web_module = sys.modules.get("web")
        if web_module and hasattr(web_module, "_emit_node_status"):
            web_module._emit_node_status(
                "vision_extraction", "started", {"image_path": state["image_path"]}
            )
            if hasattr(web_module, "_emit_thinking_bubble"):
                web_module._emit_thinking_bubble(
                    "Starting OCR scan of schematic image...", confidence=0.8
                )
    except Exception as e:
        logger.error(f"Failed to emit node status: {e}")

    if not os.path.exists(state["image_path"]):
        state["quarantine"].append(
            {"error": f"Image not found: {state['image_path']}", "stage": "vision"}
        )
        try:
            import sys

            web_module = sys.modules.get("web")
            if web_module and hasattr(web_module, "_emit_node_status"):
                web_module._emit_node_status(
                    "vision_extraction", "error", {"error": "Image not found"}
                )
        except Exception:
            pass
        return state

    worker = get_florence_worker()
    try:
        raw_result = worker.run_task(
            state["image_path"], task_prompt="<CAPTION_TO_PHRASE_GROUNDING>"
        )
        # Compress vision data before storing
        import zlib

        state["vision_raw"] = {
            "bboxes": raw_result["bboxes"],
            "labels": raw_result["labels"],
            "compressed": zlib.compress(json.dumps(raw_result).encode()),
        }

        # Emit completion
        try:
            import sys

            web_module = sys.modules.get("web")
            if web_module and hasattr(web_module, "_emit_node_status"):
                web_module._emit_node_status(
                    "vision_extraction",
                    "completed",
                    {
                        "bboxes_count": len(raw_result.get("bboxes", [])),
                        "labels_count": len(raw_result.get("labels", [])),
                    },
                )
                if hasattr(web_module, "_emit_thinking_bubble"):
                    web_module._emit_thinking_bubble(
                        f"Found {len(raw_result.get('labels', []))} components in image",
                        confidence=0.9,
                    )
        except Exception as e:
            logger.error(f"Failed to emit completion: {e}")

    except Exception as e:
        logger.error(f"Vision extraction failed: {e}")
        state["quarantine"].append({"error": str(e), "stage": "vision"})
        try:
            import sys

            web_module = sys.modules.get("web")
            if web_module and hasattr(web_module, "_emit_node_status"):
                web_module._emit_node_status("vision_extraction", "error", {"error": str(e)})
        except Exception:
            pass

    state["iterations"] += 1
    return state


def validate_logic_node(state: HardwareState) -> HardwareState:
    """Tier 3: Validate with early termination checks."""
    # Emit node status
    try:
        import sys

        web_module = sys.modules.get("web")
        if web_module and hasattr(web_module, "_emit_node_status"):
            web_module._emit_node_status("logic_validation", "started", {})
            if hasattr(web_module, "_emit_thinking_bubble"):
                web_module._emit_thinking_bubble(
                    "Validating component logic and connections...", confidence=0.7
                )
    except Exception as e:
        logger.error(f"Failed to emit node status: {e}")

    if not state.get("vision_raw"):
        return state

    # Early termination if no valid components found
    if len(state["vision_raw"].get("labels", [])) == 0:
        state["quarantine"].append({"warning": "No components detected in image"})
        return state

    # Skip validation if confidence is too low
    if state.get("metrics", {}).get("confidence_avg", 0) < 0.2:
        state["quarantine"].append({"warning": "Low confidence in component detection"})
        return state

    # Enhanced OCR filtering with component pattern matching
    import re

    bboxes = state["vision_raw"].get("bboxes", [])
    labels = state["vision_raw"].get("labels", [])
    filtered_vision = []

    from src.config.config_manager import ConfigManager
    config_manager = ConfigManager()

    rules = config_manager.get_component_rules()
    component_pattern = re.compile(rules.designator_pattern)
    re.compile(rules.value_pattern) if rules.require_units else None

    # Vectorized preprocessing
    labels = np.array(labels)
    bboxes = np.array(bboxes)
    valid_mask = np.array([bool(component_pattern.match(label.strip())) for label in labels])

    for i in np.where(valid_mask)[0]:
        label = labels[i].strip()
        bbox = bboxes[i]
        label = label.strip()
        if not component_pattern.match(label):
            continue

        # Calculate confidence score (0-1) based on match quality
        match = component_pattern.match(label)
        confidence = 0.5 + (0.5 * (len(match.group(1)) / 5))

        filtered_vision.append(
            {
                "id": f"ocr-{i}",
                "text": label,
                "bbox": bbox,
                "confidence": min(1.0, confidence),
                "type": determine_component_type(label),  # Reuse SVG generator's logic
            }
        )

    from src.config.config_manager import ConfigManager
    config_manager = ConfigManager()

    try:
        agent_def = config_manager.load_config("electronics")
        system_prompt = agent_def["instructions"]
    except Exception as e:
        logger.warning(f"Using default electronics instructions: {str(e)}")
        system_prompt = (
            "You are an expert electrical engineering assistant. Analyze schematic components "
            "and connections, validating against standard electronics conventions."
        )
    user_prompt = (
        f"Document URI: {state.get('image_path', 'unknown')}\n"
        f"Filtered Vision Data: {json.dumps(filtered_vision)}\n\n"
        "Map the identified electronics components and their connections."
    )

    try:
        models_to_try = [
            os.getenv("HARDWARE_MODEL", "google/gemini-2.0-flash-001"),
            "anthropic/claude-3-haiku",
            "anthropic/claude-2.1",
        ]

        last_error = None
        for model in models_to_try:
            try:
                result = client.chat.completions.create(
                    model=model,
                    response_model=ExtractionResult,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_retries=2,
                )
                break
            except Exception as e:
                last_error = e
                continue
        else:
            raise RuntimeError(f"All models failed: {last_error}")

        entities = [e.model_dump() for e in result.entities]
        edges = [e.model_dump() for e in result.edges]

        # Calculate data quality scores
        def validate_against_rules(component: dict) -> bool:
            """Validate a component against design rules."""
            from src.config.config_manager import ConfigManager

            config_manager = ConfigManager()

            rules = config_manager.get_component_rules()

            designator = component.get("designator", "")
            value = component.get("value", "")

            # Check designator pattern
            import re

            if not re.match(rules.designator_pattern, designator):
                return False

            # Check value pattern if required
            if rules.require_units and value:
                if not re.match(rules.value_pattern, value):
                    return False

            # Check confidence threshold
            if component.get("confidence", 0) < rules.min_confidence:
                return False

            return True

        def calculate_quality(ents: list[dict]) -> dict[str, float]:
            valid = sum(1 for e in ents if e.get("confidence", 0) > 0.7)
            return {
                "completeness": valid / len(ents) if ents else 0,
                "confidence_avg": sum(e.get("confidence", 0) for e in ents) / len(ents)
                if ents
                else 0,
                "rules_compliance": sum(1 for e in ents if validate_against_rules(e)) / len(ents)
                if ents
                else 0,
            }

        state["entities"] = entities
        state["edges"] = edges
        state["metrics"]["data_quality"] = calculate_quality(entities)

        # Emit completion
        try:
            import sys

            web_module = sys.modules.get("web")
            if web_module and hasattr(web_module, "_emit_node_status"):
                web_module._emit_node_status(
                    "logic_validation",
                    "completed",
                    {"entities_count": len(entities), "edges_count": len(edges)},
                )
        except Exception as e:
            logger.error(f"Failed to emit completion: {e}")

        for entity in result.entities:
            log_canonical(entity)
        for edge in result.edges:
            log_canonical(edge)

    except Exception as e:
        logger.error(f"Logic validation failed: {e}")
        log_quarantine(state["vision_raw"], str(e))
        state["quarantine"].append({"error": str(e), "stage": "logic"})
        # Emit error
        try:
            import sys

            web_module = sys.modules.get("web")
            if web_module and hasattr(web_module, "_emit_node_status"):
                web_module._emit_node_status("logic_validation", "error", {"error": str(e)})
        except Exception:
            pass

    return state


def trace_specialist_node(state: HardwareState) -> HardwareState:
    """Tier 4: Perform circuit analysis including:
    - Signal path tracing
    - Power rail identification
    - Netlist generation
    - Connectivity validation
    """
    from src.utils.graph_processor import HardwareGraph

    if not state.get("entities"):
        state["trace_result"] = "No components identified to trace."
        return state

    logger.info("Tracing signal paths with Graph Co-Processor...")

    # Initialize graph from the current log
    hg = HardwareGraph()

    # Check if user query mentions specific components to trace
    import re

    designators = re.findall(r"[RCDQLT]\d{3}", state["user_input"].upper())

    if len(designators) >= 2:
        # Try to find a path between the first two mentioned components
        path = hg.find_signal_path(designators[0], designators[1])
        if path:
            path_str = " -> ".join(
                [p.get("properties", {}).get("designator", "unknown") for p in path]
            )
            state["trace_result"] = f"Signal Path: {path_str}. Trace successful."
            return state

    # Fallback: Summary of findings
    summary = f"Identified {len(state['entities'])} components and {len(state.get('edges', []))} connections. "
    if state["entities"]:
        top_entity = state["entities"][0]
        summary += f"Top entity: {top_entity.get('label', 'unknown')}. "

        # Get neighbors for the top entity
        neighbors = hg.get_neighbors(top_entity.get("properties", {}).get("designator", ""))
        if neighbors:
            n_labels = [n.get("properties", {}).get("designator", "unknown") for n in neighbors]
            summary += f"Connected to: {', '.join(n_labels)}."

    state["trace_result"] = summary
    return state


def coder_fix_node(state: HardwareState) -> HardwareState:
    """Autonomous code fixing node that analyzes errors and implements fixes."""
    logger.info("Coder node activated for autonomous fixes...")

    # Check if we have quarantine entries that need fixing
    if not state.get("quarantine"):
        state["trace_result"] += "\n[No errors detected - coder node skipped]"
        return state

    # Prepare error context for the coder agent
    error_context = {
        "quarantine_entries": state.get("quarantine", []),
        "vision_raw_keys": list(state.get("vision_raw", {}).keys())
        if state.get("vision_raw")
        else [],
        "entities_count": len(state.get("entities", [])),
        "edges_count": len(state.get("edges", [])),
        "iterations": state.get("iterations", 0),
    }

    # Create a prompt for the coder agent
    f"""
    Analyze these hardware analysis pipeline errors and propose code fixes:

    ERROR CONTEXT:
    {json.dumps(error_context, indent=2)}

    PIPELINE STATE:
    - Current file: {__file__}
    - Hardware subgraph with nodes: vision → logic → specialist → coder_fix
    - Recent quarantine entries indicate issues in extraction or validation

    TASKS:
    1. Identify the root cause of the errors
    2. Read relevant source files to understand current implementation
    3. Propose specific code changes to fix the issues
    4. Implement changes using SEARCH/REPLACE blocks
    5. Suggest any improvements to prevent similar errors

    Focus on fixing:
    - Vision extraction failures
    - Component validation issues
    - Data quality problems
    - Performance bottlenecks

    Provide concrete code changes.
    """

    # In a real implementation, we would call the coder agent via Ollama/OpenRouter
    # For now, we'll log the intent and prepare for actual implementation
    logger.info(f"Would analyze {len(state['quarantine'])} quarantine entries")
    logger.info("Error context prepared for autonomous fixing")

    # Mark that coder node was activated
    state.setdefault("debug_info", {})["coder_activated"] = True
    state.setdefault("debug_info", {})["coder_timestamp"] = time.time()

    # For now, just add a note to trace_result
    state["trace_result"] += (
        f"\n[Coder] {len(state['quarantine'])} errors queued for autonomous fixing"
    )

    return state


def create_hardware_graph(debug: bool = False):
    """Create hardware processing graph with optional debugging and autonomous fixing."""
    workflow = StateGraph(HardwareState)

    if debug:

        debug_state = {}

        def debug_checkpoint(state: HardwareState) -> None:
            """Debug checkpoint that captures full state"""
            debug_state.update(state)
            logger.debug(f"State update:\n{json.dumps(state, indent=2)}")

        workflow.add_node("debug", debug_checkpoint)

    workflow.add_node("vision", extract_vision_node)
    workflow.add_node("logic", validate_logic_node)
    workflow.add_node("specialist", trace_specialist_node)
    workflow.add_node("coder_fix", coder_fix_node)

    workflow.set_entry_point("vision")
    workflow.add_edge("vision", "logic")

    # Conditional routing: if quarantine has entries, go to coder_fix, else to specialist
    def route_after_logic(state: HardwareState) -> str:
        if state.get("quarantine") and len(state["quarantine"]) > 0:
            logger.info(f"{len(state['quarantine'])} quarantine entries → coder_fix")
            return "coder_fix"
        else:
            return "specialist"

    workflow.add_conditional_edges(
        "logic", route_after_logic, {"coder_fix": "coder_fix", "specialist": "specialist"}
    )

    # After coder_fix, retry vision extraction (reflexion loop)
    def route_after_coder(state: HardwareState) -> str:
        # Check if coder made fixes that warrant retry
        if state.get("debug_info", {}).get("coder_activated"):
            logger.info("Coder completed → retrying vision extraction")
            return "vision"
        else:
            return "specialist"

    workflow.add_conditional_edges(
        "coder_fix", route_after_coder, {"vision": "vision", "specialist": "specialist"}
    )

    workflow.add_edge("specialist", END)

    return workflow.compile()


hardware_graph = create_hardware_graph()
