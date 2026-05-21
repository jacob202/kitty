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
import sqlite3
import time
import uuid
from pathlib import Path

from gateway.paths import DATA_DIR

logger = logging.getLogger("kitty.builder")

BUILD_DB = DATA_DIR / "builds.db"
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
    asyncio.create_task(_run_pipeline(build_id, goal, target, auto_approve))

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
        row = conn.execute(
            "SELECT artifact FROM builds WHERE id = ?", (build_id,)
        ).fetchone()
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
    build_id: str, goal: str, target_dir: str, auto_approve: bool
) -> None:
    """Execute all pipeline stages in sequence."""
    stages_status: dict[str, str] = {}

    try:
        # Stage 1: PLAN
        stages_status["plan"] = "running"
        _update(build_id, current_stage="plan", stage_status=stages_status)

        plan = await _run_plan_stage(goal)
        stages_status["plan"] = "completed"
        _update(build_id, stage_status=stages_status, artifact=plan)

        # Stage 2: SCAFFOLD
        stages_status["scaffold"] = "running"
        _update(build_id, current_stage="scaffold", stage_status=stages_status)

        scaffold_result = await _run_scaffold_stage(goal, plan, target_dir)
        stages_status["scaffold"] = "completed"
        _update(build_id, stage_status=stages_status)

        # Stage 3: IMPLEMENT — requires approval
        stages_status["implement"] = (
            "awaiting_approval" if not auto_approve else "approved"
        )
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
        stages_status["review"] = "completed"
        _update(build_id, stage_status=stages_status, artifact=review)

        # Stage 6: COMMIT — requires approval
        stages_status["commit"] = (
            "awaiting_approval" if not auto_approve else "approved"
        )
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
    from gateway.agent_runner import spawn, get_output, get_status

    session_id = await spawn(goal, agent_type="planner", max_iterations=3)
    for _ in range(30):
        await asyncio.sleep(3)
        s = get_status(session_id)
        if s["status"] in ("completed", "failed"):
            break
    return get_output(session_id)


async def _run_scaffold_stage(goal: str, plan: str, target_dir: str) -> str:
    """Generate file structure based on the plan."""
    from gateway.agent_runner import spawn, get_output, get_status

    scaffold_goal = (
        f"Based on this plan, create the file and directory structure for the project.\n\n"
        f"Goal: {goal}\n\nPlan:\n{plan}\n\n"
        f"Target directory: {target_dir}\n\n"
        f"List every file and directory that needs to be created. Format as a tree."
    )
    session_id = await spawn(scaffold_goal, agent_type="planner", max_iterations=2)
    for _ in range(20):
        await asyncio.sleep(3)
        s = get_status(session_id)
        if s["status"] in ("completed", "failed"):
            break
    return get_output(session_id)


async def _run_implement_stage(
    goal: str, plan: str, scaffold: str, target_dir: str
) -> str:
    """Write the actual code."""
    from gateway.agent_runner import spawn, get_output, get_status

    impl_goal = (
        f"Implement the following project. Write complete, working code for every file.\n\n"
        f"Goal: {goal}\n\nPlan:\n{plan}\n\nFile structure:\n{scaffold}\n\n"
        f"Target: {target_dir}\n\n"
        f"Output the COMPLETE content of each file. Use markdown code blocks with file paths."
    )
    session_id = await spawn(impl_goal, agent_type="coder", max_iterations=5)
    for _ in range(60):
        await asyncio.sleep(5)
        s = get_status(session_id)
        if s["status"] in ("completed", "failed"):
            break
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
    from gateway.agent_runner import spawn, get_output, get_status

    review_goal = (
        f"Review this code implementation.\n\n"
        f"Goal: {goal}\n\n"
        f"Test results: {'PASSED' if test_result.get('passed') else 'FAILED'}\n\n"
        f"Code:\n{code[:4000]}\n\n"
        f"Review for: correctness, completeness, edge cases, security, style. Be constructive."
    )
    session_id = await spawn(review_goal, agent_type="reviewer", max_iterations=2)
    for _ in range(20):
        await asyncio.sleep(3)
        s = get_status(session_id)
        if s["status"] in ("completed", "failed"):
            break
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
    raise TimeoutError(
        f"Build {build_id} timed out waiting for approval on stage {stage}"
    )


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
