"""Verification Agent — post-change validation with test running and regression checks.

Public API:
  verify(target_dir, test_path) -> dict    Run tests and return result
  verify_with_review(goal, code, target_dir) -> dict   Full verify + review
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("kitty.verifier")


async def verify(
    target_dir: str,
    test_path: Optional[str] = None,
    timeout: int = 60,
) -> dict:
    """Run tests in target_dir. Returns {passed, total, failures, output}."""
    test_target = test_path or target_dir
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3.12", "-m", "pytest", str(test_target), "-q", "--tb=line",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out_text = stdout.decode()
        err_text = stderr.decode()

        # Parse pytest output for counts
        total = 0
        passed = 0
        failed = 0
        for line in out_text.split("\n"):
            if "passed" in line and "failed" in line:
                try:
                    parts = line.strip().split()
                    for i, p in enumerate(parts):
                        if "passed" in p:
                            passed = int(parts[i - 1]) if i > 0 else int(p.replace("passed", "0"))
                        if "failed" in p:
                            failed = int(parts[i - 1]) if i > 0 else int(p.replace("failed", "0"))
                    total = passed + failed
                except (ValueError, IndexError):
                    pass

        return {
            "passed": proc.returncode == 0 or failed == 0,
            "total": total,
            "passed_count": passed,
            "failed_count": failed,
            "output": out_text[:3000],
            "errors": err_text[:500],
        }
    except asyncio.TimeoutError:
        return {"passed": False, "error": f"Test timeout after {timeout}s"}
    except Exception as e:
        return {"passed": False, "error": str(e)}


async def verify_with_review(
    goal: str,
    code: str,
    target_dir: str,
) -> dict:
    """Full verification: run tests + spawn reviewer agent for human-readable feedback."""
    result = await verify(target_dir)

    # Spawn reviewer for qualitative feedback
    try:
        from gateway.agent_runner import get_output, get_status, spawn
        review_goal = (
            f"Review this verification result for a build.\n\n"
            f"Goal: {goal}\n\n"
            f"Verification: {'PASSED' if result.get('passed') else 'FAILED'}\n"
            f"Test output:\n{result.get('output', '')[:2000]}\n\n"
            f"Give a 2-3 sentence verdict: what's good, what needs attention."
        )
        session_id = await spawn(review_goal, agent_type="reviewer", max_iterations=2)
        for _ in range(15):
            await asyncio.sleep(3)
            s = get_status(session_id)
            if s["status"] in ("completed", "failed"):
                break
        result["review"] = get_output(session_id)
    except Exception as e:
        logger.warning("Verifier review agent failed: %s", e)
        result["review"] = ""

    return result
