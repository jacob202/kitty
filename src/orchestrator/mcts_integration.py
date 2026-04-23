"""
MCTS Integration — Wires mcts_planner.py into the orchestration layer.
Routes complex requests through MCTS planning before sub-agent dispatch.
Includes Token Circuit Breaker and Iron Law enforcement.
"""

import time

from src.utils.mcts_planner import MCTSPlanner, VibeState


class IronLawViolationError(Exception):
    """Raised when sub-agent attempts execution without Root Cause Investigation."""

    pass


class TokenLimitExceededError(Exception):
    """Raised when token budget is exceeded."""

    pass


class MCTSDispatcher:
    """Routes complex tasks through MCTS planning before execution."""

    COMPLEXITY_THRESHOLD = 0.6  # Score above this triggers MCTS
    DEFAULT_TOKEN_LIMIT = 50000  # 50k tokens per session

    def __init__(self, token_limit: int = DEFAULT_TOKEN_LIMIT):
        self.planner = MCTSPlanner()
        self.planning_enabled = True
        self.token_limit = token_limit
        self.tokens_used = 0
        self.session_start = time.time()

    def reset_tokens(self):
        """Reset token counter for new session."""
        self.tokens_used = 0
        self.session_start = time.time()

    def add_tokens(self, count: int):
        """Add token usage and check circuit breaker."""
        self.tokens_used += count
        if self.tokens_used > self.token_limit:
            raise TokenLimitExceededError(
                f"Token limit ({self.token_limit}) exceeded. Halting MCTS loop."
            )

    def get_token_status(self) -> dict:
        """Get current token usage status."""
        return {
            "tokens_used": self.tokens_used,
            "token_limit": self.token_limit,
            "percent_used": (self.tokens_used / self.token_limit) * 100,
            "session_duration": time.time() - self.session_start,
        }

    def verify_rci_log(self) -> bool:
        """
        Verify Root Cause Investigation was logged before execution.
        Iron Law: Phase 1 must precede Phase 4.
        """
        # Check if council has debated (simulates RCI)
        if not self.planner.council.debate_history:
            return False
        return True

    def should_plan(self, task_description: str) -> bool:
        """Determine if task is complex enough to require MCTS planning."""
        complexity_indicators = [
            "create",
            "implement",
            "build",
            "design",
            "refactor",
            "multiple",
            "complex",
            "architecture",
            "system",
            "integrate",
            "debug",
            "fix",
            "rewrite",
        ]
        task_lower = task_description.lower()
        indicator_count = sum(1 for ind in complexity_indicators if ind in task_lower)
        return indicator_count >= 2

    def plan_and_route(self, task_description: str) -> dict:
        """
        Run MCTS planning on task.
        Returns routing decision: {'route': 'parallel'|'sequential'|'defer', 'plan': MCTSNode}
        """
        # Check token limit before planning
        if self.tokens_used >= self.token_limit:
            return {
                "route": "halted",
                "error": "Token limit exceeded",
                "vibe": "halted",
                "token_status": self.get_token_status(),
            }

        if not self.planning_enabled:
            return {"route": "direct", "plan": None, "vibe": "executing"}

        if not self.should_plan(task_description):
            return {"route": "direct", "plan": None, "vibe": "executing"}

        # Run MCTS planning
        plan = self.planner.plan(task_description)

        # Determine route based on MCTS decision
        selected_child = next(
            (c for c in plan.children if c.status.value == "selected"), None
        )

        if selected_child:
            if "Parallel" in selected_child.label:
                route = "parallel"
            elif "Sequential" in selected_child.label:
                route = "sequential"
            else:
                route = "defer"
        else:
            route = "direct"

        return {
            "route": route,
            "plan": plan,
            "vibe": self.planner.vibe_state.value,
            "council_approved": all(m.approved for m in self.planner.council.members),
            "council_members": [
                {"name": m.name, "stance": m.stance, "approved": m.approved}
                for m in self.planner.council.members
            ],
        }

    def get_current_state(self) -> dict:
        """Get current planning state for UI display."""
        return {
            "vibe": self.planner.vibe_state.value,
            "has_active_plan": self.planner.root is not None,
            "council_approved": all(m.approved for m in self.planner.council.members),
        }

    def interrupt(self):
        """Halt any active planning and reset state."""
        self.planner.vibe_state = VibeState.HALTED
        self.planner.root = None


# Global dispatcher instance
_mcts_dispatcher: MCTSDispatcher | None = None


def get_dispatcher() -> MCTSDispatcher:
    global _mcts_dispatcher
    if _mcts_dispatcher is None:
        _mcts_dispatcher = MCTSDispatcher()
    return _mcts_dispatcher


def route_task(task_description: str) -> dict:
    """Convenience function to route a task through MCTS."""
    return get_dispatcher().plan_and_route(task_description)
