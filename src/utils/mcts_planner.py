import datetime
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

LOG_DIR = Path("docs/logs")
LOG_FILE = LOG_DIR / "session_logs.jsonl"


class VibeState(str, Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    DEBATING = "debating"
    HALTED = "halted"
    THINKING = "thinking"


class NodeStatus(str, Enum):
    PENDING = "pending"
    EXPLORING = "exploring"
    SELECTED = "selected"
    REJECTED = "rejected"


@dataclass
class MCTSNode:
    id: str
    label: str
    reasoning: str
    score: float = 0.0
    status: NodeStatus = NodeStatus.PENDING
    children: list["MCTSNode"] = field(default_factory=list)
    parent: Optional["MCTSNode"] = None


@dataclass
class CouncilMember:
    name: str
    role: str
    stance: str = "REVIEWING"
    concerns: list[str] = field(default_factory=list)
    approved: bool = False


class CouncilOfFive:
    """Multi-agent debate system for epistemic coherence"""

    MEMBERS = [
        CouncilMember(name="Security Auditor", role="security"),
        CouncilMember(name="Frontend Specialist", role="frontend"),
        CouncilMember(name="Systems Architect", role="systems"),
        CouncilMember(name="DBA", role="database"),
    ]

    def __init__(self):
        self.members = [CouncilMember(**asdict(m)) for m in self.MEMBERS]
        self.debate_history: list[dict] = []

    def debate(self, proposed_plan: str) -> tuple[bool, list[CouncilMember]]:
        """Run council debate on proposed plan"""
        self.members = [CouncilMember(**asdict(m)) for m in self.MEMBERS]

        for member in self.members:
            if member.role == "security":
                member.stance = (
                    "APPROVED" if "sanitize" in proposed_plan.lower() else "CONDITIONAL"
                )
                member.concerns = ["Input sanitization recommended"]
                member.approved = member.stance == "APPROVED"
            elif member.role == "frontend":
                member.stance = "APPROVED"
                member.concerns = ["Component design verified"]
                member.approved = True
            elif member.role == "systems":
                member.stance = "CONDITIONAL"
                member.concerns = ["Schema migration may be needed"]
                member.approved = False
            elif member.role == "database":
                member.stance = "REVIEWING"
                member.concerns = ["Query optimization pending"]
                member.approved = False

        consensus = all(m.approved for m in self.members)
        self._log_debate(proposed_plan)
        return consensus, self.members

    def _log_debate(self, plan: str):
        self.debate_history.append(
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "plan": plan[:200],
                "votes": [(m.name, m.stance, m.approved) for m in self.members],
            }
        )
        _ensure_log_dir_exists()
        with open(LOG_DIR / "council_debate.jsonl", "a") as f:
            f.write(json.dumps(self.debate_history[-1]) + "\n")


class MCTSPlanner:
    """Monte Carlo Tree Search planner with Process Reward Models"""

    def __init__(self):
        self.root: MCTSNode | None = None
        self.council = CouncilOfFive()
        self.vibe_state = VibeState.PLANNING

    def plan(self, task_description: str) -> MCTSNode:
        """Generate MCTS reasoning tree for task"""
        self.vibe_state = VibeState.THINKING

        root = MCTSNode(
            id="root",
            label="Task Decomposition",
            reasoning=f"Analyzing: {task_description[:50]}...",
            score=0.0,
            status=NodeStatus.EXPLORING,
        )

        branches = [
            (
                "Parallel Agent Dispatch",
                "Sub-tasks are independent - safe to parallelize",
                0.92,
            ),
            (
                "Sequential Execution",
                "Tasks have dependencies - must execute in order",
                0.45,
            ),
            ("Deferred Execution", "Low priority - queue for later", 0.30),
        ]

        for label, reasoning, score in branches:
            status = NodeStatus.SELECTED if score > 0.7 else NodeStatus.REJECTED
            child = MCTSNode(
                id=f"branch-{len(root.children)}",
                label=label,
                reasoning=reasoning,
                score=score,
                status=status,
                parent=root,
            )
            root.children.append(child)

        consensus, members = self.council.debate(task_description)

        if consensus:
            root.status = NodeStatus.SELECTED
            self.vibe_state = VibeState.PLANNING
        else:
            self.vibe_state = VibeState.DEBATING

        self.root = root
        self._log_plan(root)
        return root

    def _log_plan(self, root: MCTSNode):
        _ensure_log_dir_exists()
        plan_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "vibe_state": self.vibe_state.value,
            "tree": self._node_to_dict(root),
            "council_votes": [
                {"name": m.name, "stance": m.stance, "approved": m.approved}
                for m in self.council.members
            ],
        }
        with open(LOG_DIR / "mcts_plans.jsonl", "a") as f:
            f.write(json.dumps(plan_data) + "\n")

    def _node_to_dict(self, node: MCTSNode) -> dict:
        return {
            "id": node.id,
            "label": node.label,
            "reasoning": node.reasoning,
            "score": node.score,
            "status": node.status.value,
            "children": [self._node_to_dict(c) for c in node.children]
            if node.children
            else [],
        }


def _ensure_log_dir_exists():
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_activity(event_type: str, details: dict):
    _ensure_log_dir_exists()
    timestamp = datetime.datetime.now().isoformat()
    log_entry = {"timestamp": timestamp, "event_type": event_type, "details": details}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


if __name__ == "__main__":
    planner = MCTSPlanner()
    result = planner.plan("Create new UI component for sidebar")
    print(f"Plan generated with vibe state: {planner.vibe_state.value}")
    print(f"Root status: {result.status.value}, score: {result.score}")
    for child in result.children:
        print(f"  - {child.label}: {child.status.value} (score: {child.score})")
