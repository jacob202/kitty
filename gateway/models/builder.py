"""Pydantic models for the KittyBuilder control plane.

Models define Builder operator, worker-result, and agent-dispatch contracts.
The executable Mission contract is the canonical initiative manifest validated by
``gateway.builder_initiative`` rather than a parallel Pydantic dialect.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


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
    "AttemptResult",
    "BuilderCommandRequest",
    "ContextTier",
    "ReviewContract",
    "WorkerContextBundle",
    "WorkerContract",
]
