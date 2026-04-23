"""
Parallel dispatcher — pulls jobs from the queue and runs them as subprocesses.
Includes a watchdog thread that kills timed-out jobs and requeues them.
"""

import logging
import os
import subprocess
import threading
import time
from pathlib import Path

from src.core.aura_loader import get_branding
from src.orchestrator.job_queue import dequeue, enqueue, list_jobs, update_status
from src.orchestrator.tmux_mcp import list_agents as tmux_list_agents
from src.orchestrator.tmux_mcp import spawn_agent

logger = logging.getLogger(__name__)

_branding = get_branding()

_DEFAULT_CONCURRENCY = int(os.environ.get("DISPATCHER_CONCURRENCY", "4"))
_DEFAULT_TIMEOUT_S = int(os.environ.get("DISPATCHER_TIMEOUT_S", "300"))  # 5 min
_WATCHDOG_INTERVAL_S = 10

# Registry: task_type → shell command template (use {payload_json} placeholder)
_TASK_HANDLERS: dict[str, list[str]] = {
    "aider": ["python", "-m", "aider", "--message", "{task}"],
    "autogpt": [
        "venv/bin/python",
        "-m",
        "autogpt",
        "run",
        "--continuous",
        "--skip-reprompt",
        "--task",
        "{task}",
        "--ai-name",
        _branding["coder_name"],
        "--ai-role",
        "Autonomous Coding Assistant",
        "--constraint",
        "Follow project standards",
        "--resource",
        "src/",
        "--best-practice",
        "Use systematic debugging",
    ],
    "shell": ["bash", "-c", "{task}"],
}

# Running jobs: job_id → (Process, file_handle, start_time, timeout)
_running: dict[int, tuple[subprocess.Popen, object, float, int]] = {}
_running_lock = threading.Lock()


def _build_cmd(job: dict) -> list[str] | None:
    handler = _TASK_HANDLERS.get(job["task_type"])
    if not handler:
        return None
    task_str = job["payload"].get("task", "")
    return [part.replace("{task}", task_str) for part in handler]


def _validate_task(task_type: str, payload: dict) -> str | None:
    """Validate task payload. Returns error message if invalid, None if OK."""
    if task_type == "shell":
        return "Shell task type is disabled for security reasons"
    task = payload.get("task", "")
    if not task or len(task) > 10000:
        return f"Invalid task length: {len(task)}"
    return None


def _dispatch_one(job: dict, timeout_s: int = _DEFAULT_TIMEOUT_S):
    validation_error = _validate_task(job["task_type"], job["payload"])
    if validation_error:
        update_status(job["id"], "failed", error=validation_error)
        return

    cmd = _build_cmd(job)
    if not cmd:
        update_status(
            job["id"], "failed", error=f"No handler for task_type '{job['task_type']}'"
        )
        return

    log_file = None
    try:
        log_path = Path(f"data/logs/job_{job['id']}.log")
        log_path.parent.mkdir(exist_ok=True)

        log_file = open(log_path, "w")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        update_status(job["id"], "running", pid=proc.pid)
        with _running_lock:
            _running[job["id"]] = (proc, log_file, time.time(), timeout_s)
    except Exception as e:
        if log_file:
            log_file.close()
        update_status(job["id"], "failed", error=str(e))


