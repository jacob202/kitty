"""
Rich spinner and progress utilities for better UX.
"""

import sys
import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import Optional

try:
    from rich.console import Console
    from rich.live import Live
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeRemainingColumn,
    )
    from rich.spinner import Spinner

    CONSOLE = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    CONSOLE = None


class SimpleSpinner:
    """Fallback spinner for when rich is not available."""

    frames = ["⠋", "⠐", "⠠", "⠤", "⸤", "⠴", "⠧", "⠇"]
    _instance: Optional["SimpleSpinner"] = None

    def __init__(self, message: str = "Processing"):
        self.message = message
        self.running = False
        self.thread: threading.Thread | None = None
        self.idx = 0

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.daemon = True
        self.thread.start()

    def _spin(self):
        while self.running:
            sys.stdout.write(
                f"\r{self.message}... {self.frames[self.idx % len(self.frames)]} "
            )
            sys.stdout.flush()
            time.sleep(0.1)
            self.idx += 1
        self.stop()

    def stop(self):
        self.running = False
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()

    def update(self, message: str):
        self.message = message


def spinner(message: str = "Processing", show_time: bool = True):
    """
    Decorator for adding spinner to a function.

    Usage:
        @spinner("Processing file")
        def long_operation():
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if RICH_AVAILABLE:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TimeRemainingColumn(),
                    console=CONSOLE,
                ) as progress:
                    task = progress.add_task(message, total=None)
                    result = func(*args, **kwargs)
                    progress.update(task, completed=True)
                    return result
            else:
                spin = SimpleSpinner(message)
                spin.start()
                try:
                    return func(*args, **kwargs)
                finally:
                    spin.stop()

        return wrapper

    return decorator


def with_spinner(message: str, func: Callable, *args, **kwargs):
    """
    Run a function with a spinner.

    Returns: (result, elapsed_time_ms)
    """
    start = time.time()
    if RICH_AVAILABLE:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=CONSOLE,
        ) as progress:
            task = progress.add_task(message, total=None)
            try:
                result = func(*args, **kwargs)
                progress.update(task, completed=True)
                return result, (time.time() - start) * 1000
            except Exception as e:
                progress.stop()
                raise e
    else:
        spin = SimpleSpinner(message)
        spin.start()
        try:
            result = func(*args, **kwargs)
            return result, (time.time() - start) * 1000
        finally:
            spin.stop()


class ProgressTracker:
    """Track progress of multi-step operations."""

    def __init__(self, total: int, message: str = "Processing"):
        self.total = total
        self.current = 0
        self.message = message
        self.start_time = time.time()

    def update(self, advance: int = 1):
        self.current += advance

    @property
    def percent(self) -> float:
        return (self.current / self.total * 100) if self.total > 0 else 0

    @property
    def elapsed_ms(self) -> float:
        return (time.time() - self.start_time) * 1000

    @property
    def eta_ms(self) -> float:
        if self.current == 0:
            return 0
        return (self.elapsed_ms / self.current) * (self.total - self.current)

    def __str__(self) -> str:
        return f"{self.message}: {self.current}/{self.total} ({self.percent:.0f}%) - ETA: {self.eta_ms:.0f}ms"
