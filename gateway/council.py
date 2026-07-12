"""Council supervisor — classify, route to agents, then synthesize one answer.

The Council does not execute work itself (per the product spec). It runs a fixed
loop and ends with SYNTHESIZE so the user gets ONE coherent reply, not raw agent
fragments:

  ANALYZE     decompose input into tasks (split on newlines / 'then', not 'and')
  ROUTE       score-based classify -> dispatch each task to a specialist agent
  VERIFY      flag empty/failed outputs (fail loud, never mask)
  SYNTHESIZE  combine agent outputs into a single answer, tailored to user state

The agent backend is injectable so the logic is testable without real model APIs.
The default backend maps each agent role onto gateway.llm_client.call_llm and adds
a synthesis pass.
"""

from __future__ import annotations

import logging
import re
import time
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


@dataclass
class CouncilOutput:
    """What the Council returns: the final answer plus the raw agent results."""

    answer: str
    results: list[TaskResult]
    routing: list[dict] = field(default_factory=list)
    timings: list[dict] = field(default_factory=list)
    total_ms: float = 0.0


class AgentBackend(Protocol):
    """Anything that can execute a dispatched task and synthesize a final answer."""

    def run(self, agent: str, dispatch: TaskDispatch) -> str: ...

    def synthesize(self, question: str, parts: list[TaskResult], state: str) -> str: ...


# v1 classifier is rule-based but SCORED, not first-match. Each category counts
# keyword hits; the highest score wins. "test" is excluded from coding so
# "test the API" routes to research, not a code agent.
_CATEGORY_PATTERNS: dict[str, re.Pattern[str]] = {
    "coding": re.compile(r"\b(implement|refactor|bug|function|class|pr|debug|fix|code|script)\b", re.I),
    "research": re.compile(r"\b(research|find|summari[sz]e|compare|investigate|survey|lookup)\b", re.I),
    "writing": re.compile(r"\b(write|draft|doc|explain|plan|describe|outline)\b", re.I),
    "routine": re.compile(r"\b(run|execute|shell|cli|cron|restart|start|stop|status)\b", re.I),
}
_AGENT_FOR = {
    "coding": AGENT_DEEPSEEK,
    "research": AGENT_CLAUDE,
    "writing": AGENT_CLAUDE,
    "routine": AGENT_OLLAMA,
}
_PRIORITY_FOR = {"coding": "high", "research": "medium", "writing": "medium", "routine": "low"}

# Code-gen guard: a request to *produce* code must reach the code agent even when
# it also reads as "writing", overriding the writing/coding tie that would otherwise
# route "write a python script" to Claude.
_CODEGEN = re.compile(
    r"\b(write|implement|create|build|make)\b.{0,20}\b(script|program|function|code|api|class|module|app|bot)\b",
    re.I,
)

# Weak referents that signal a later segment depends on a prior one.
_REFERENT = re.compile(r"\b(it|this|that|these|those|how it works|the above|the previous)\b", re.I)

# Concrete nouns that make a segment self-contained even if it uses a referent.
_CONCRETE = re.compile(
    r"\b(csv|file|script|function|code|data|list|api|table|result|output|text|string|model|service|app)\b",
    re.I,
)

# Patterns that mean an "answer" is actually a clarification question / refusal.
_CLARIFY = re.compile(
    r"(could you clarify|please specify|can you clarify|i'm unable to|i cannot help|i can't help|what would you like)",
    re.I,
)


def classify(task: str) -> tuple[str, str, str]:
    """Return ``(category, agent, priority)`` by keyword score, not first match.

    Ties that include a Claude (synthesis) category resolve to Claude, so
    "explain the code" or "fix the docs" reach planning, not a code agent.
    """
    # Code-gen guard fires first so producing code always reaches the code agent.
    if _CODEGEN.search(task):
        return ("coding", AGENT_DEEPSEEK, "high")
    scores = {cat: len(p.findall(task)) for cat, p in _CATEGORY_PATTERNS.items()}
    top = max(scores.values())
    if top == 0:
        return ("general", AGENT_CLAUDE, "medium")
    winners = [c for c, s in scores.items() if s == top]
    if "coding" in winners and ("writing" in winners or "research" in winners):
        cat = "writing" if "writing" in winners else "research"
    else:
        cat = winners[0]
    return (cat, _AGENT_FOR[cat], _PRIORITY_FOR[cat])