def _watchdog(stop_event: threading.Event):
    """Kill processes that exceed their timeout. Validate PID before killing."""
    while not stop_event.is_set():
        try:
            now = time.time()
            with _running_lock:
                timed_out = [
                    (jid, proc, log_file, start)
                    for jid, (proc, log_file, start, timeout) in _running.items()
                    if now - start > timeout
                ]

            for job_id, proc, log_file, start in timed_out:
                try:
                    if proc.poll() is None:
                        proc.kill()
                        update_status(
                            job_id,
                            "failed",
                            pid=proc.pid,
                            error=f"Killed: exceeded timeout after {int(now - start)}s",
                        )
                except Exception as e:
                    logger.error(f"Watchdog failed to kill job {job_id}: {e}")
                finally:
                    try:
                        log_file.close()
                    except Exception:
                        pass
                    with _running_lock:
                        _running.pop(job_id, None)

            with _running_lock:
                finished = [
                    (jid, proc, log_file)
                    for jid, (proc, log_file, _, _t) in _running.items()
                    if proc.poll() is not None
                ]

            for job_id, proc, log_file in finished:
                try:
                    rc = proc.returncode
                    log_path = Path(f"data/logs/job_{job_id}.log")
                    output = ""
                    if log_path.exists():
                        with open(log_path) as f:
                            output = f.read()

                    if rc == 0:
                        update_status(job_id, "completed", result=output[:4000])
                    else:
                        update_status(
                            job_id, "failed", error=f"Exit {rc}: {output[:2000]}"
                        )
                except Exception as e:
                    logger.error(f"Watchdog failed to finish job {job_id}: {e}")
                finally:
                    try:
                        log_file.close()
                    except Exception:
                        pass
                    with _running_lock:
                        _running.pop(job_id, None)
        except Exception as global_e:
            logger.critical(f"Watchdog global error: {global_e}")

        stop_event.wait(timeout=_WATCHDOG_INTERVAL_S)


class ParallelDispatcher:
    def __init__(
        self,
        concurrency: int = _DEFAULT_CONCURRENCY,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
    ):
        self.concurrency = concurrency
        self.timeout_s = timeout_s
        self._stop = threading.Event()
        self._watchdog_t = threading.Thread(
            target=_watchdog,
            args=(self._stop,),
            daemon=True,
            name="dispatcher-watchdog",
        )
        self._worker_t = threading.Thread(
            target=self._worker_loop, daemon=True, name="dispatcher-worker"
        )

    def start(self):
        self._watchdog_t.start()
        self._worker_t.start()

    def stop(self):
        self._stop.set()

    def _worker_loop(self):
        while not self._stop.is_set():
            with _running_lock:
                active = len(_running)

            if active >= self.concurrency:
                self._stop.wait(timeout=0.5)
                continue

            job = dequeue()
            if job is None:
                self._stop.wait(timeout=1.0)
                continue

            # Check dependencies
            deps = job["payload"].get("dependencies", [])
            if deps:
                from src.orchestrator.job_queue import get_db

                try:
                    with get_db() as c:
                        placeholders = ",".join("?" * len(deps))
                        rows = c.execute(
                            f"SELECT id, status FROM jobs WHERE id IN ({placeholders})",
                            tuple(deps),
                        ).fetchall()

                    # If any dependency is not completed, push back to pending
                    pending_deps = any(r[1] != "completed" for r in rows)
                    # Also check if any dependency failed
                    failed_deps = any(r[1] == "failed" for r in rows)

                    if failed_deps:
                        update_status(job["id"], "failed", error="Dependency failed")
                        continue
                    elif pending_deps:
                        update_status(job["id"], "pending")
                        self._stop.wait(timeout=2.0)
                        continue
                except Exception as e:
                    logger.error(f"Dependency check failed for job {job['id']}: {e}")
                    update_status(
                        job["id"], "failed", error=f"Dependency check error: {e}"
                    )
                    continue

            t = threading.Thread(
                target=_dispatch_one,
                args=(job, self.timeout_s),
                daemon=True,
            )
            t.start()

    def submit(
        self, task_type: str, task: str, priority: int = 5, correlation_id: str = None
    ) -> int:
        """Convenience: enqueue a job and let the worker pick it up."""
        return enqueue(
            task_type, {"task": task}, priority=priority, correlation_id=correlation_id
        )

    def status(self) -> dict:
        with _running_lock:
            active = len(_running)
        pending = len(list_jobs(status="pending"))
        return {"active": active, "pending": pending, "concurrency": self.concurrency}

    def spawn_in_tmux(
        self, task_type: str, task: str, window_name: str = None
    ) -> tuple[bool, str]:
        """Spawn a task in a tmux window for fire-and-forget execution."""
        return spawn_agent(task_type, task, window_name=window_name)

    def tmux_status(self) -> dict:
        """Get status of tmux-based agents."""
        success, agents = tmux_list_agents()
        if success:
            return {
                "tmux_session": _branding["session_prefix"],
                "active_windows": len(agents),
                "agents": agents,
            }
        return {
            "tmux_session": _branding["session_prefix"],
            "active_windows": 0,
            "agents": [],
            "error": "tmux not available",
        }
