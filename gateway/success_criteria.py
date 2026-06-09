"""Success Criteria (ISA-lite) — derive and check atomic, binary criteria for a goal.

Adapted from PAI's ISA primitive (the Criteria / ISC section): a task's "done"
should be a small set of atomic, independently-verifiable, binary criteria — not a
vague goal. This module derives them from a goal and checks them against evidence
(test output, generated code, agent results).

Deep module — callers use:
    derive(goal) -> list[str]
    check(goal, criteria, evidence) -> list[dict]
    format_block(criteria_or_results) -> str
    all_passed(results) -> bool

LLM calls degrade gracefully: any failure returns an empty/neutral result rather
than raising, so build pipelines never break on criteria.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from gateway import llm_client

logger = logging.getLogger("kitty.success_criteria")

MAX_CRITERIA = 7

_DERIVE_SYS = (
    "You convert a task goal into atomic, binary success criteria (ISCs), in the "
    "spirit of an Ideal State Artifact. Each criterion must be independently "
    "verifiable and strictly pass/fail. Apply the splitting test: if a criterion "
    "contains 'and', 'with', 'including', or a scope word ('all', 'every', "
    "'complete'), break it into separate criteria. Include at least one 'Anti:' "
    "criterion naming something that must NOT happen. Return 3-"
    f"{MAX_CRITERIA} criteria, one per line, no numbering and no preamble."
)

_CHECK_SYS = (
    "You are a strict verifier. Given a goal, its success criteria, and evidence "
    "(test output, code, results), judge each criterion. Return ONLY a JSON array "
    'of objects: [{"criterion": str, "passed": bool, "note": str}]. A criterion '
    "passes only if the evidence clearly supports it; if unknown, passed=false."
)


def derive(goal: str) -> list[str]:
    """Derive atomic, binary success criteria from a goal. Returns [] on failure."""
    if not goal or not goal.strip():
        return []
    try:
        text = llm_client.chat(
            model=llm_client.route_model("analyze " + goal),
            messages=[
                {"role": "system", "content": _DERIVE_SYS},
                {"role": "user", "content": f"Goal: {goal.strip()}"},
            ],
            max_tokens=400,
            temperature=0.2,
        )
    except Exception as e:
        logger.warning("criteria derive failed: %s", e)
        return []
    return _parse_criteria(text)


def check(goal: str, criteria: list[str], evidence: str) -> list[dict[str, Any]]:
    """Judge each criterion against evidence. Neutral (passed=False) on failure."""
    if not criteria:
        return []
    payload = {"goal": goal, "criteria": criteria, "evidence": (evidence or "")[:6000]}
    try:
        text = llm_client.chat(
            model=llm_client.route_model("analyze verification"),
            messages=[
                {"role": "system", "content": _CHECK_SYS},
                {"role": "user", "content": json.dumps(payload)},
            ],
            max_tokens=600,
            temperature=0.0,
        )
        results = _parse_check(text)
        if results:
            return results
    except Exception as e:
        logger.warning("criteria check failed: %s", e)
    return [{"criterion": c, "passed": False, "note": "unverified"} for c in criteria]


def format_block(criteria_or_results: list) -> str:
    """Render criteria (list[str]) or results (list[dict]) as a markdown checklist."""
    if not criteria_or_results:
        return ""
    lines = ["## Success Criteria (ISC)"]
    for item in criteria_or_results:
        if isinstance(item, dict):
            box = "x" if item.get("passed") else " "
            note = f" — {item['note']}" if item.get("note") else ""
            lines.append(f"- [{box}] {item.get('criterion', '')}{note}")
        else:
            lines.append(f"- [ ] {item}")
    return "\n".join(lines)


def all_passed(results: list[dict[str, Any]]) -> bool:
    """True only if there is at least one result and every one passed."""
    return bool(results) and all(r.get("passed") for r in results)


# --- Internal parsing ---


def _parse_criteria(text: str) -> list[str]:
    out: list[str] = []
    for line in (text or "").splitlines():
        line = re.sub(r"^[-*\d.)\s]+", "", line.strip()).strip()
        if line:
            out.append(line)
    return out[:MAX_CRITERIA]


def _parse_check(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict) and "criterion" in item:
            out.append(
                {
                    "criterion": str(item.get("criterion", "")),
                    "passed": bool(item.get("passed", False)),
                    "note": str(item.get("note", "")),
                }
            )
    return out
