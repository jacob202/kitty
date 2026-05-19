import json
import logging
from typing import Annotated, Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from gateway.llm_client import call_llm
from gateway.paths import PROJECT_ROOT
from gateway.search_client import search_client

logger = logging.getLogger("kitty.council")

ENV_FILE = PROJECT_ROOT / "kitty_gateway" / "openwebui.env"


def load_owui_creds():
    vals = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    return {
        "url": vals.get("WEBUI_URL", "http://127.0.0.1:3000"),
        "email": vals.get("WEBUI_ADMIN_EMAIL"),
        "password": vals.get("WEBUI_ADMIN_PASSWORD"),
    }


# --- State Schema ---
class CouncilState(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    target_specialists: List[str]
    context_pool: List[Dict[str, Any]]
    final_response: str
    iteration_count: int


# --- Node Implementations ---


def librarian_node(state: CouncilState):
    """The Librarian: Analyzes the query and routes to one or more specialists."""
    logger.info("Librarian: analyzing query routing")

    specialists = [
        "electronics",
        "automotive",
        "math & physics",
        "audio repair",
        "machine learning",
        "llms & rag",
        "anatomy & biomechanics",
        "clinical & trauma",
        "habits & performance",
    ]

    prompt = f"""
    You are the Head Librarian of the Specialist Council. 
    Analyze the user's query and decide which specialist(s) are best suited to answer.
    
    AVAILABLE SPECIALISTS: {", ".join(specialists)}
    
    QUERY: {state['query']}
    
    Respond ONLY with a JSON list of specialist names.
    Example: ["electronics", "audio repair"]
    """

    response = call_llm(
        messages=[{"role": "user", "content": prompt}],
        model="kitty-default",
        max_tokens=200,
        temperature=0,
    )

    try:
        clean_json = response.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0]
        targets = json.loads(clean_json)
    except (json.JSONDecodeError, IndexError, TypeError):
        targets = ["generalist"]

    return {"target_specialists": targets, "iteration_count": 0}


def specialist_node(state: CouncilState):
    """The Specialist: Performs a real vector search in their specific KB."""
    specialist = state["target_specialists"][0]
    logger.info("%s specialist: researching knowledge base", specialist.capitalize())

    context = search_client.search_kb(specialist, state["query"])

    mock_context = {
        "specialist": specialist,
        "content": context,
    }

    new_pool = list(state.get("context_pool", []))
    new_pool.append(mock_context)

    return {"context_pool": new_pool}


def synthesis_node(state: CouncilState):
    """The Synthesizer: Merges all specialist briefings into the final answer."""
    logger.info("Synthesizer: crafting unified response")

    context_str = "\n\n".join(
        [f"[{c['specialist']}]: {c['content']}" for c in state["context_pool"]]
    )

    prompt = f"""
    You are the Voice of the Specialist Council. 
    Synthesize a final response to the user's query based on the briefings provided by our specialists.
    
    QUERY: {state['query']}
    
    SPECIALIST BRIEFINGS:
    {context_str}
    
    Ensure you highlight the "Soul" and "Spicy Hooks" found in our library.
    """

    response = call_llm(
        messages=[{"role": "user", "content": prompt}],
        model="kitty-default",
        max_tokens=1500,
    )

    return {"final_response": response}


# --- Graph Assembly ---


def build_production_council():
    builder = StateGraph(CouncilState)

    builder.add_node("librarian", librarian_node)
    builder.add_node("specialist", specialist_node)
    builder.add_node("synthesizer", synthesis_node)

    builder.set_entry_point("librarian")
    builder.add_edge("librarian", "specialist")
    builder.add_edge("specialist", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile()


if __name__ == "__main__":
    graph = build_production_council()
    result = graph.invoke(
        {
            "query": "How do I fix a Sansui amp with a blown mosfet?",
            "messages": [],
        }
    )
    print("\n--- FINAL COUNCIL RESPONSE ---")
    print(result["final_response"])
