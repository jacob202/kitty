"""Prototype 1a — the ADR-0017 Mission as a hand-rolled Pydantic v2 model.

No PydanticAI, no LLM. This is the baseline: what does a minimal Kitty-owned
typed Mission cost, and what shape does it enforce?

Run: `python mission_pydantic.py`  (prints round-trip + validation results).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


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


class RiskTier(str, Enum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"


class Origin(BaseModel):
    conversation_id: str
    message_refs: list[str] = Field(default_factory=list)
    project_id: str | None = None
    repository: str
    base_sha: str
    context_receipt_ref: str

    @field_validator("base_sha")
    @classmethod
    def _sha_shape(cls, v: str) -> str:
        if len(v) != 40 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError("base_sha must be a 40-char lowercase hex SHA")
        return v


class Objective(BaseModel):
    outcome: str = Field(min_length=1)
    rationale: str
    non_goals: list[str] = Field(default_factory=list)


class Assumption(BaseModel):
    claim: str
    evidence: str | None = None
    disposition: Literal["accepted", "risky", "unverified"] = "unverified"


class Context(BaseModel):
    required_refs: list[str] = Field(default_factory=list)
    selected_refs: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)


class Execution(BaseModel):
    strategy: Literal[
        "direct", "retrieval", "research", "tools", "records", "experts", "builder"
    ]
    packets: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    allowed_paths: list[str] = Field(default_factory=list)
    forbidden_operations: list[str] = Field(default_factory=list)
    worker_constraints: dict[str, str] = Field(default_factory=dict)
    routing_policy: str | None = None


class Approval(BaseModel):
    approver: str
    approved_at: datetime
    scope: str


class Authority(BaseModel):
    risk_tier: RiskTier
    policy_version: str
    approvals: list[Approval] = Field(default_factory=list)
    expires_at: datetime | None = None


class Budgets(BaseModel):
    max_attempts: int = Field(ge=1, le=100)
    max_time_seconds: int | None = Field(default=None, ge=1)
    max_tokens: int | None = Field(default=None, ge=1)
    max_cost_usd: float | None = Field(default=None, ge=0)


class EvidencePlan(BaseModel):
    acceptance_criteria: list[str] = Field(min_length=1)
    validation_commands: list[str] = Field(default_factory=list)
    required_artifacts: list[str] = Field(default_factory=list)
    independent_review: bool = False


class Mission(BaseModel):
    """ADR-0017 Mission, v1. Ships as a plain Pydantic model — no dep on frameworks."""

    model_config = ConfigDict(extra="forbid", frozen=False)

    schema_version: Literal[1] = 1
    mission_id: str = Field(pattern=r"^[A-Z]+-\d+$")
    created_at: datetime
    approved_at: datetime | None = None
    origin: Origin
    objective: Objective
    context: Context = Field(default_factory=Context)
    execution: Execution
    authority: Authority
    budgets: Budgets
    evidence_plan: EvidencePlan
    state: MissionState = MissionState.proposed


def _demo() -> None:
    now = datetime.now(timezone.utc)
    mission = Mission(
        mission_id="RECON-001",
        created_at=now,
        origin=Origin(
            conversation_id="conv_abc",
            message_refs=["msg_1", "msg_2"],
            repository="jacob202/kitty",
            base_sha="e0a7fb69d251c01654f5c3e335d50e9f6bf680b5",
            context_receipt_ref="receipt_abc",
        ),
        objective=Objective(
            outcome="Evaluate PydanticAI vs plain Pydantic for the Kitty Mission contract",
            rationale="ADR-0017 ratifies the schema; nothing has been built yet",
            non_goals=["Adopt PydanticAI without evidence"],
        ),
        execution=Execution(strategy="research"),
        authority=Authority(risk_tier=RiskTier.T0, policy_version="v1"),
        budgets=Budgets(max_attempts=3, max_time_seconds=1200),
        evidence_plan=EvidencePlan(acceptance_criteria=["Reversible", "Reproducible"]),
    )

    # 1. Round-trip via JSON — the on-the-wire form Builder would receive.
    on_wire = mission.model_dump_json()
    parsed = Mission.model_validate_json(on_wire)
    assert parsed == mission, "round-trip mismatch"
    print(f"[proto1a] round-trip: OK  ({len(on_wire)} chars)")

    # 2. Reject unknown fields — extra='forbid' catches silent shape drift.
    payload = mission.model_dump()
    payload["state"] = "proposed"
    payload["extra_field"] = "should-fail"
    try:
        Mission.model_validate(payload)
        raise SystemExit("expected extra='forbid' to reject unknown fields")
    except ValidationError as exc:
        assert "extra_field" in str(exc)
        print(f"[proto1a] unknown-field rejection: OK")

    # 3. Reject a bad SHA — the field validator earns its keep.
    bad = mission.model_dump()
    bad["origin"]["base_sha"] = "not-a-sha"
    try:
        Mission.model_validate(bad)
        raise SystemExit("expected SHA validator to reject non-hex")
    except ValidationError as exc:
        assert "base_sha" in str(exc)
        print(f"[proto1a] bad-SHA rejection: OK")

    # 4. State machine enum coverage.
    for s in MissionState:
        m = mission.model_copy(update={"state": s})
        assert m.state == s
    print(f"[proto1a] state enum coverage: OK  ({len(list(MissionState))} states)")

    # 5. Missing required field — fail loud (Article I).
    try:
        Mission.model_validate({"schema_version": 1})
        raise SystemExit("expected validation to reject minimal payload")
    except ValidationError as exc:
        assert "objective" in str(exc) or "mission_id" in str(exc)
        print(f"[proto1a] missing-required rejection: OK")

    print("[proto1a] all checks pass — plain Pydantic Mission is viable.")


if __name__ == "__main__":
    _demo()
