"""Council supervisor — classify user input and route tasks to agents.

The Council does not execute work itself (per the product spec). It runs a fixed
loop:

  ANALYZE     decompose input into tasks
  PRIORITIZE  run trivial tasks inline
  ROUTE       dispatch complex tasks to a specialist agent
  VERIFY      gate results before they are returned

The agent backend is injectable so the routing logic can be tested without
hitting real model APIs. The default backend maps each agent role onto the
existing gateway LLM client (``gateway.llm_client.call_llm``).
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger("kitty.council")

# Agent roles named in the Council config.
AGENT_DEEPSEEK = "deepseek"  # Logic / Code
AGENT_CLAUDE = "claude"  # Synthesis / Planning
AGENT_OLLAMA = "ollama"  # CLI / Routine


@dataclass
class TaskDispatch:
    """The only contract an agent receives. Self-contained by design."""

    task_id: str
    priority: str
    assigned_to: str
    instructions: str
    context: dict = field(default_factory=dict)


@dataclass
class TaskResult:
    task_id: str
    assigned_to: str
    output: str
    ok: bool


class AgentBackend(Protocol):
    """Anything that can execute a dispatched task and return text."""

    def run(self, agent: str, dispatch: TaskDispatch) -> str: ...


# v1 classifier is rule-based: deterministic and zero-latency. Each category maps
# to one agent role from the config.
_CODING = re.compile(r"\b(implement|refactor|bug|test|function|class|pr|code|debug|fix)\b", re.I)
_RESEARCH = re.compile(r"\b(research|find|summari[sz]e|compare|investigate|survey|lookup)\b", re.I)
_WRITING = re.compile(r"\b(write|draft|doc|explain|plan|describe|outline)\b", re.I)
_ROUTINE = re.compile(r"\b(run|execute|shell|cli|cron|restart|start|stop|status)\b", re.I)
_TRIVIAL = re.compile(r"\b(what|list|show|how many|where is|which port)\b", re.I)


def classify(task: str) -> tuple[str, str, str]:
    """Return ``(category, agent, priority)`` for a single task string."""
    if _CODING.search(task):
        return ("coding", AGENT_DEEPSEEK, "high")
    if _RESEARCH.search(task):
        return ("research", AGENT_CLAUDE, "medium")
    if _WRITING.search(task):
        return ("writing", AGENT_CLAUDE, "medium")
    if _ROUTINE.search(task):
        return ("routine", AGENT_OLLAMA, "low")
    # Default: synthesis / triage via Claude.
    return ("general", AGENT_CLAUDE, "medium")


def is_trivial(task: str) -> bool:
    """True when the Council can answer inline without an agent."""
    return bool(_TRIVIAL.search(task)) and not _CODING.search(task)


def decompose(user_input: str) -> list[str]:
    """Split input into task strings. v1: on newlines and 'and'/'then'."""
    parts = re.split(r"[\n]|\band\b|\bthen\b", user_input)
    return [p.strip() for p in parts if p.strip()]


def _default_backend() -> AgentBackend:
    """Map each agent role to a model hint and call the gateway LLM hub."""
    from gateway.llm_client import call_llm

    hints = {
        AGENT_DEEPSEEK: "deepseek/deepseek-v4-flash",
        AGENT_CLAUDE: "kitty-sonnet",
        AGENT_OLLAMA: "kitty-default",
    }

    class LlmBackend:
        def run(self, agent: str, dispatch: TaskDispatch) -> str:
            messages = [
                {"role": "system", "content": f"You are the {agent} agent."},
                {"role": "user", "content": dispatch.instructions},
            ]
            return call_llm(messages, model=hints.get(agent))

    return LlmBackend()


def council_route(
    user_input: str,
    *,
    backend: AgentBackend | None = None,
    state: str | None = None,
) -> list[TaskResult]:
    """ANALYZE -> PRIORITIZE -> ROUTE -> VERIFY. One result per task."""
    backend = backend or _default_backend()
    ctx = {"project": "kitty", "state": state or ""}
    results: list[TaskResult] = []

    for task in decompose(user_input):
        if is_trivial(task):
            # PRIORITIZE: handled inline. v1 returns a stub; wire to a local
            # lookup (ports, status) later.
            results.append(
                TaskResult(str(uuid.uuid4()), "council", f"[inline] {task}", ok=True)
            )
            continue

        category, agent, priority = classify(task)
        dispatch = TaskDispatch(
            task_id=str(uuid.uuid4()),
            priority=priority,
            assigned_to=agent,
            instructions=task,
            context={**ctx, "category": category},
        )
        try:
            out = backend.run(agent, dispatch)
        except Exception as e:  # fail loud, then surface
            logger.error("agent %s failed on task %s: %s", agent, dispatch.task_id, e)
            out = ""
        results.append(TaskResult(dispatch.task_id, agent, out, ok=bool(out)))

    return _verify(results)


def _verify(results: list[TaskResult]) -> list[TaskResult]:
    """Gate results: warn on empty outputs (fail loud, never mask)."""
    for r in results:
        if not r.output:
            logger.warning("task %s (%s) produced no output", r.task_id, r.assigned_to)
    return results
