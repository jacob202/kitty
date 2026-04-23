import logging
import threading

from src.orchestrator.job_queue import dequeue, update_status

logger = logging.getLogger(__name__)

# Supported task types handled by this worker
_HANDLERS = ("kitty_coder", "skill_refinery", "flush_corrections")


class BackgroundWorker:
    """
    Background worker that polls the job queue and dispatches to per-type handlers.

    Supported task_types:
      kitty_coder      — autonomous code fix/improve via specialist agent
      skill_refinery   — adversarial Jester review of a staged skill
      flush_corrections — write corrections.db entries as training examples
    """

    def __init__(self, supervisor, sleep_interval=5):
        self.supervisor = supervisor
        self.sleep_interval = sleep_interval
        self._stop_event = threading.Event()
        self.thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="KittyBackgroundWorker"
        )

    def start(self):
        logger.info("Starting kitty background worker...")
        self.thread.start()

    def stop(self):
        logger.info("Stopping kitty background worker...")
        self._stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=5.0)

    # ── Main loop ──────────────────────────────────────────────────────────────

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                job = dequeue()
                if job:
                    job_id = job.get("id")
                    task_type = job.get("task_type")
                    logger.info(f"Background worker dequeued job {job_id} (type: {task_type})")

                    if task_type == "kitty_coder":
                        self._handle_kitty_coder_job(job)
                    elif task_type == "skill_refinery":
                        self._handle_skill_refinery_job(job)
                    elif task_type == "flush_corrections":
                        self._handle_flush_corrections(job)
                    else:
                        logger.warning(f"Unsupported task_type '{task_type}' for job {job_id}.")
                        update_status(job_id, "failed", error=f"Unsupported task_type: {task_type}")
                else:
                    self._stop_event.wait(self.sleep_interval)
            except Exception as e:
                logger.error(f"Error in background worker loop: {e}")
                self._stop_event.wait(self.sleep_interval)

    # ── Handlers ───────────────────────────────────────────────────────────────

    def _handle_kitty_coder_job(self, job):
        job_id = job["id"]
        payload = job.get("payload", {})
        prompt = payload.get("task", "")

        if not prompt:
            update_status(job_id, "failed", error="No prompt provided in task payload.")
            return

        agent_config = next(
            (cfg for cfg in self.supervisor.specialists if cfg.get("name") == "kitty_coder"), None
        )
        if not agent_config:
            update_status(job_id, "failed", error="kitty_coder agent config not found.")
            return

        try:
            logger.info(f"Executing kitty_coder job {job_id}...")
            result_msg = self.supervisor._run_specialist_with_tools(agent_config, prompt)
            update_status(job_id, "completed", result=result_msg)
            logger.info(f"kitty_coder job {job_id} completed.")
            self._log_improvement_event("kitty_coder_completed", f"job {job_id}")
        except Exception as e:
            logger.error(f"kitty_coder job {job_id} failed: {e}")
            update_status(job_id, "failed", error=str(e))

    def _handle_skill_refinery_job(self, job):
        """Run Jester adversarial review on a staged skill. Auto-approve if Jester offline."""
        job_id = job["id"]
        payload = job.get("payload", {})
        skill_name = payload.get("skill_name", "")
        skill_code = payload.get("skill_code", "")

        if not skill_code:
            update_status(job_id, "failed", error="No skill_code in payload.")
            return

        try:
            from src.core.skill_refinery import run_jester_review

            approved, feedback = run_jester_review(skill_code)
            if approved:
                logger.info(f"Skill '{skill_name}' approved by Jester.")
                update_status(job_id, "completed", result=f"approved: {feedback[:200]}")
                self._log_improvement_event("skill_approved", skill_name)
            else:
                logger.warning(f"Skill '{skill_name}' REJECTED by Jester: {feedback[:200]}")
                update_status(job_id, "failed", error=f"rejected: {feedback[:200]}")
                self._log_improvement_event("skill_rejected", f"{skill_name}: {feedback[:100]}")
        except Exception as e:
            logger.error(f"skill_refinery job {job_id} failed: {e}")
            update_status(job_id, "failed", error=str(e))

    def _handle_flush_corrections(self, job):
        """Write corrections.db entries to training JSONL."""
        job_id = job["id"]
        try:
            from src.autonomy.self_improvement_engine import SelfImprovementEngine

            sie = SelfImprovementEngine()
            written = sie.flush_corrections_to_training()
            update_status(job_id, "completed", result=f"{written} correction examples written")
            self._log_improvement_event("corrections_flushed", f"{written} examples")
        except Exception as e:
            logger.error(f"flush_corrections job {job_id} failed: {e}")
            update_status(job_id, "failed", error=str(e))

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _log_improvement_event(self, event_type: str, detail: str = ""):
        """Best-effort log to SelfImprovementEngine."""
        try:
            from src.autonomy.self_improvement_engine import SelfImprovementEngine

            SelfImprovementEngine().log_event(event_type, detail)
        except Exception:
            pass
