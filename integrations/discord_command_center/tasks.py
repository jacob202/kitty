from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Callable


@dataclass
class TaskEntry:
    task_id: str
    owner_id: int | None
    created_at: float
    thread_id: int | None = None
    task: asyncio.Task[object] | None = None


class TaskRegistry:
    """Bounded, process-local registry for live Discord task callbacks."""

    def __init__(
        self,
        *,
        max_concurrent_runs: int = 2,
        max_runs_per_user: int = 1,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_concurrent_runs <= 0:
            raise ValueError("max_concurrent_runs must be positive")
        if max_runs_per_user <= 0:
            raise ValueError("max_runs_per_user must be positive")
        self.max_concurrent_runs = max_concurrent_runs
        self.max_runs_per_user = max_runs_per_user
        self._clock = clock
        self._entries: dict[str, TaskEntry] = {}

    def reserve(self, owner_id: int | None) -> TaskEntry | None:
        self._reap_finished()
        if len(self._entries) >= self.max_concurrent_runs:
            return None
        if sum(entry.owner_id == owner_id for entry in self._entries.values()) >= self.max_runs_per_user:
            return None
        entry = TaskEntry(
            task_id=f"cc-{uuid.uuid4().hex[:12]}",
            owner_id=owner_id,
            created_at=self._clock(),
        )
        self._entries[entry.task_id] = entry
        return entry

    def register(
        self,
        entry: TaskEntry,
        task: asyncio.Task[object],
        *,
        thread_id: int | None,
    ) -> None:
        current = self._entries.get(entry.task_id)
        if current is not entry:
            raise RuntimeError(f"task reservation is not active: {entry.task_id}")
        entry.task = task
        entry.thread_id = thread_id

    def release(self, task_id: str) -> None:
        self._entries.pop(task_id, None)

    def find(
        self,
        *,
        owner_id: int | None,
        task_id: str | None = None,
        thread_id: int | None = None,
    ) -> TaskEntry | None:
        self._reap_finished()
        if task_id is not None:
            entry = self._entries.get(task_id)
            return entry if entry is not None and entry.owner_id == owner_id else None
        if thread_id is None:
            return None
        return next(
            (
                entry
                for entry in self._entries.values()
                if entry.owner_id == owner_id and entry.thread_id == thread_id
            ),
            None,
        )

    def for_owner(self, owner_id: int | None) -> tuple[TaskEntry, ...]:
        self._reap_finished()
        return tuple(entry for entry in self._entries.values() if entry.owner_id == owner_id)

    def _reap_finished(self) -> None:
        finished = [
            task_id
            for task_id, entry in self._entries.items()
            if entry.task is not None and entry.task.done()
        ]
        for task_id in finished:
            self._entries.pop(task_id, None)
