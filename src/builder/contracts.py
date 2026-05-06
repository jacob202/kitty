from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

RiskLevel = Literal["low", "medium", "high"]
ExecutionMode = Literal[
    "answer_only",
    "intake_only",
    "scout",
    "single_worker",
    "parallel_workers",
    "review_gate",
    "human_question",
]


@dataclass(frozen=True)
class BuilderBrief:
    raw_input: str
    normalized_goal: str
    non_goals: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    validation_commands: list[str] = field(default_factory=list)
    allowed_files: list[str] = field(default_factory=list)
    forbidden_files: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)
    blocking_question: str = ""
    context_targets: list[str] = field(default_factory=list)
    risk_level: RiskLevel = "medium"
    recommended_execution_mode: ExecutionMode = "intake_only"
    handoff_prompt: str = ""
    confidence: float = 0.0
    next_agent_packet: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
