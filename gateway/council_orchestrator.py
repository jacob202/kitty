from __future__ import annotations
import logging
from gateway.council_graph import build_production_council

logger = logging.getLogger("kitty.orchestration")


def build_council_graph():
    """Returns the production LangGraph Specialist Council."""
    return build_production_council()


def consult_specialist_council(query: str) -> str:
    """Convenience wrapper for the production council."""
    graph = build_council_graph()
    result = graph.invoke({"query": query, "messages": []})
    return result.get("final_response", "Error: No response generated.")


if __name__ == "__main__":
    demo = consult_specialist_council(
        "How do I repair an audio amplifier using modern machine learning tools?"
    )
    print("--- Answer ---")
    print(demo)