def decompose(user_input: str) -> list[str]:
    """Split input into task strings. v1: on newlines, 'then', and ';' — NOT 'and'
    (coordinating conjunctions usually join a single task, not two)."""
    parts = re.split(r"[\n;]|\bthen\b", user_input)
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
            ctx = dispatch.context or {}
            system = f"You are the {agent} agent."
            if ctx:
                ctx_lines = "\n".join(f"- {k}: {v}" for k, v in ctx.items())
                system += (
                    "\nContext (use it; do not ask the user to repeat it):\n"
                    f"{ctx_lines}"
                )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": dispatch.instructions},
            ]
            return call_llm(messages, model=hints.get(agent))

        def synthesize(self, question: str, parts: list[TaskResult], state: str) -> str:
            # Single healthy task: return its output directly (no extra call).
            if len(parts) == 1 and parts[0].ok:
                return parts[0].output
            blocks = []
            for p in parts:
                if p.ok:
                    blocks.append(f"[{p.assigned_to} / ok]\n{p.output}")
                else:
                    # Don't feed a clarification/refusal back in — it would poison
                    # the merged answer. State the gap, not the noise.
                    blocks.append(f"[{p.assigned_to} / FAILED]\n[FAILED] task produced no usable output")
            system = (
                "You are the Council supervisor. Combine the specialist outputs "
                "below into ONE coherent answer to the user's request. If a "
                "specialist failed, state clearly what could not be done. Be concise."
            )
            if state:
                system += f"\nUser context (personal, use it): {state}"
            messages = [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        f"Request: {question}\n\nSpecialist outputs:\n"
                        + "\n\n".join(blocks)
                    ),
                },
            ]
            return call_llm(messages, model="kitty-sonnet")

    return LlmBackend()


def council_route(
    user_input: str,
    *,
    backend: AgentBackend | None = None,
    state: str | None = None,
) -> CouncilOutput:
    """ANALYZE -> ROUTE -> VERIFY -> SYNTHESIZE. Returns one final answer + raw results."""
    # Greeting short-circuit: exact greetings get an instant answer, no model call.
    # Narrow on purpose (fullmatch + greeting-only vocab) so real prompts are never masked.
    if _is_greeting(user_input):
        return CouncilOutput(
            answer="Hello! Tell me what to build, research, or run.",
            results=[],
            routing=[],
            timings=[],
            total_ms=0.0,
        )

    backend = backend or _default_backend()
    ctx = {"project": "kitty", "state": state or ""}
    results: list[TaskResult] = []
    routing: list[dict] = []
    timings: list[dict] = []
    total_start = time.perf_counter()

    prev_task: str | None = None
    for task in decompose(user_input):
        raw = task
        # Bind referent-only later segments to their antecedent so the agent never
        # has to resolve a dangling "it"/"this"/"how it works" on its own.
        if prev_task is not None and _is_referent_only(task):
            task = f'{task} — this refers to the previous task: "{prev_task}"'
        category, agent, priority = classify(task)
        dispatch = TaskDispatch(
            task_id=str(uuid.uuid4()),
            priority=priority,
            assigned_to=agent,
            instructions=task,
            context={
                **ctx,
                "category": category,
                **({"prior_task": prev_task} if prev_task else {}),
            },
        )
        start = time.perf_counter()
        try:
            out = backend.run(agent, dispatch)
        except Exception as e:  # fail loud, then surface
            logger.error("agent %s failed on task %s: %s", agent, dispatch.task_id, e)
            out = ""
        ms = (time.perf_counter() - start) * 1000
        ok = _is_answer_ok(out)
        results.append(TaskResult(dispatch.task_id, agent, out, ok))
        routing.append(
            {"task_id": dispatch.task_id, "category": category, "agent": agent, "priority": priority}
        )
        timings.append({"task_id": dispatch.task_id, "ms": round(ms, 2)})
        prev_task = raw

    total_ms = round((time.perf_counter() - total_start) * 1000, 2)
    results = _verify(results)
    answer = backend.synthesize(user_input, results, state or "")
    return CouncilOutput(
        answer=answer, results=results, routing=routing, timings=timings, total_ms=total_ms
    )


def _is_greeting(text: str) -> bool:
    return bool(
        re.fullmatch(r"(hi|hello|hey|yo|sup|thanks|thank you|ok|cool|nice)\b[!.]?", text.strip().lower())
    )


def _is_referent_only(task: str) -> bool:
    """True when a segment leans on a weak referent and names no concrete object."""
    if not _REFERENT.search(task):
        return False
    if _CONCRETE.search(task):
        return False
    return True


def _is_answer_ok(text: str) -> bool:
    """A usable answer, not a clarification question or refusal."""
    if not text or not text.strip():
        return False
    if _CLARIFY.search(text):
        return False
    # A bare short question (e.g. "Can you clarify?") is not an answer.
    if len(text.strip()) < 40 and text.strip().rstrip().endswith("?"):
        return False
    return True


def _verify(results: list[TaskResult]) -> list[TaskResult]:
    """Flag empty/failed outputs (fail loud, never mask)."""
    for r in results:
        if not r.output:
            logger.warning("task %s (%s) produced no output", r.task_id, r.assigned_to)
    return results
