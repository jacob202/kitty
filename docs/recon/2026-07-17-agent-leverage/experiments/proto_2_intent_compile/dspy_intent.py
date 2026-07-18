"""Prototype 2 — DSPy Signature for compiling messy Jacob prose into a Mission spec.

Two paths:
  A. Offline structural test  — proves the DSPy Signature + Module wire up and
     produce a valid MissionSummary from a canned dummy LM response.
  B. Live-eval rig            — a `run_live()` entry Jacob invokes with keys:
     OPENROUTER_API_KEY (cheap), ANTHROPIC_API_KEY (premium). Runs 5 messy
     inputs through cheap + premium DSPy modules, prints per-input metrics
     (structured-output-valid, unnecessary-question rate, wall-clock).

We don't fake numbers. Path A is what runs in this session.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

import dspy


# ---------- Signature: what Kitty asks Jacob's messy request to become ----------

class CompileMission(dspy.Signature):
    """Turn Jacob's spoken request into a precise Mission summary.

    Fail loudly:
    - if the objective isn't clear enough to act on, set missing_context and
      list one concrete question the user must answer;
    - never guess a strategy — return the shortest that would work.
    """
    request: str = dspy.InputField(desc="Jacob's raw message; may be terse, typo-heavy, non-linear")
    prior_context_available: bool = dspy.InputField(
        desc="Whether prior conversation context is loaded",
    )

    objective: str = dspy.OutputField(desc="One-sentence outcome; verb-first")
    proposed_method: str = dspy.OutputField(
        desc="Jacob's suggested approach if he offered one, else 'none'",
    )
    strategy: Literal["direct", "retrieval", "research", "tools", "records", "experts", "builder"] = (
        dspy.OutputField(desc="Shortest strategy that could satisfy the objective")
    )
    missing_context: list[str] = dspy.OutputField(
        desc="Facts Jacob must supply before acting; empty if none",
    )
    clarifying_question: str = dspy.OutputField(
        desc="At most one question, or 'none'. Ask only if missing_context is non-empty",
    )


# ---------- A. Offline structural test ----------

class _DummyLM(dspy.BaseLM):
    """A dummy LM that returns a fixed reply — proves the DSPy pipeline shape
    without needing any API. Used for structural tests only."""

    def __init__(self, canned: str) -> None:
        super().__init__(model="dummy/dummy")
        self.canned = canned
        self.call_count = 0

    def forward(self, prompt=None, messages=None, **kwargs) -> Any:
        self.call_count += 1
        # DSPy's BaseLM expects a litellm-like ModelResponse; usage must be a plain dict
        # because base_lm._process_lm_response does `dict(getattr(response, "usage", {}))`.
        return type(
            "R", (),
            {
                "choices": [type("C", (), {
                    "message": type("M", (), {"content": self.canned, "tool_calls": None})(),
                    "finish_reason": "stop",
                })()],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "model": "dummy",
                "id": "dummy-1",
            },
        )()


def _offline_check() -> None:
    # DSPy's ChatAdapter parses field-tagged text; use JSONAdapter for stricter parsing.
    canned = (
        "[[ ## objective ## ]]\n"
        "Compare DSPy structured outputs against plain LLM prompting on next_step\n\n"
        "[[ ## proposed_method ## ]]\n"
        "none\n\n"
        "[[ ## strategy ## ]]\n"
        "research\n\n"
        "[[ ## missing_context ## ]]\n"
        "[]\n\n"
        "[[ ## clarifying_question ## ]]\n"
        "none\n\n"
        "[[ ## completed ## ]]"
    )
    with dspy.context(lm=_DummyLM(canned), adapter=dspy.ChatAdapter()):
        module = dspy.Predict(CompileMission)
        result = module(
            request="figure out if dspy is worth it for next_step",
            prior_context_available=False,
        )
    print(f"[proto2/A] Signature.OutputField parse: OK")
    print(f"[proto2/A]   objective:  {result.objective}")
    print(f"[proto2/A]   strategy:   {result.strategy}")
    print(f"[proto2/A]   missing:    {result.missing_context}")
    print(f"[proto2/A]   question:   {result.clarifying_question}")
    assert result.strategy == "research"
    assert result.missing_context == []
    print(f"[proto2/A] structural pass — DSPy Signature/Module/Adapter wires up")


# ---------- B. Live-eval rig ----------

@dataclass
class LiveResult:
    request: str
    model_alias: str
    valid: bool
    strategy: str | None
    missing_count: int
    asked_question: bool
    wall_clock_s: float
    error: str | None = None


REPRESENTATIVE_JACOB_REQUESTS = [
    "ok so benefits like the CRA thing i think i need to file something",
    "figure out that job posting review thing before end of week",
    "hey the ui went weird when i clicked next steps on my phone earlier",
    "i want to remember that the mail thing broke again",
    "should i take that free udemy course thing you mentioned",
]


def run_live() -> list[LiveResult]:  # pragma: no cover — needs live keys
    """Run the same Signature against cheap + premium models.

    Requires at least one of:
      OPENROUTER_API_KEY   (kitty-default → deepseek-v4-flash, cheap)
      ANTHROPIC_API_KEY    (kitty-sonnet → claude-sonnet-4-6, premium)
    """
    import time

    results: list[LiveResult] = []

    lm_configs: list[tuple[str, dspy.LM]] = []
    if os.environ.get("OPENROUTER_API_KEY"):
        lm_configs.append((
            "cheap:deepseek-v4-flash",
            dspy.LM("openrouter/deepseek/deepseek-v4-flash", cache=False),
        ))
    if os.environ.get("ANTHROPIC_API_KEY"):
        lm_configs.append((
            "premium:claude-sonnet-4-6",
            dspy.LM("anthropic/claude-sonnet-4-6", cache=False),
        ))

    if not lm_configs:
        print("[proto2/B] skipped — no OPENROUTER_API_KEY or ANTHROPIC_API_KEY in env")
        return []

    for alias, lm in lm_configs:
        with dspy.context(lm=lm, adapter=dspy.ChatAdapter()):
            module = dspy.Predict(CompileMission)
            for request in REPRESENTATIVE_JACOB_REQUESTS:
                start = time.time()
                try:
                    out = module(request=request, prior_context_available=False)
                    results.append(LiveResult(
                        request=request,
                        model_alias=alias,
                        valid=True,
                        strategy=out.strategy,
                        missing_count=len(out.missing_context),
                        asked_question=out.clarifying_question.strip().lower() != "none",
                        wall_clock_s=round(time.time() - start, 2),
                    ))
                except Exception as exc:  # noqa: BLE001 — record everything
                    results.append(LiveResult(
                        request=request, model_alias=alias, valid=False,
                        strategy=None, missing_count=0, asked_question=False,
                        wall_clock_s=round(time.time() - start, 2),
                        error=f"{type(exc).__name__}: {exc}",
                    ))
    for r in results:
        print(f"[proto2/B] {r.model_alias:35}  strategy={r.strategy or '<fail>':10} "
              f"missing={r.missing_count} ask={r.asked_question} "
              f"{r.wall_clock_s:5.2f}s  err={r.error or '-'}")
    return results


if __name__ == "__main__":
    _offline_check()
    run_live()  # no-op if no keys
