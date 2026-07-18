"""Prototype 1b — the same ADR-0017 Mission via PydanticAI Agent.

Two evidence tracks, both without a live API call:

A. Structural surface only — Agent(output_type=Mission) constructs, schema
   introspection works, retry/output_validator/tool_plain register.
B. FunctionModel forces a schema-valid Mission payload to prove the
   structured-output pipeline wires end-to-end.

Also documents the finding from the first run: TestModel's default synthesis
is NOT schema-aware, so strict Pydantic constraints (e.g. mission_id pattern
`^[A-Z]+-\\d+$`) cause `UnexpectedModelBehavior: Exceeded maximum output
retries (1)`. A live LLM has the same failure mode — the retry budget is the
gate.

Run: `python mission_pydantic_ai.py`
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(__file__.rsplit("/", 1)[0]))
from mission_pydantic import Mission  # noqa: E402

from pydantic_ai import Agent, ModelRetry  # noqa: E402
from pydantic_ai.messages import ModelResponse, TextPart  # noqa: E402
from pydantic_ai.models.function import AgentInfo, FunctionModel  # noqa: E402


# ---------- A. Structural surface ----------

def _agent_construction() -> None:
    agent = Agent(
        model=FunctionModel(function=lambda *_a, **_k: None),  # placeholder, not called
        output_type=Mission,
        instructions=(
            "Compile Jacob's messy request into an ADR-0017 Mission. "
            "Assume repo=jacob202/kitty, base_sha=<current HEAD SHA>."
        ),
    )
    # Just prove the object exists.
    assert agent is not None
    print("[proto1b/A] Agent(output_type=Mission) constructs: OK")

    # Register an output_validator (this is a PydanticAI-only concept).
    @agent.output_validator
    def _must_have_objective(m: Mission) -> Mission:
        if len(m.objective.outcome) < 10:
            raise ModelRetry("objective.outcome too short — needs at least 10 chars")
        return m

    print("[proto1b/A] output_validator + ModelRetry registered: OK")

    # Register a tool.
    @agent.tool_plain
    def approve_mission(mission_id: str, approver: str) -> str:
        """Kitty-approves a Mission. Only Jacob may call this."""
        return f"approved:{mission_id}:{approver}"

    print("[proto1b/A] tool_plain registration: OK")


# ---------- B. Wire end-to-end with FunctionModel ----------

_VALID_MISSION_JSON = json.dumps({
    "schema_version": 1,
    "mission_id": "RECON-002",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "approved_at": None,
    "origin": {
        "conversation_id": "conv_abc",
        "message_refs": ["msg_1"],
        "project_id": None,
        "repository": "jacob202/kitty",
        "base_sha": "e0a7fb69d251c01654f5c3e335d50e9f6bf680b5",
        "context_receipt_ref": "receipt_abc",
    },
    "objective": {
        "outcome": "Prove PydanticAI structured-output wiring works with a strict Mission schema",
        "rationale": "Cheapest evidence first",
        "non_goals": ["Adopt PydanticAI without measuring against plain Pydantic"],
    },
    "context": {
        "required_refs": [], "selected_refs": [], "missing": [],
        "contradictions": [], "assumptions": [],
    },
    "execution": {
        "strategy": "research", "packets": [], "dependencies": [],
        "allowed_paths": [], "forbidden_operations": [],
        "worker_constraints": {}, "routing_policy": None,
    },
    "authority": {
        "risk_tier": "T0",
        "policy_version": "v1",
        "approvals": [],
        "expires_at": None,
    },
    "budgets": {
        "max_attempts": 3, "max_time_seconds": 1200,
        "max_tokens": None, "max_cost_usd": None,
    },
    "evidence_plan": {
        "acceptance_criteria": ["Structural"],
        "validation_commands": [], "required_artifacts": [],
        "independent_review": False,
    },
    "state": "proposed",
})


def _emit_valid_mission(_messages, _info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content=_VALID_MISSION_JSON)])


def _end_to_end() -> None:
    agent = Agent(
        model=FunctionModel(function=_emit_valid_mission),
        output_type=Mission,
    )
    result = agent.run_sync("compile this into a mission")
    assert isinstance(result.output, Mission)
    assert result.output.mission_id == "RECON-002"
    print(f"[proto1b/B] end-to-end structured output via FunctionModel: OK "
          f"(mission_id={result.output.mission_id}, state={result.output.state.value})")

    # Schema PydanticAI would inject into the prompt.
    schema = Mission.model_json_schema()
    schema_str = json.dumps(schema)
    print(f"[proto1b/B] injected JSON schema size: {len(schema_str)} chars "
          f"(~{len(schema_str) // 4} tokens of prompt overhead per call)")


def _record_test_model_finding() -> None:
    """Documented finding from prior run — kept as a comment so the reason is stable."""
    print("[proto1b/finding] TestModel synthesizes non-schema-aware data. Strict Pydantic")
    print("[proto1b/finding]   constraints cause UnexpectedModelBehavior after 1 retry.")
    print("[proto1b/finding]   Implication: a real LLM will also miss strict patterns")
    print("[proto1b/finding]   sometimes; the retry budget is the gate. PydanticAI default")
    print("[proto1b/finding]   is retries=1; bump to 3+ for strict Mission-shaped outputs")
    print("[proto1b/finding]   or relax the pattern. Trade: repair cost vs strictness.")


if __name__ == "__main__":
    _agent_construction()
    _end_to_end()
    _record_test_model_finding()
