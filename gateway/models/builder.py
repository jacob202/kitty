"""Pydantic models for the KittyBuilder control plane.

Models correspond to the Mission object defined in ADR 0017 and the
execution-level contracts used by builder_runner and the companion
preset wiring.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MissionState(str, Enum):
    proposed = "proposed"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    accepted = "accepted"
    running = "running"
    blocked = "blocked"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"
    superseded = "superseded"


class AgentPreset(str, Enum):
    explorer = "explorer"
    planner = "planner"
    coder = "coder"
    reviewer = "reviewer"
    researcher = "researcher"


class ContextTier(str, Enum):
    trivial = "trivial"
    standard = "standard"
    deep = "deep"


class RiskTier(str, Enum):
    t0 = "t0"
    t1 = "t1"
    t2 = "t2"


# ---------------------------------------------------------------------------
# Mission models (ADR 0017)
# ---------------------------------------------------------------------------


class MissionOrigin(BaseModel):
    conversation_id: str | None = None
    message_refs: list[str] = Field(default_factory=list)
    project_id: str | None = None
    repository: str | None = None
    base_sha: str | None = None
    context_receipt_ref: str | None = None


class Assumption(BaseModel):
    claim: str
    evidence: str | None = None
    disposition: str | None = None


class MissionContext(BaseModel):
    required_refs: list[str] = Field(default_factory=list)
    selected_refs: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)


class MissionExecution(BaseModel):
    strategy: str | None = None
    packets: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    allowed_paths: list[str] = Field(default_factory=list)
    forbidden_operations: list[str] = Field(default_factory=list)
    worker_constraints: dict[str, Any] = Field(default_factory=dict)
    routing_policy: dict[str, Any] = Field(default_factory=dict)


class MissionAuthority(BaseModel):
    risk_tier: RiskTier = RiskTier.t2
    policy_version: str | None = None
    approvals: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class MissionBudgets(BaseModel):
    max_attempts: int = 3
    max_time_seconds: int = 3600
    max_tokens: int | None = None
    max_cost: float | None = None


class EvidenceCriterion(BaseModel):
    description: str
    validation_command: str | None = None


class MissionEvidencePlan(BaseModel):
    acceptance_criteria: list[EvidenceCriterion] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    required_artifacts: list[str] = Field(default_factory=list)
    independent_review: bool = False


class Mission(BaseModel):
    """A versioned Mission object — the durable command boundary between
    Kitty and KittyBuilder (ADR 0017)."""

    schema_version: int = 1
    mission_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=datetime.now)
    approved_at: datetime | None = None
    origin: MissionOrigin = Field(default_factory=MissionOrigin)
    objective: str
    rationale: str | None = None
    non_goals: list[str] = Field(default_factory=list)
    context: MissionContext = Field(default_factory=MissionContext)
    execution: MissionExecution = Field(default_factory=MissionExecution)
    authority: MissionAuthority = Field(default_factory=MissionAuthority)
    budgets: MissionBudgets = Field(default_factory=MissionBudgets)
    evidence_plan: MissionEvidencePlan = Field(default_factory=MissionEvidencePlan)
    state: MissionState = MissionState.proposed


class BuilderCommandRequest(BaseModel):
    """Canonical request shape for Kitty's Builder operator controls.

    The command route owns transport-specific response and audit behavior;
    Builder state remains behind the canonical command boundary.
    """

    action: str
    task_id: str | None = None
    initiative_id: str | None = None
    packet_id: str | None = None
    reason: str | None = None
    actor: str | None = None
    expected_version: int | None = None


# ---------------------------------------------------------------------------
# Worker context / contract models
# ---------------------------------------------------------------------------


class WorkerContextBundle(BaseModel):
    """The structured context injected into a builder worker environment."""

    task_id: str
    run_id: str
    branch: str
    brief_path: str | None = None
    bundle_path: str | None = None
    result_path: str | None = None
    context_manifest_path: str | None = None
    attempt_id: str | None = None
    agent_preset: AgentPreset | None = None
    model: str | None = None
    provider: str | None = None
    tier: ContextTier = ContextTier.standard
    allowed_paths: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


class WorkerContract(BaseModel):
    """Contract a worker writes to KB_RESULT_PATH after execution."""

    status: str
    summary: str | None = None
    diff_summary: str | None = None
    changed_paths: list[str] = Field(default_factory=list)
    validation_results: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ReviewContract(BaseModel):
    """Contract a reviewer writes to KB_REVIEW_RESULT_PATH."""

    verdict: str
    summary: str | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)


class AttemptResult(BaseModel):
    """Structured outcome of a single packet attempt."""

    attempt_id: int
    attempt_no: int
    outcome: str
    run_id: str | None = None
    run_state: str | None = None
    exit_code: int | None = None
    implementation_status: str | None = None
    validation_status: str | None = None
    review_verdict: str | None = None
    failure: str | None = None
    changed_paths: list[str] = Field(default_factory=list)
    scope_violations: list[str] = Field(default_factory=list)
    identity_findings: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent preset models (companion wiring)
# ---------------------------------------------------------------------------


class AgentPresetConfig(BaseModel):
    """Configuration for an agent preset that can be dispatched by the builder."""

    preset: AgentPreset
    description: str
    system_prompt: str
    model: str | None = None
    max_iterations: int = 3
    temperature: float = 0.3
    tier: ContextTier = ContextTier.standard
    timeout_seconds: int = 300


class AgentDispatchRequest(BaseModel):
    """Request to dispatch an agent via the companion wiring."""

    goal: str
    preset: AgentPreset
    task_id: str | None = None
    run_id: str | None = None
    extra_context: str | None = None
    model: str | None = None
    max_iterations: int | None = None
    temperature: float | None = None


class AgentDispatchResult(BaseModel):
    """Result from dispatching an agent."""

    session_id: int
    preset: AgentPreset
    goal: str
    status: str
    output: str | None = None
    error: str | None = None


__all__ = [
    "AgentDispatchRequest",
    "AgentDispatchResult",
    "AgentPreset",
    "AgentPresetConfig",
    "Assumption",
    "AttemptResult",
    "BuilderCommandRequest",
    "ContextTier",
    "EvidenceCriterion",
    "Mission",
    "MissionAuthority",
    "MissionBudgets",
    "MissionContext",
    "MissionEvidencePlan",
    "MissionExecution",
    "MissionOrigin",
    "MissionState",
    "ReviewContract",
    "RiskTier",
    "WorkerContextBundle",
    "WorkerContract",
]
