from __future__ import annotations

import re
from pathlib import Path

from src.builder.contracts import BuilderBrief

_VAGUE_PATTERNS = (
    "clean up everything",
    "cleanup everything",
    "make it better",
    "fix everything",
    "optimize everything",
    "improve the repo",
)

_COMMAND_PATTERNS = (
    "command",
    "slash",
    "/stuck",
    "/brief",
    "candidate c",
    "unified command",
)


def compile_intent(project_root: str | Path, raw_input: str) -> BuilderBrief:
    root = Path(project_root).expanduser().resolve()
    raw = (raw_input or "").strip()
    lower = raw.lower()

    context_targets = _context_targets(root, lower)
    forbidden_files: list[str] = []
    non_goals: list[str] = []
    ambiguities: list[str] = []
    assumptions = [
        "Use existing repo authority order and builder safety gates.",
        "Do not broaden scope without an approved spec.",
    ]

    if any(token in lower for token in ("do not do ui", "do not touch ui", "no ui", "ui polish")):
        forbidden_files.append("garage-ui/")
        non_goals.append("Do not change UI styling or polish.")

    if not raw:
        brief = BuilderBrief(
            raw_input=raw,
            normalized_goal="Clarify the requested target.",
            ambiguities=["No request text was provided."],
            blocking_question="What exact task should KittyBuilder handle first?",
            context_targets=context_targets,
            risk_level="high",
            recommended_execution_mode="human_question",
            confidence=0.0,
        )
        return _with_packet(brief, stage="intake")

    if any(pattern in lower for pattern in _VAGUE_PATTERNS):
        ambiguities.append("The request is too broad to execute safely.")
        brief = BuilderBrief(
            raw_input=raw,
            normalized_goal="Clarify the requested cleanup target.",
            non_goals=non_goals,
            ambiguities=ambiguities,
            blocking_question="What single concrete target should KittyBuilder improve first?",
            context_targets=context_targets,
            risk_level="high",
            recommended_execution_mode="human_question",
            handoff_prompt="Ask one scoping question before any execution.",
            confidence=0.25,
        )
        return _with_packet(brief, stage="intake")

    normalized_goal = _goal_from_text(lower)
    mode = _recommended_mode(lower)
    success_criteria = ["Implementation follows the compiled goal without scope expansion."]
    validation_commands = _validation_commands(root, lower)

    if "and" in lower and sum(1 for pat in _COMMAND_PATTERNS if pat in lower) >= 2 and "also" in lower:
        ambiguities.append("Request may include multiple command slices.")

    brief = BuilderBrief(
        raw_input=raw,
        normalized_goal=normalized_goal,
        non_goals=non_goals,
        success_criteria=success_criteria,
        validation_commands=validation_commands,
        allowed_files=[],
        forbidden_files=list(dict.fromkeys(forbidden_files)),
        assumptions=assumptions,
        ambiguities=ambiguities,
        blocking_question="",
        context_targets=context_targets,
        risk_level="medium" if mode != "parallel_workers" else "high",
        recommended_execution_mode=mode,
        handoff_prompt=f"Execute this scoped goal: {normalized_goal}",
        confidence=0.78 if mode != "human_question" else 0.25,
    )
    return _with_packet(brief, stage="intent_compiled")


def _goal_from_text(lower: str) -> str:
    if any(pat in lower for pat in _COMMAND_PATTERNS):
        return "Advance the Unified Command System through KittyBuilder with verification."
    if "kittybuilder" in lower:
        return "Improve KittyBuilder control-layer behavior with verification."
    if "research" in lower:
        return "Run focused research and summarize with sources."
    return "Compile the request into one scoped, verifiable KittyBuilder task."


def _recommended_mode(lower: str):
    if "research" in lower or "analyze" in lower:
        return "scout"
    if "parallel" in lower and "independent" in lower:
        return "parallel_workers"
    if "verify" in lower or "test" in lower or "works" in lower:
        return "single_worker"
    return "intake_only"


def _validation_commands(root: Path, lower: str) -> list[str]:
    commands: list[str] = []
    gate = root / "scripts" / "run_gates.sh"
    if gate.is_file():
        commands.append("bash scripts/run_gates.sh")
    if "command" in lower:
        commands.append("venv/bin/python -m pytest tests/test_kitty_builder.py -q --tb=short")
    return commands


def _context_targets(root: Path, lower: str) -> list[str]:
    targets = [
        "CURRENT_FOCUS.md",
        "TASKS.md",
        "docs/LAYER0_CONTROL_PLANE.md",
        "docs/DECISIONS.md",
    ]
    if any(pat in lower for pat in _COMMAND_PATTERNS):
        spec = root / "specs" / "unified-command-system-candidate-c.spec.md"
        if spec.is_file():
            targets.append("specs/unified-command-system-candidate-c.spec.md")
    return list(dict.fromkeys(targets))


def _with_packet(brief: BuilderBrief, *, stage: str) -> BuilderBrief:
    packet = build_next_agent_packet(brief, stage=stage)
    return BuilderBrief(
        raw_input=brief.raw_input,
        normalized_goal=brief.normalized_goal,
        non_goals=list(brief.non_goals),
        success_criteria=list(brief.success_criteria),
        validation_commands=list(brief.validation_commands),
        allowed_files=list(brief.allowed_files),
        forbidden_files=list(brief.forbidden_files),
        assumptions=list(brief.assumptions),
        ambiguities=list(brief.ambiguities),
        blocking_question=brief.blocking_question,
        context_targets=list(brief.context_targets),
        risk_level=brief.risk_level,
        recommended_execution_mode=brief.recommended_execution_mode,
        handoff_prompt=brief.handoff_prompt,
        confidence=brief.confidence,
        next_agent_packet=packet,
    )


def build_next_agent_packet(brief: BuilderBrief, *, stage: str) -> dict[str, object]:
    """Build a deterministic, compact packet for the next agent in the chain."""
    output_contract = [
        "Return files changed.",
        "Return commands run.",
        "Return tests run with pass/fail.",
        "Return blockers and residual risks.",
        "Return one next action for the following agent.",
    ]
    if brief.recommended_execution_mode == "human_question":
        output_contract = [
            "Ask exactly one blocking question.",
            "Do not write code.",
            "Wait for answer before execution.",
        ]

    return {
        "schema_version": "builder_handoff.v1",
        "stage": stage,
        "objective": brief.normalized_goal,
        "recommended_mode": brief.recommended_execution_mode,
        "must_do": list(dict.fromkeys(brief.success_criteria + brief.assumptions)),
        "must_not_do": list(dict.fromkeys(brief.non_goals + brief.forbidden_files)),
        "context_targets": list(brief.context_targets),
        "validation_commands": list(brief.validation_commands),
        "blocking_question": brief.blocking_question,
        "output_contract": output_contract,
        "next_prompt": _next_prompt(brief),
    }


def _next_prompt(brief: BuilderBrief) -> str:
    lines = [
        "You are the next worker in KittyBuilder.",
        f"Objective: {brief.normalized_goal}",
        f"Mode: {brief.recommended_execution_mode}",
    ]
    if brief.context_targets:
        lines.append("Read context targets first: " + ", ".join(brief.context_targets))
    if brief.validation_commands:
        lines.append("Validation commands: " + " ; ".join(brief.validation_commands))
    if brief.blocking_question:
        lines.append("Blocking question: " + brief.blocking_question)
    if brief.handoff_prompt:
        lines.append("Execution note: " + brief.handoff_prompt)
    lines.append("Output must follow the output_contract exactly.")
    return "\n".join(lines)
