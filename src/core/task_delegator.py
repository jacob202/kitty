import logging
import threading
import time

from src.orchestrator.job_queue import enqueue, list_jobs

logger = logging.getLogger(__name__)


class TaskDelegator:
    """
    Handles asynchronous execution of heavy tasks using a SQLite-backed job queue.
    """

    def __init__(self, supervisor):
        self.supervisor = supervisor
        self._tasks_lock = threading.Lock()
        self.active_tasks = {}

    def delegate_heavy_task(self, user_query: str, task_type: str = "autogpt"):
        """
        Enqueues a task into the job queue. Returns a tracking ID (job ID).
        """
        # We default to 'autogpt' for heavy tasks unless specified
        job_id = enqueue(task_type, {"task": user_query}, priority=5)

        task_id = str(job_id)
        with self._tasks_lock:
            self.active_tasks[task_id] = {
                "status": "pending",
                "query": user_query,
                "type": task_type,
                "start_time": time.time(),
            }

        logger.info(f"Enqueued heavy task {task_id} (type: {task_type})")
        # Emit to web UI that a background task was enqueued
        self.supervisor._emit_status(
            f"bg_task_{task_id}", "pending", data={"query": user_query, "job_id": job_id}
        )

        return task_id

    def check_task_status(self, task_id: str):
        """
        Checks the status of a specific job in the queue.
        """
        try:
            job_id = int(task_id)
            jobs = list_jobs()  # This is a bit inefficient for a single job, but job_queue.py doesn't have get_job(id)
            for job in jobs:
                if job["id"] == job_id:
                    return job
            return None
        except ValueError:
            return None
