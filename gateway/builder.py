"""Autonomous Build Pipeline — spec → scaffold → implement → test → review.

Stages:
  1. PLAN: planner agent breaks goal into steps
  2. SCAFFOLD: coder agent creates file structure
  3. IMPLEMENT: coder agent writes the code
  4. TEST: verify tests pass
  5. REVIEW: reviewer agent checks quality
  6. COMMIT: auto-commit if all gates pass

Public API:
  start(goal, target_dir, auto_approve=False) -> build_id
  status(build_id) -> dict
  approve_stage(build_id, stage) -> bool
  get_artifact(build_id) -> str
  list_builds(limit) -> list[dict]
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from gateway import llm_client
from gateway.paths import BUILDS_DB, DATA_DIR

logger = logging.getLogger("kitty.builder")

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

BUILD_DB = BUILDS_DB
VALID_STAGES = ["plan", "scaffold", "implement", "test", "review", "commit"]
STAGE_ORDER = {s: i for i, s in enumerate(VALID_STAGES)}

APPROVAL_REQUIRED = {"implement", "commit"}  # stages that need user approval


def init_db() -> None:
    BUILD_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(BUILD_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS builds (
                id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                target_dir TEXT NOT NULL,
                status TEXT DEFAULT 'queued',
                current_stage TEXT DEFAULT 'plan',
                stage_status TEXT DEFAULT '{}',
                auto_approve INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL,
                artifact TEXT DEFAULT ''
            )
        """)
        conn.commit()


def start(
    goal: str,
    target_dir: str = "",
    auto_approve: bool = False,
    require_criteria: bool = False,
) -> str:
    """Start a new build pipeline. Returns build_id."""
    init_db()
    build_id = str(uuid.uuid4())[:8]
    now = time.time()

    target = target_dir or str(DATA_DIR / "builds" / build_id)
    Path(target).mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(BUILD_DB) as conn:
        conn.execute(
            "INSERT INTO builds (id, goal, target_dir, status, auto_approve, created_at, updated_at) "
            "VALUES (?, ?, ?, 'running', ?, ?, ?)",
            (build_id, goal, target, int(auto_approve), now, now),
        )
        conn.commit()

    logger.info("Build started: %s goal=%s", build_id, goal[:80])

    # Launch pipeline in background
    asyncio.create_task(_run_pipeline(build_id, goal, target, auto_approve, require_criteria))

    return build_id


