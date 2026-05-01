"""Helpers for streaming blueprint: app-level locks and background supervisor tasks."""

from __future__ import annotations

import threading
from typing import Callable

from flask import current_app


def get_busy_lock():
    """Get or create the app-level busy lock, ensuring it's set once."""
    lock = getattr(current_app, "_busy_lock", None)
    if lock is None:
        lock = threading.Lock()
        current_app._busy_lock = lock
    return lock


def run_with_app_context(app, func: Callable[[], None]) -> None:
    with app.app_context():
        func()


def spawn_broadcasting_task(work: Callable[[], None], *, error_prefix: str) -> None:
    """Run ``work`` under the busy lock in a daemon thread; broadcast error/done on the token bus."""

    def _runner() -> None:
        lock = get_busy_lock()
        with lock:
            try:
                work()
            except Exception as exc:
                from src.api.shared import token_broadcaster

                token_broadcaster.broadcast("error", f"{error_prefix}: {exc}")
            finally:
                from src.api.shared import token_broadcaster

                token_broadcaster.broadcast("done", "")

    app = current_app._get_current_object()
    threading.Thread(
        target=run_with_app_context, args=(app, _runner), daemon=True
    ).start()
