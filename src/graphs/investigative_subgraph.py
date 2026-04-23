import json
import os
from typing import TypedDict

import instructor
from langgraph.graph import END, StateGraph
from openai import OpenAI
from pydantic import BaseModel

from src.schemas.hardware import BaseEntity, Edge
from src.utils.canonical_logger import log_canonical, log_quarantine
from tools.analytics_engine import AnalyticsEngine


class InvestigativeState(TypedDict):
    user_input: str
    raw_text: str
    entities: list[dict]
    edges: list[dict]
    summary: str
    iterations: int

class InvestigativeExtraction(BaseModel):
    entities: list[BaseEntity]
    edges: list[Edge] = []

# Initialize Instructor client
client = instructor.from_openai(OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
), mode=instructor.Mode.JSON)

def extract_investigative_node(state: InvestigativeState) -> InvestigativeState:
    """Tier 3: Extract People, Orgs, and Transactions from raw text dump."""
    print("[Investigator] Extracting entities and relationships from text...")

    # Emit status
    try:
        import sys
        web_module = sys.modules.get('web')
        if web_module:
            if hasattr(web_module, '_emit_node_status'):
                web_module._emit_node_status("investigative_extraction", "started")
            if hasattr(web_module, '_emit_thinking_bubble'):
                web_module._emit_thinking_bubble("Analyzing document dump for people and organizations...", confidence=0.8)
    except Exception:
        pass

    system_prompt = (
        "You are a senior investigative journalist AI. Your task is to analyze "
        "document dumps and extract a knowledge graph of entities and their connections.\n\n"
        "Entities: Person, Organization, Transaction, Contract.\n"
        "Edges: OWNED_BY, PAID_TO, WORKS_FOR, SIGNED_BY.\n\n"
        "Be extremely precise. Look for shell companies and beneficial ownership."
    )

    user_prompt = f"Raw Text Data:\n{state['raw_text']}\n\nMap the graph."

    try:
        result = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            response_model=InvestigativeExtraction,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        state["entities"] = [e.model_dump() for e in result.entities]
        state["edges"] = [e.model_dump() for e in result.edges]

        if web_module:
            if hasattr(web_module, '_emit_node_status'):
                web_module._emit_node_status("investigative_extraction", "completed", {"entities": len(result.entities)})
            if hasattr(web_module, '_emit_thinking_bubble'):
                web_module._emit_thinking_bubble(f"Mapped {len(result.entities)} entities and {len(result.edges)} connections.", confidence=1.0)

        for entity in result.entities:
            log_canonical(entity)
        for edge in result.edges:
            log_canonical(edge)

    except Exception as e:
        print(f"[Investigator] Extraction failed: {e}")
        log_quarantine({"text": state["raw_text"][:500]}, str(e))
        if web_module and hasattr(web_module, '_emit_node_status'):
            web_module._emit_node_status("investigative_extraction", "error", {"error": str(e)})

    return state

def pattern_analysis_node(state: InvestigativeState) -> InvestigativeState:
    """Tier 4: Use DuckDB to find hidden patterns or anomalies in the current log."""
    print("[Investigator] Running DuckDB pattern analysis...")

    # Emit status
    try:
        import sys
        web_module = sys.modules.get('web')
        if web_module:
            if hasattr(web_module, '_emit_node_status'):
                web_module._emit_node_status("pattern_analysis", "started")
            if hasattr(web_module, '_emit_thinking_bubble'):
                web_module._emit_thinking_bubble("Running DuckDB analytical joins to detect shell company patterns...", confidence=0.9)
    except Exception:
        pass

    ae = AnalyticsEngine()

    # Example: Find people with multiple organization roles
    sql = """
    SELECT label, count(*) as role_count
    FROM log
    WHERE type = 'Person'
    GROUP BY label
    HAVING count(*) > 1
    """
    patterns = ae.query(sql)

    if patterns:
        state["summary"] = f"Anomalies detected: {json.dumps(patterns)}"
        if web_module and hasattr(web_module, '_emit_thinking_bubble'):
            web_module._emit_thinking_bubble(f"ALERT: Detected {len(patterns)} entities with overlapping roles.", confidence=1.0)
    else:
        state["summary"] = "No obvious patterns detected in this batch."

    if web_module and hasattr(web_module, '_emit_node_status'):
        web_module._emit_node_status("pattern_analysis", "completed")

    return state

def create_investigative_graph():
    workflow = StateGraph(InvestigativeState)

    workflow.add_node("extraction", extract_investigative_node)
    workflow.add_node("analysis", pattern_analysis_node)

    workflow.set_entry_point("extraction")
    workflow.add_edge("extraction", "analysis")
    workflow.add_edge("analysis", END)

    return workflow.compile()

investigative_graph = create_investigative_graph()
