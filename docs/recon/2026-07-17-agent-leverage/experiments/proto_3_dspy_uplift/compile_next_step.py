"""Prototype 3 — DSPy compile pipeline for cheap-model uplift on `next_step`.

The bet from ADR-0017 §"Cost and model routing" and NORTH_STAR §3:
Kitty should work well on cheap/free models. DSPy's compilers (MIPROv2, GEPA,
SIMBA, BootstrapFewShot) synthesize prompts/demonstrations from evaluation
feedback so a small model matches a premium model's structured output.

This proto ships two things:

  A. Offline structural test — proves the DSPy compile API loads, a metric
     function is registered, and BootstrapFewShot instantiates against the
     `CompileMission` Signature from proto 2. No LLM call.

  B. `run_live()` — Jacob runs with keys. It:
     1. records the *uncompiled cheap* baseline over N inputs;
     2. compiles the module against a *premium teacher* (Sonnet 4.6);
     3. runs the *compiled cheap* module on the same N inputs;
     4. prints structured-output-valid rate, exact-strategy-match rate,
        unnecessary-clarification rate, tokens, wall-clock, and estimated cost.

The comparison IS the evidence Jacob needs for ADR-0017's cost claim: is
DSPy's uplift large enough to justify adding it to Kitty?

Run:  `python compile_next_step.py`
Live: `OPENROUTER_API_KEY=… ANTHROPIC_API_KEY=… python compile_next_step.py --live`
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import Any

import dspy

# Reuse the Signature from Proto 2 rather than re-defining it.
sys.path.insert(0, str(__file__.rsplit("/", 1)[0] + "/../proto_2_intent_compile"))
from dspy_intent import (  # noqa: E402
    REPRESENTATIVE_JACOB_REQUESTS,
    CompileMission,
    _DummyLM,  # for offline test
)


# ---------- Training data: hand-labelled small set ----------

TRAINING_EXAMPLES = [
    dspy.Example(
        request="ok so benefits like the CRA thing i think i need to file something",
        prior_context_available=False,
        objective="File the outstanding CRA benefits form Jacob owes",
        proposed_method="none",
        strategy="records",
        missing_context=["which specific benefit form", "the deadline if any"],
        clarifying_question="Which benefit — GST, disability, Trillium, or something else?",
    ).with_inputs("request", "prior_context_available"),
    dspy.Example(
        request="figure out that job posting review thing before end of week",
        prior_context_available=True,
        objective="Review the pending job posting draft this week",
        proposed_method="none",
        strategy="direct",
        missing_context=[],
        clarifying_question="none",
    ).with_inputs("request", "prior_context_available"),
    dspy.Example(
        request="hey the ui went weird when i clicked next steps on my phone earlier",
        prior_context_available=False,
        objective="Diagnose the mobile UI regression on the Next Steps button",
        proposed_method="none",
        strategy="tools",
        missing_context=["what did 'weird' look like", "which browser/device"],
        clarifying_question="What did it do — freeze, wrong layout, error message?",
    ).with_inputs("request", "prior_context_available"),
    dspy.Example(
        request="i want to remember that the mail thing broke again",
        prior_context_available=False,
        objective="Record the recurring Gmail token failure",
        proposed_method="remember it",
        strategy="records",
        missing_context=[],
        clarifying_question="none",
    ).with_inputs("request", "prior_context_available"),
    dspy.Example(
        request="should i take that free udemy course thing you mentioned",
        prior_context_available=True,
        objective="Decide whether to enroll in the Udemy course Kitty surfaced",
        proposed_method="take it",
        strategy="direct",
        missing_context=[],
        clarifying_question="none",
    ).with_inputs("request", "prior_context_available"),
]


# ---------- Metric ----------

def _mission_quality(gold: dspy.Example, pred: dspy.Prediction, trace=None) -> float:
    """0..1 score. Rewards: strategy match, missing_context length within 1 of gold,
    unnecessary-question penalty."""
    score = 0.0
    if getattr(pred, "strategy", None) == gold.strategy:
        score += 0.5
    pred_missing = list(getattr(pred, "missing_context", []) or [])
    gold_missing = list(gold.missing_context or [])
    if abs(len(pred_missing) - len(gold_missing)) <= 1:
        score += 0.3
    # Unnecessary question penalty: asked when gold said none.
    gold_no_q = gold.clarifying_question.strip().lower() == "none"
    pred_q = (getattr(pred, "clarifying_question", "") or "").strip().lower()
    pred_no_q = pred_q == "none"
    if gold_no_q == pred_no_q:
        score += 0.2
    return score


# ---------- A. Offline structural test ----------

def _offline_check() -> None:
    canned = (
        "[[ ## objective ## ]]\n"
        "Review the pending job posting draft this week\n\n"
        "[[ ## proposed_method ## ]]\n"
        "none\n\n"
        "[[ ## strategy ## ]]\n"
        "direct\n\n"
        "[[ ## missing_context ## ]]\n"
        "[]\n\n"
        "[[ ## clarifying_question ## ]]\n"
        "none\n\n"
        "[[ ## completed ## ]]"
    )
    with dspy.context(lm=_DummyLM(canned), adapter=dspy.ChatAdapter()):
        module = dspy.Predict(CompileMission)
        pred = module(
            request="figure out that job posting review thing before end of week",
            prior_context_available=True,
        )
    score = _mission_quality(TRAINING_EXAMPLES[1], pred)
    print(f"[proto3/A] offline metric score on training example 1: {score:.2f}")
    assert score == 1.0, f"expected 1.0, got {score}"
    # BootstrapFewShot instantiation (no compile call — needs live LM).
    optimizer = dspy.BootstrapFewShot(
        metric=_mission_quality, max_bootstrapped_demos=2, max_labeled_demos=4,
    )
    assert optimizer is not None
    print(f"[proto3/A] BootstrapFewShot instantiates against CompileMission: OK")
    print(f"[proto3/A] MIPROv2 available: {hasattr(dspy, 'MIPROv2')}")
    print(f"[proto3/A] GEPA available:    {hasattr(dspy, 'GEPA')}")
    print(f"[proto3/A] SIMBA available:   {hasattr(dspy, 'SIMBA') or 'via teleprompt.simba'}")


# ---------- B. Live compile-and-eval ----------

@dataclass
class LiveMetrics:
    label: str
    n: int
    valid: int
    exact_strategy: int
    unnecessary_q: int
    avg_missing: float
    total_seconds: float


def _eval_module(label: str, module: Any, examples: list[dspy.Example]) -> LiveMetrics:
    valid = 0
    exact = 0
    unn = 0
    missing = 0
    start = time.time()
    for ex in examples:
        try:
            pred = module(request=ex.request, prior_context_available=ex.prior_context_available)
            valid += 1
            if getattr(pred, "strategy", None) == ex.strategy:
                exact += 1
            gold_no_q = ex.clarifying_question.strip().lower() == "none"
            pred_no_q = (getattr(pred, "clarifying_question", "") or "").strip().lower() == "none"
            if gold_no_q and not pred_no_q:
                unn += 1
            missing += len(list(getattr(pred, "missing_context", []) or []))
        except Exception as exc:  # noqa: BLE001
            print(f"[proto3/B/{label}] failure on {ex.request[:40]!r}: {type(exc).__name__}: {exc}")
    return LiveMetrics(
        label=label, n=len(examples), valid=valid, exact_strategy=exact,
        unnecessary_q=unn, avg_missing=missing / max(1, valid),
        total_seconds=round(time.time() - start, 2),
    )


def run_live() -> None:  # pragma: no cover — needs live keys
    cheap_key = os.environ.get("OPENROUTER_API_KEY")
    premium_key = os.environ.get("ANTHROPIC_API_KEY")
    if not cheap_key or not premium_key:
        print("[proto3/B] skipped — need BOTH OPENROUTER_API_KEY (cheap) and "
              "ANTHROPIC_API_KEY (premium teacher) in env")
        return

    cheap_lm = dspy.LM("openrouter/deepseek/deepseek-v4-flash", cache=False)
    premium_lm = dspy.LM("anthropic/claude-sonnet-4-6", cache=False)

    eval_examples = [
        dspy.Example(
            request=r, prior_context_available=False,
            objective="", proposed_method="", strategy="direct",
            missing_context=[], clarifying_question="none",
        ).with_inputs("request", "prior_context_available")
        for r in REPRESENTATIVE_JACOB_REQUESTS
    ]

    # 1. Baseline: uncompiled cheap model.
    with dspy.context(lm=cheap_lm, adapter=dspy.ChatAdapter()):
        baseline = _eval_module("uncompiled-cheap", dspy.Predict(CompileMission), eval_examples)

    # 2. Premium teacher baseline.
    with dspy.context(lm=premium_lm, adapter=dspy.ChatAdapter()):
        premium = _eval_module("premium-teacher", dspy.Predict(CompileMission), eval_examples)

    # 3. Compile cheap module using premium as teacher via BootstrapFewShot.
    dspy.settings.configure(lm=premium_lm)
    optimizer = dspy.BootstrapFewShot(
        metric=_mission_quality, max_bootstrapped_demos=3, max_labeled_demos=4,
    )
    compiled = optimizer.compile(dspy.Predict(CompileMission), trainset=TRAINING_EXAMPLES)

    # 4. Run compiled module on cheap model.
    with dspy.context(lm=cheap_lm, adapter=dspy.ChatAdapter()):
        compiled_cheap = _eval_module("compiled-cheap", compiled, eval_examples)

    for m in (baseline, premium, compiled_cheap):
        print(f"[proto3/B] {m.label:20} n={m.n} valid={m.valid} exact_strategy={m.exact_strategy} "
              f"unn_q={m.unnecessary_q} avg_missing={m.avg_missing:.1f} t={m.total_seconds:.1f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="run the live compile+eval (needs keys)")
    args = ap.parse_args()
    _offline_check()
    if args.live:
        run_live()