def status(build_id: str) -> dict:
    """Get build status."""
    init_db()
    with sqlite3.connect(BUILD_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM builds WHERE id = ?", (build_id,)).fetchone()
    if not row:
        return {"id": build_id, "status": "not_found"}
    d = dict(row)
    try:
        d["stage_status"] = json.loads(d.get("stage_status", "{}"))
    except (json.JSONDecodeError, TypeError):
        d["stage_status"] = {}
    return d


def approve_stage(build_id: str, stage: str) -> bool:
    """Approve a stage that's waiting for user input. Returns True if approved."""
    # For now, just signals approval by updating stage status
    build = status(build_id)
    if build.get("status") != "running":
        return False

    stages = build.get("stage_status", {})
    if stages.get(stage) == "awaiting_approval":
        stages[stage] = "approved"
        _update_stage_status(build_id, stages)
        return True
    return False


def get_artifact(build_id: str) -> str:
    """Get the build artifact (generated code/text)."""
    init_db()
    with sqlite3.connect(BUILD_DB) as conn:
        row = conn.execute("SELECT artifact FROM builds WHERE id = ?", (build_id,)).fetchone()
    return row[0] if row else ""


def list_builds(limit: int = 10) -> list[dict]:
    """List recent builds."""
    init_db()
    with sqlite3.connect(BUILD_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM builds ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# --- Pipeline Execution ---


async def _run_pipeline(
    build_id: str,
    goal: str,
    target_dir: str,
    auto_approve: bool,
    require_criteria: bool = False,
) -> None:
    """Execute all pipeline stages in sequence."""
    stages_status: dict[str, str] = {}
    criteria_met = True

    try:
        # Stage 1: PLAN
        stages_status["plan"] = "running"
        _update(build_id, current_stage="plan", stage_status=stages_status)

        plan = await _run_plan_stage(goal)
        # Derive atomic success criteria (ISCs) up front so "done" is explicit.
        criteria = await asyncio.to_thread(derive_criteria, goal)
        if criteria:
            plan = f"{plan}\n\n{format_criteria_block(criteria)}"
        stages_status["plan"] = "completed"
        _update(build_id, stage_status=stages_status, artifact=plan)

        # Stage 2: SCAFFOLD
        stages_status["scaffold"] = "running"
        _update(build_id, current_stage="scaffold", stage_status=stages_status)

        scaffold_result = await _run_scaffold_stage(goal, plan, target_dir)
        stages_status["scaffold"] = "completed"
        _update(build_id, stage_status=stages_status)

        # Stage 3: IMPLEMENT — requires approval
        stages_status["implement"] = "awaiting_approval" if not auto_approve else "approved"
        _update(build_id, current_stage="implement", stage_status=stages_status)

        if not auto_approve:
            await _wait_for_approval(build_id, "implement", timeout=300)

        stages_status["implement"] = "running"
        _update(build_id, stage_status=stages_status)

        code = await _run_implement_stage(goal, plan, scaffold_result, target_dir)
        stages_status["implement"] = "completed"
        _update(build_id, stage_status=stages_status, artifact=code)

        # Stage 4: TEST
        stages_status["test"] = "running"
        _update(build_id, current_stage="test", stage_status=stages_status)

        test_result = await _run_test_stage(target_dir)
        stages_status["test"] = "completed" if test_result.get("passed") else "failed"
        _update(build_id, stage_status=stages_status)

        if not test_result.get("passed"):
            _update(build_id, status="failed")
            return

        # Stage 5: REVIEW
        stages_status["review"] = "running"
        _update(build_id, current_stage="review", stage_status=stages_status)

        review = await _run_review_stage(goal, code, test_result)
        # Check the build against the success criteria derived at PLAN (advisory).
        if criteria:
            evidence = f"Test output:\n{test_result.get('stdout', '')}\n\nCode:\n{code[:4000]}"
            crit_results = await asyncio.to_thread(check_criteria, goal, criteria, evidence)
            review = f"{review}\n\n{format_criteria_block(crit_results)}"
            criteria_met = all_criteria_passed(crit_results)
            if not criteria_met:
                logger.info("Build %s: not all success criteria met", build_id)
        stages_status["review"] = "completed"
        _update(build_id, stage_status=stages_status, artifact=review)

        # Optional hard gate: block commit unless every criterion passed.
        if require_criteria and not criteria_met:
            stages_status["commit"] = "blocked"
            _update(build_id, status="failed", stage_status=stages_status)
            logger.info("Build %s blocked: success criteria not met", build_id)
            return

        # Stage 6: COMMIT — requires approval
        stages_status["commit"] = "awaiting_approval" if not auto_approve else "approved"
        _update(build_id, current_stage="commit", stage_status=stages_status)

        if not auto_approve:
            await _wait_for_approval(build_id, "commit", timeout=300)

        stages_status["commit"] = "completed"
        _update(build_id, status="completed", stage_status=stages_status)

        logger.info("Build %s completed successfully", build_id)

    except asyncio.CancelledError:
        _update(build_id, status="cancelled", stage_status=stages_status)
    except Exception:
        logger.exception("Build %s failed", build_id)
        _update(build_id, status="failed", stage_status=stages_status)


# --- Individual Stage Runners ---


async def _run_plan_stage(goal: str) -> str:
    """Use planner agent to break goal into steps."""
    from gateway.agent_runner import await_completion, get_output, spawn

    session_id = await spawn(goal, agent_type="planner", max_iterations=3)
    await await_completion(session_id, poll=3.0, timeout=90.0)
    return get_output(session_id)


async def _run_scaffold_stage(goal: str, plan: str, target_dir: str) -> str:
    """Generate file structure based on the plan."""
    from gateway.agent_runner import await_completion, get_output, spawn

    scaffold_goal = (
        f"Based on this plan, create the file and directory structure for the project.\n\n"
        f"Goal: {goal}\n\nPlan:\n{plan}\n\n"
        f"Target directory: {target_dir}\n\n"
        f"List every file and directory that needs to be created. Format as a tree."
    )
    session_id = await spawn(scaffold_goal, agent_type="planner", max_iterations=2)
    await await_completion(session_id, poll=3.0, timeout=60.0)
    return get_output(session_id)


async def _run_implement_stage(goal: str, plan: str, scaffold: str, target_dir: str) -> str:
    """Write the actual code."""
    from gateway.agent_runner import await_completion, get_output, spawn

    impl_goal = (
        f"Implement the following project. Write complete, working code for every file.\n\n"
        f"Goal: {goal}\n\nPlan:\n{plan}\n\nFile structure:\n{scaffold}\n\n"
        f"Target: {target_dir}\n\n"
        f"Output the COMPLETE content of each file. Use markdown code blocks with file paths."
    )
    session_id = await spawn(impl_goal, agent_type="coder", max_iterations=5)
    await await_completion(session_id, poll=5.0, timeout=300.0)
    return get_output(session_id)


async def _run_test_stage(target_dir: str) -> dict:
    """Run tests in the target directory."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3.12",
            "-m",
            "pytest",
            str(target_dir),
            "-q",
            "--tb=short",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        return {
            "passed": proc.returncode == 0,
            "stdout": stdout.decode()[:2000],
            "stderr": stderr.decode()[:500],
        }
    except Exception as e:
        return {"passed": False, "error": str(e)}


async def _run_review_stage(goal: str, code: str, test_result: dict) -> str:
    """Review the output for quality."""
    from gateway.agent_runner import await_completion, get_output, spawn

    review_goal = (
        f"Review this code implementation.\n\n"
        f"Goal: {goal}\n\n"
        f"Test results: {'PASSED' if test_result.get('passed') else 'FAILED'}\n\n"
        f"Code:\n{code[:4000]}\n\n"
        f"Review for: correctness, completeness, edge cases, security, style. Be constructive."
    )
    session_id = await spawn(review_goal, agent_type="reviewer", max_iterations=2)
    await await_completion(session_id, poll=3.0, timeout=60.0)
    return get_output(session_id)


async def _wait_for_approval(build_id: str, stage: str, timeout: int) -> None:
    """Poll until the stage is approved or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        build = status(build_id)
        stages = build.get("stage_status", {})
        if stages.get(stage) == "approved":
            return
        await asyncio.sleep(2)
    raise TimeoutError(f"Build {build_id} timed out waiting for approval on stage {stage}")


# --- Helpers ---


def _update(build_id: str, **fields) -> None:
    init_db()
    now = time.time()
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [now, build_id]
    with sqlite3.connect(BUILD_DB) as conn:
        conn.execute(f"UPDATE builds SET {sets}, updated_at = ? WHERE id = ?", values)
        conn.commit()


def _update_stage_status(build_id: str, stages: dict) -> None:
    _update(build_id, stage_status=json.dumps(stages))


# --- Success Criteria (ISA-lite, formerly gateway/success_criteria.py) ---


def derive_criteria(goal: str) -> list[str]:
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


def check_criteria(goal: str, criteria: list[str], evidence: str) -> list[dict[str, Any]]:
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


def format_criteria_block(criteria_or_results: list) -> str:
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


def all_criteria_passed(results: list[dict[str, Any]]) -> bool:
    """True only if there is at least one result and every one passed."""
    return bool(results) and all(r.get("passed") for r in results)


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
