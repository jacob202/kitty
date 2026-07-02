"""Autonomous Sub-Agent Runner — spawn agents that execute goals independently.

Agents are LLM-driven workers with a goal, a preset type, and an iteration budget.
They run in background asyncio tasks, recording progress to autonomy_state.db.
By default each agent works its goal through Kitty's explicit reasoning loop
(OBSERVE → ORIENT → DECIDE → ACT → VERIFY → LEARN), and the detected phase
is tagged onto each recorded step.

Agent presets (inspired by free-code's builtInAgents):
- explorer:   search and discover — wide research, finding sources, exploring topics
- planner:    break down a complex goal into ordered steps
- coder:      implement code changes (read-only analysis for now, write later)
- reviewer:   review code or output for issues, suggest improvements
- researcher: deep technical research with structured output

Public API:
  spawn(goal, agent_type, **opts) -> session_id
  get_status(session_id) -> dict
  get_output(session_id) -> str
  list_agents() -> list[dict]
  stop(session_id) -> bool
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger("kitty.agent_runner")

DEFAULT_MAX_ITERATIONS: int = 5
AGENT_TIMEOUT_SECONDS: int = 300  # 5 min hard cap per agent

# --- The Algorithm (reasoning loop, formerly gateway/algorithm.py) ---


@dataclass(frozen=True)
class Phase:
    """One step of the Algorithm: a name, the question it answers, what to do."""

    name: str
    intent: str
    guidance: str


PHASES: tuple[Phase, ...] = (
    Phase(
        "OBSERVE",
        "What is actually being asked?",
        "Restate the goal in your own words and gather the raw facts and "
        "context. No solutions yet.",
    ),
    Phase(
        "ORIENT",
        "What does it mean?",
        "Frame the problem: constraints, unknowns, assumptions, and what success would look like.",
    ),
    Phase(
        "DECIDE",
        "What's the plan?",
        "Choose one approach and list the concrete steps. Name the success "
        "criteria you'll check later.",
    ),
    Phase(
        "ACT", "Do it.", "Execute the chosen step. Show the work — code, commands, or reasoning."
    ),
    Phase(
        "VERIFY",
        "Did it work?",
        "Check the result against the success criteria from DECIDE. Be honest about gaps.",
    ),
    Phase(
        "LEARN",
        "What's worth keeping?",
        "Capture the one durable lesson or note, then give your final answer.",
    ),
)

PHASE_NAMES: tuple[str, ...] = tuple(p.name for p in PHASES)

_PHASE_MARKER = re.compile(r"PHASE:\s*([A-Za-z]+)", re.IGNORECASE)


def frame_prompt(base: str) -> str:
    """Append the Algorithm phase guide to a base system prompt."""
    lines = [
        base,
        "",
        "## The Algorithm",
        "Work the goal through these phases in order. Label each section with a "
        "`## PHASE: NAME` heading so your progress is legible:",
    ]
    for i, p in enumerate(PHASES, 1):
        lines.append(f"{i}. **{p.name}** — {p.intent} {p.guidance}")
    lines.append(
        "Skip a phase only if it genuinely doesn't apply. Loop back to an "
        "earlier phase if VERIFY surfaces a problem."
    )
    return "\n".join(lines)


def detect_phase(text: str) -> str | None:
    """Best-guess the phase from agent output. Last explicit PHASE: marker wins."""
    if not text:
        return None
    for name in reversed(_PHASE_MARKER.findall(text)):
        upper = name.upper()
        if upper in PHASE_NAMES:
            return upper
    return None


# --- Agent Preset Definitions ---

AGENT_PRESETS: dict[str, dict[str, Any]] = {
    "explorer": {
        "description": "Search and discover — wide research, finding sources, exploring topics",
        "system_prompt": (
            "You are an explorer agent for Kitty. Your job is research and discovery.\n"
            "Given a goal, search broadly, find relevant information, and return a "
            "concise summary of what you found with sources.\n"
            "Think step by step. Be thorough. Cite your reasoning."
        ),
        "model": None,  # uses route_model default
        "max_iterations": 3,
        "temperature": 0.5,
    },
    "planner": {
        "description": "Break down a complex goal into ordered, actionable steps",
        "system_prompt": (
            "You are a planner agent for Kitty. Your job is to break down complex "
            "goals into clear, ordered, actionable steps.\n"
            "For each step, include: what needs to happen, dependencies, and estimated effort.\n"
            "Output the plan as a numbered list with clear step descriptions."
        ),
        "model": None,
        "max_iterations": 2,
        "temperature": 0.4,
    },
    "coder": {
        "description": "Analyze and implement code changes",
        "system_prompt": (
            "You are a coder agent for Kitty. Your job is to analyze code and "
            "propose or implement changes.\n"
            "Explain your reasoning. Show the code changes clearly.\n"
            "Be precise. Consider edge cases."
        ),
        "model": None,
        "max_iterations": 5,
        "temperature": 0.2,
    },
    "reviewer": {
        "description": "Review code or output for issues and suggest improvements",
        "system_prompt": (
            "You are a reviewer agent for Kitty. Your job is to examine work "
            "and identify issues, risks, and improvement opportunities.\n"
            "Be constructive. Flag real problems, don't nitpick.\n"
            "Structure your review: what works, what needs attention, concrete suggestions."
        ),
        "model": None,
        "max_iterations": 2,
        "temperature": 0.3,
    },
    "researcher": {
        "description": "Deep technical research with structured output",
        "system_prompt": (
            "You are a researcher agent for Kitty. Your job is deep technical research.\n"
            "Analyze the topic thoroughly. Provide structured output with:\n"
            "1. Key findings\n2. Technical details\n3. Practical implications\n4. Open questions"
        ),
        "model": None,
        "max_iterations": 4,
        "temperature": 0.4,
    },
}


# --- Agent Runner ---


async def spawn(
    goal: str,
    agent_type: str = "explorer",
    *,
    model: Optional[str] = None,
    max_iterations: Optional[int] = None,
    temperature: Optional[float] = None,
    extra_context: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    algorithm: bool = True,
) -> int:
    """Spawn an autonomous agent. Returns the session_id for tracking.

    The agent runs as a background asyncio task. Use get_status() to check
    progress and get_output() to retrieve results.

    When ``algorithm`` is set (the default), the agent works the goal through
    Kitty's explicit reasoning loop (OBSERVE → … → LEARN); see ``algorithm.py``.
    """
    preset = AGENT_PRESETS.get(agent_type)
    if not preset:
        raise ValueError(f"Unknown agent type: {agent_type}. Available: {list(AGENT_PRESETS)}")

    model = model or preset["model"]
    max_iterations = int(max_iterations or preset["max_iterations"])
    temperature = temperature or preset["temperature"]
    system_prompt = preset["system_prompt"]

    if extra_context:
        system_prompt = f"{system_prompt}\n\nAdditional context:\n{extra_context}"

    # Create session in autonomy_state
    from gateway.autonomy_state import AutonomyState

    state = AutonomyState.start_new(f"[agent:{agent_type}] {goal}")
    session_id = state.session_id
    if session_id is None:
        raise RuntimeError("AutonomyState.start_new did not allocate a session_id")

    # Record metadata
    state.record_step(
        "system",
        content=json.dumps(
            {
                "agent_type": agent_type,
                "model": model,
                "max_iterations": max_iterations,
                "temperature": temperature,
                "metadata": metadata or {},
            }
        ),
    )

    # Launch background task
    asyncio.create_task(
        _run_agent_loop(
            session_id,
            goal,
            system_prompt,
            model,
            max_iterations,
            temperature,
            algorithm,
        )
    )

    logger.info("Agent spawned: type=%s session=%d goal=%s", agent_type, session_id, goal[:80])
    return session_id


async def _run_agent_loop(
    session_id: int,
    goal: str,
    system_prompt: str,
    model: Optional[str],
    max_iterations: int,
    temperature: float,
    use_algorithm: bool = True,
) -> None:
    """Core agent loop — runs in background, records all steps."""
    from gateway.autonomy_state import AutonomyState
    from gateway.llm_client import call_llm, route_model

    if use_algorithm:
        system_prompt = frame_prompt(system_prompt)

    state = AutonomyState(session_id=session_id)
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Goal: {goal}\n\nWork through this step by step. When you're done, give your final answer.",
        },
    ]

    model = model or route_model(goal)

    try:
        for iteration in range(max_iterations):
            t_start = time.monotonic()

            try:
                response = await asyncio.to_thread(
                    call_llm,
                    messages=messages,
                    model=model,
                    max_tokens=2000,
                    temperature=temperature,
                    timeout=60,
                    operation=f"agent.{session_id}",
                )
            except Exception as e:
                logger.error("Agent %d iteration %d failed: %s", session_id, iteration, e)
                state.record_step(
                    "error",
                    content=f"LLM call failed: {e}",
                    thinking="",
                )
                break

            elapsed = round((time.monotonic() - t_start) * 1000)
            thinking = f"Iteration {iteration + 1}/{max_iterations}, {elapsed}ms"
            if use_algorithm:
                phase = detect_phase(response)
                if phase:
                    thinking = f"[{phase}] {thinking}"
            state.record_step(
                "assistant",
                content=response,
                thinking=thinking,
            )

            messages.append({"role": "assistant", "content": response})

            # Check if the agent signals completion
            if _is_finished(response):
                logger.info("Agent %d finished after %d iterations", session_id, iteration + 1)
                break

        state.finish("completed")

    except asyncio.CancelledError:
        state.finish("cancelled")
        logger.info("Agent %d cancelled", session_id)
    except Exception:
        logger.exception("Agent %d crashed", session_id)
        state.finish("failed")


def _is_finished(response: str) -> bool:
    """Heuristic: does the response look like a final answer?"""
    lower = response.lower().strip()
    finish_markers = [
        "final answer:",
        "in conclusion",
        "to summarize",
        "here is my final",
        "this completes the",
    ]
    return any(m in lower for m in finish_markers)


# --- Query API ---


def get_status(session_id: int) -> dict[str, Any]:
    """Get the current status of an agent by session_id."""
    from gateway.autonomy_state import AutonomyState

    state = AutonomyState(session_id=session_id)
    history = state.get_history()

    if not history:
        return {"session_id": session_id, "status": "not_found"}

    # Find session row
    import sqlite3

    from gateway.autonomy_state import STATE_DB

    with sqlite3.connect(STATE_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM autonomy_sessions WHERE id = ?", (session_id,)).fetchone()

    status = row["status"] if row else "unknown"
    goal = row["goal"] if row else ""

    iterations = sum(1 for h in history if h.get("role") == "assistant")
    last_content = ""
    for h in reversed(history):
        if h.get("role") == "assistant" and h.get("content"):
            last_content = h["content"][:500]
            break

    return {
        "session_id": session_id,
        "status": status,
        "goal": goal,
        "iterations": iterations,
        "total_steps": len(history),
        "last_output_snippet": last_content,
    }


def get_output(session_id: int) -> str:
    """Get the full output from a completed or running agent."""
    from gateway.autonomy_state import AutonomyState

    state = AutonomyState(session_id=session_id)
    history = state.get_history()

    outputs = []
    for h in history:
        if h.get("role") == "assistant" and h.get("content"):
            outputs.append(h["content"])
    return "\n\n---\n\n".join(outputs)


def list_agents(limit: int = 20) -> list[dict[str, Any]]:
    """List recent agents, newest first."""
    import sqlite3

    from gateway.autonomy_state import STATE_DB, init_db

    init_db()

    with sqlite3.connect(STATE_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM autonomy_sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()

    agents = []
    for row in rows:
        sid = row["id"]
        goal = row["goal"] or ""
        agents.append(
            {
                "session_id": sid,
                "goal": goal,
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
    return agents


def stop(session_id: int) -> bool:
    """Request an agent to stop. Returns True if it was running."""
    import sqlite3

    from gateway.autonomy_state import STATE_DB

    with sqlite3.connect(STATE_DB) as conn:
        row = conn.execute(
            "SELECT status FROM autonomy_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row or row[0] != "active":
            return False
        conn.execute(
            "UPDATE autonomy_sessions SET status = 'cancelled', updated_at = ? WHERE id = ?",
            (time.time(), session_id),
        )
        conn.commit()
    logger.info("Agent %d marked cancelled", session_id)
    return True


async def await_completion(
    session_id: int,
    *,
    timeout: float = AGENT_TIMEOUT_SECONDS,
    poll: float = 5.0,
    on_poll: Optional[Callable[[dict[str, Any]], None]] = None,
) -> dict[str, Any]:
    """Poll agent status until terminal state or timeout.

    Interactive agents use spawn + get_status/get_output. Durable queued tasks
    should call this helper instead of duplicating poll loops.
    """
    elapsed = 0.0
    while elapsed < timeout:
        await asyncio.sleep(poll)
        elapsed += poll
        status = get_status(session_id)
        if on_poll:
            on_poll(status)
        if status["status"] in ("completed", "failed", "cancelled"):
            return status
    return get_status(session_id)


# Avoid circular import at module level
import json  # noqa: E402
