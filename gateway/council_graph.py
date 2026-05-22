import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from gateway.llm_client import call_llm
from gateway.paths import LOGS_DIR, PROJECT_ROOT
from gateway.registry import get_collection_id, list_specialists
from gateway.search_client import search_client

logger = logging.getLogger("kitty.council")

ENV_FILE = PROJECT_ROOT / "kitty_gateway" / "openwebui.env"
COUNCIL_TRACE_FILE = LOGS_DIR / "council_traces.jsonl"


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
    retrieval_debug: Dict[str, Any]
    synthesis_allowed: bool


def _summarize_attempt(retrieval: Dict[str, Any], specialist: str) -> Dict[str, Any]:
    return {
        "specialist": specialist,
        "kb_name": retrieval.get("kb_name"),
        "kb_id": retrieval.get("kb_id"),
        "status": retrieval.get("status"),
        "hit_count": retrieval.get("hit_count", 0),
        "sources": retrieval.get("sources", []),
        "query": retrieval.get("query"),
        "summary": retrieval.get("summary"),
    }


def _normalize_specialist_name(name: str) -> str:
    return (name or "").strip()


def _log_council_trace(
    *,
    query: str,
    hyde_used: bool,
    specialists_routed: List[str],
    retrieval_debug: Dict[str, Any],
    synthesis_allowed: bool,
    error: str | None = None,
) -> None:
    attempts = retrieval_debug.get("attempts", [])
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "hyde_used": hyde_used,
        "specialists_routed": specialists_routed,
        "per_specialist_hits": {
            attempt.get("specialist"): attempt.get("hit_count", 0)
            for attempt in attempts
        },
        "total_hits": retrieval_debug.get("total_hit_count", 0),
        "sources_found": [
            search_client._hit_chunk_id(hit)
            for hit in retrieval_debug.get("all_hits", [])
        ],
        "synthesis_allowed": synthesis_allowed,
        "error": error,
    }
    COUNCIL_TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if COUNCIL_TRACE_FILE.exists():
        modified = datetime.fromtimestamp(os.path.getmtime(COUNCIL_TRACE_FILE), tz=timezone.utc).date()
        today = datetime.now(timezone.utc).date()
        if modified != today:
            rotated = COUNCIL_TRACE_FILE.with_name(f"council_traces-{modified.isoformat()}.jsonl")
            if not rotated.exists():
                COUNCIL_TRACE_FILE.rename(rotated)
    with COUNCIL_TRACE_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


async def _search_specialists_async(specialists: List[str], query: str, use_hyde: bool):
    tasks = [
        asyncio.to_thread(search_client.search_kb, specialist, query, 5, use_hyde)
        for specialist in specialists
    ]
    return await asyncio.gather(*tasks)


# --- Node Implementations ---


def librarian_node(state: CouncilState):
    """The Librarian: Analyzes the query and routes to one or more specialists."""
    logger.info("Librarian: analyzing query routing")

    specialists = list_specialists()

    prompt = f"""
    You are the Head Librarian of the Specialist Council. 
    Analyze the user's query and decide which specialist(s) are best suited to answer.
    
    AVAILABLE SPECIALISTS: {", ".join(specialists)}
    
    QUERY: {state['query']}
    
    Respond ONLY with a JSON list of specialist names.
    Example: ["electronics", "audio_repair"]
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
        raise KeyError("Librarian returned invalid specialist payload")

    if not isinstance(targets, list) or not targets:
        raise KeyError("Librarian returned no specialists")

    normalized_targets = []
    for specialist in targets:
        normalized = _normalize_specialist_name(specialist)
        get_collection_id(normalized)
        normalized_targets.append(normalized)

    return {"target_specialists": normalized_targets, "iteration_count": 0}


def specialist_node(state: CouncilState):
    """The Specialist: Performs a real vector search in their specific KB."""
    new_pool = list(state.get("context_pool", []))
    specialists = [_normalize_specialist_name(name) for name in (state.get("target_specialists") or [])]
    if not specialists:
        raise KeyError("No specialists available for council retrieval")
    for specialist in specialists:
        get_collection_id(specialist)

    retrievals = asyncio.run(_search_specialists_async(specialists, state["query"], True))
    attempts = []
    all_hits = []
    for specialist, retrieval in zip(specialists, retrievals):
        logger.info("%s specialist: researching knowledge base", specialist.capitalize())
        attempt = _summarize_attempt(retrieval, specialist)
        attempts.append(attempt)
        if retrieval.get("status") == "ok" and retrieval.get("hit_count", 0) > 0:
            all_hits.extend(retrieval.get("hits", []))
            new_pool.append(
                {
                    "specialist": specialist,
                    "content": retrieval["summary"],
                }
            )

    best_attempt = max(attempts, key=lambda item: item.get("hit_count", 0), default={
        "specialist": "unknown specialist",
        "kb_name": "unknown kb",
        "kb_id": None,
        "status": "unknown",
        "hit_count": 0,
        "sources": [],
        "query": state["query"],
        "summary": "",
    })
    total_hit_count = sum(attempt.get("hit_count", 0) for attempt in attempts)
    synthesis_allowed = total_hit_count >= 3
    retrieval_debug = dict(best_attempt)
    retrieval_debug["attempts"] = attempts
    retrieval_debug["searched_specialists"] = [attempt["specialist"] for attempt in attempts]
    retrieval_debug["total_hit_count"] = total_hit_count
    retrieval_debug["all_hits"] = all_hits

    logger.info(
        "Council retrieval debug: searched=%s best_specialist=%s total_hits=%s synthesis_allowed=%s top_sources=%s",
        ", ".join(retrieval_debug["searched_specialists"]) or "none",
        retrieval_debug["specialist"],
        total_hit_count,
        synthesis_allowed,
        ", ".join(retrieval_debug["sources"][:3]) or "none",
    )
    _log_council_trace(
        query=state["query"],
        hyde_used=True,
        specialists_routed=specialists,
        retrieval_debug=retrieval_debug,
        synthesis_allowed=synthesis_allowed,
    )

    return {
        "context_pool": new_pool,
        "retrieval_debug": retrieval_debug,
        "synthesis_allowed": synthesis_allowed,
    }


def synthesis_node(state: CouncilState):
    """The Synthesizer: Merges all specialist briefings into the final answer."""
    logger.info("Synthesizer: crafting unified response")

    retrieval_debug = state.get("retrieval_debug") or {}
    if not state.get("synthesis_allowed", False):
        return {
            "final_response": "Insufficient evidence. Please refine your query or ingest more documents."
        }

    context_str = "\n\n".join(
        [f"[{c['specialist']}]: {c['content']}" for c in state["context_pool"]]
    )

    prompt = f"""
    You are the Voice of the Specialist Council. 
    Synthesize a final response to the user's query based on the briefings provided by our specialists.
    
    QUERY: {state['query']}
    
    SPECIALIST BRIEFINGS:
    {context_str}
    
    Ground every meaningful claim in the specialist briefings above.
    Use inline citations in the form [specialist: source] for each meaningful claim.
    Example: Based on [electronics: service-manual.pdf], the driver stage likely failed at the gate resistor.
    Name the most relevant source documents when they materially support your answer.
    If the briefings are incomplete or generic, say so plainly instead of pretending they are model-specific.
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
