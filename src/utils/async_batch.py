#!/usr/bin/env python3
"""
Async Batch Processor for Kitty
Processes multiple tasks concurrently with retry logic
"""

import asyncio
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Task:
    """A task in the batch processor"""

    id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None
    attempts: int = 0
    max_attempts: int = 3
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None


@dataclass
class BatchResult:
    """Result of batch processing"""

    total: int
    successful: int
    failed: int
    duration: float
    results: list[Task]


class AsyncBatchProcessor:
    """Process tasks in batch with concurrency and retry"""

    def __init__(self, max_workers: int = 4, default_timeout: int = 60, retry_delay: float = 1.0):
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.retry_delay = retry_delay
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, func: Callable, *args, task_id: str = None, **kwargs) -> Task:
        """Submit a task"""
        task_id = task_id or f"task_{int(time.time() * 1000)}"
        task = Task(id=task_id, func=func, args=args, kwargs=kwargs)
        return task

    def _run_task(self, task: Task) -> Task:
        """Run a single task with retry"""
        while task.attempts < task.max_attempts:
            try:
                task.status = TaskStatus.RUNNING
                task.started_at = time.time()
                task.result = task.func(*task.args, **task.kwargs)
                task.status = TaskStatus.COMPLETED
                task.completed_at = time.time()
                return task
            except Exception as e:
                task.attempts += 1
                task.error = str(e)[:100]
                if task.attempts < task.max_attempts:
                    task.status = TaskStatus.RETRYING
                    time.sleep(self.retry_delay * task.attempts)
                else:
                    task.status = TaskStatus.FAILED
                    task.completed_at = time.time()
        return task

    def process(self, tasks: list[Task]) -> BatchResult:
        """Process multiple tasks"""
        start_time = time.time()

        # Submit all tasks
        futures = {self.executor.submit(self._run_task, task): task for task in tasks}

        # Collect results
        for future in as_completed(futures):
            future.result()

        duration = time.time() - start_time
        results = [f.result() for f in futures]

        successful = sum(1 for t in results if t.status == TaskStatus.COMPLETED)
        failed = len(results) - successful

        return BatchResult(
            total=len(tasks),
            successful=successful,
            failed=failed,
            duration=duration,
            results=results,
        )

    def process_async(self, tasks: list[Task]) -> BatchResult:
        """Process tasks asynchronously"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._process_async(tasks))
        finally:
            loop.close()

    async def _process_async(self, tasks: list[Task]) -> BatchResult:
        """Async task processing"""
        start_time = time.time()

        # Run tasks concurrently
        task_coroutines = [self._run_task_async(task) for task in tasks]

        results = await asyncio.gather(*task_coroutines)
        duration = time.time() - start_time

        successful = sum(1 for t in results if t.status == TaskStatus.COMPLETED)
        failed = len(results) - successful

        return BatchResult(
            total=len(tasks),
            successful=successful,
            failed=failed,
            duration=duration,
            results=results,
        )

    async def _run_task_async(self, task: Task) -> Task:
        """Run a task asynchronously"""
        while task.attempts < task.max_attempts:
            try:
                task.status = TaskStatus.RUNNING
                task.started_at = time.time()

                # Run sync function in executor
                loop = asyncio.get_event_loop()
                task.result = await loop.run_in_executor(None, task.func, *task.args, **task.kwargs)

                task.status = TaskStatus.COMPLETED
                task.completed_at = time.time()
                return task
            except Exception as e:
                task.attempts += 1
                task.error = str(e)[:100]
                if task.attempts < task.max_attempts:
                    task.status = TaskStatus.RETRYING
                    await asyncio.sleep(self.retry_delay * task.attempts)
                else:
                    task.status = TaskStatus.FAILED
                    task.completed_at = time.time()
        return task

    def shutdown(self):
        """Shutdown executor"""
        self.executor.shutdown(wait=True)


# Retry decorator
def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator to retry functions on failure"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    time.sleep(current_delay)
                    current_delay *= backoff

        return wrapper

    return decorator


# Fallback decorator
def fallback(fallback_func: Callable, catch: tuple = (Exception,)):
    """Decorator with fallback on failure"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except catch:
                return fallback_func(*args, **kwargs)

        return wrapper

    return decorator


# CLI
def main():
    """Batch processor CLI"""
    import typer

    app = typer.Typer(help="Async Batch Processor")

    @app.command("run")
    def run_batch(
        count: int = typer.Option(10, "--count", "-n", help="Number of tasks"),
        workers: int = typer.Option(4, "--workers", "-w", help="Max workers"),
    ):
        """Run batch tasks"""
        processor = AsyncBatchProcessor(max_workers=workers)

        def sample_task(x):
            time.sleep(0.1)
            return x * 2

        tasks = [processor.submit(sample_task, i, task_id=f"task_{i}") for i in range(count)]

        result = processor.process(tasks)

        typer.echo(f"Total: {result.total}")
        typer.echo(f"Successful: {result.successful}")
        typer.echo(f"Failed: {result.failed}")
        typer.echo(f"Duration: {result.duration:.2f}s")

        processor.shutdown()

    app()


if __name__ == "__main__":
    main()
