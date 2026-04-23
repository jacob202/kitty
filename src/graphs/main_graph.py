"""
Main LangGraph orchestration for the Kitty Supervisor.
"""
import json
import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


# 1. The Graph State
class GraphState(TypedDict):
    user_input: str
    current_tier: int
    active_agent: str | None
    context_data: str
    tool_outputs: list[dict[str, Any]]
    iterations: int
    final_result: str

class MainGraph:
    def __init__(self, supervisor):
        self.supervisor = supervisor
        self.workflow = self._build_graph()

    def _build_graph(self):
        """Compile the multi-tier Supervisor-Worker LangGraph."""
        workflow = StateGraph(GraphState)

        # Define Nodes
        workflow.add_node("supervisor_node", self._supervisor_node)
        workflow.add_node("specialist_node", self._specialist_node)
        workflow.add_node("organizer_node", self._organizer_node)
        workflow.add_node("shadow_node", self._shadow_node)

        # Set Entry
        workflow.set_entry_point("supervisor_node")

        # Safety Rails: Add Conditional Routing logic
        workflow.add_conditional_edges(
            "supervisor_node",
            self._route_task,
            {
                "specialist": "specialist_node",
                "organizer": "organizer_node",
                "shadow": "shadow_node",
                "end": END
            }
        )

        # Workers terminate the graph after task completion
        workflow.add_edge("specialist_node", END)
        workflow.add_edge("organizer_node", END)
        workflow.add_edge("shadow_node", END)

        return workflow.compile()

    def _supervisor_node(self, state: GraphState) -> GraphState:
        """Master Router using Gemini 1.5 Pro / Claude 3.5 Sonnet."""
        self.supervisor._emit_status("supervisor", "started")
        state["iterations"] += 1

        # Safety Rails
        if state["iterations"] > 3:
            state["final_result"] = "Max iterations reached. Aborting to prevent runaway loops."
            state["current_tier"] = -1
            self.supervisor._emit_status("supervisor", "error", data={"error": "Max iterations"})
            return state

        # Local fallback override
        user_input_lower = state["user_input"].lower()
        if any(keyword in user_input_lower for keyword in ["offline", "shadow", "uncensored", "free mode", "nsfw", "illegal", "restricted", "bypass", "policy"]):
            state["current_tier"] = 0
            state["active_agent"] = "local"
            self.supervisor._emit_status("supervisor", "completed", data={"decision": "local_fallback"})
            return state

        routing_system = f"""Identify intent and reply ONLY valid JSON.
        {{"tier": 2, "specialist": "<name>"}} - For tools and domain experts
        {{"tier": 1, "specialist": "organizer"}} - For fast JSON/formatting
        {{"tier": 0, "specialist": "local"}} - For free local fallback

        SPECIALISTS: {", ".join(s['name'] for s in self.supervisor.specialists)}"""

        routing_query = f"Context: {state['context_data']}\nUser: {state['user_input']}"

        try:
            # Use Tier 3 model for reasoning
            raw = self.supervisor._call_openrouter(routing_query, routing_system, model="google/gemini-1.5-pro")
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            decision = json.loads(m.group(0) if m else raw)

            state["current_tier"] = decision.get("tier", 2)
            state["active_agent"] = decision.get("specialist")
            self.supervisor._emit_status("supervisor", "completed", data=decision)
        except Exception:
            # Fallback on failure to local shadow node
            state["current_tier"] = 0
            state["active_agent"] = "local"
            self.supervisor._emit_status("supervisor", "error", data={"fallback": "local"})

        return state

    def _specialist_node(self, state: GraphState) -> GraphState:
        """Domain Experts using specialized JSON personas and local/remote tools."""
        agent_name = state.get("active_agent")
        self.supervisor._emit_status("specialist", "started", data={"agent": agent_name})

        # Standard Specialist Delegation via JSON definition
        spec = next((s for s in self.supervisor.specialists if s["name"] == agent_name), None)
        if spec:
            self.supervisor._emit_thought(f"Delegating to {agent_name} specialist with technical context...")
            # Delegate with use_history=False to prevent context-bloat and recursive loops
            result = self.supervisor._run_specialist_with_tools(spec, state["user_input"])
        else:
            # Fallback fast-path via dynamic personality model
            self.supervisor._emit_thought(f"No exact specialist found for '{agent_name}'. Using personality fallback.")
            result = self.supervisor._stream_openrouter(
                state["user_input"],
                system_prompt=state["context_data"],
                model=self.supervisor.get_personality_model()
            )

        state["final_result"] = result
        self.supervisor._emit_status("specialist", "completed")
        return state

    def _organizer_node(self, state: GraphState) -> GraphState:
        """Data structuring and rapid formatting."""
        self.supervisor._emit_status("organizer", "started")
        self.supervisor._emit_thought("Formatting response into structured tables/JSON...")
        # Use active personality model for fast data cleanup
        result = self.supervisor._stream_openrouter(
            state["user_input"],
            system_prompt="You are a data organizer. Format results in clean Markdown tables or JSON.",
            model=self.supervisor.get_personality_model()
        )
        state["final_result"] = result
        self.supervisor._emit_status("organizer", "completed")
        return state

    def _shadow_node(self, state: GraphState) -> GraphState:
        """Local routing fallback using Ollama (Shadow Mode)."""
        self.supervisor._emit_status("shadow", "started")
        try:
            model = self.supervisor.config.get("ollama_model", "qwen2.5-coder:7b")
            self.supervisor._emit_thought(f"Running offline inference via {model}...")
            result = self.supervisor._stream_ollama(state["user_input"])
        except Exception as e:
            result = f"Shadow Node Error: {e}"
            self.supervisor._emit_status("shadow", "error", data={"error": str(e)})

        state["final_result"] = result
        self.supervisor._emit_status("shadow", "completed")
        return state

    def _route_task(self, state: GraphState) -> str:
        """Reads state to determine which edge to traverse next."""
        if state["iterations"] > 3 or state.get("current_tier") == -1:
            return "end"

        tier_map = {2: "specialist", 1: "organizer", 0: "shadow"}
        return tier_map.get(state["current_tier"], "end")

    def invoke(self, initial_state: GraphState) -> GraphState:
        """Invoke the graph workflow."""
        return self.workflow.invoke(initial_state)
