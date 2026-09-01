"""Rich terminal output patterns — CLI utilities using the "rich" library.

Stolen from: Textualize/rich (MIT), Rich CLI examples (MIT), pip's CLI (MIT).

This module provides ready-to-use patterns for:
  1. Animated spinners (downloads, processing, LLM calls)
  2. Progress bars (file ingestion, batch processing)
  3. Colored tables (review sessions, knowledge stats)
  4. Panels and rule separators
  5. Live display updates

Usage:
    from gateway.rich_cli import spinner, progress, table, panel, console

    # Animated spinner
    with spinner("Thinking..."):
        result = llm_call()

    # Progress bar
    for chunk in progress(files, "Ingesting"):
        ingest(chunk)

    # Colored table
    table("Terms Due", [("term", "mastery"), ("async", 0.85)], ["Term", "Mastery"])
"""

from __future__ import annotations

import contextlib
from typing import Any, Generator, Sequence


# ---- Lazily import rich so it's never a hard dependency ----
# Kitty may run without rich installed in non-interactive mode.
def _rich():
    """Lazy import: returns (Console, Panel, Table, Progress, SpinnerColumn, ...)."""
    from rich.columns import Columns as _Columns
    from rich.console import Console as _Console
    from rich.layout import Layout as _Layout
    from rich.live import Live as _Live
    from rich.markdown import Markdown as _Markdown
    from rich.panel import Panel as _Panel
    from rich.progress import (
        BarColumn as _BarColumn,
    )
    from rich.progress import (
        Progress as _Progress,
    )
    from rich.progress import (
        SpinnerColumn as _SpinnerColumn,
    )
    from rich.progress import (
        TextColumn as _TextColumn,
    )
    from rich.progress import (
        TimeRemainingColumn as _TimeRemainingColumn,
    )
    from rich.progress import (
        TransferSpeedColumn as _TransferSpeedColumn,
    )
    from rich.prompt import Prompt as _Prompt
    from rich.status import Status as _Status
    from rich.syntax import Syntax as _Syntax
    from rich.table import Table as _Table
    from rich.text import Text as _Text
    return (
        _Console, _Panel, _Table, _Progress, _SpinnerColumn,
        _TextColumn, _BarColumn, _TimeRemainingColumn, _TransferSpeedColumn,
        _Live, _Layout, _Columns, _Text, _Syntax, _Markdown, _Prompt, _Status,
    )


# ---- Console singleton ----
_console_instance = None


def console() -> Any:
    """Get or create the shared Rich Console."""
    global _console_instance
    if _console_instance is None:
        Console, *_ = _rich()
        _console_instance = Console()
    return _console_instance


# ---- Pattern 1: Animated spinner ----

@contextlib.contextmanager
def spinner(text: str = "Working...") -> Generator[None, None, None]:
    """Show an animated spinner while a context manager runs.

    Example:
        with spinner("Searching knowledge base..."):
            results = knowledge.search(query)
    """
    try:
        Console, *_, Status = _rich()
        with Status(text, spinner="dots", console=console()):
            yield
    except ImportError:
        # Fallback: no rich installed
        print(f" {text}...", end="", flush=True)
        yield
        print(" done")


def status_spinner(text: str = "Working...") -> Any:
    """Get a Rich Status object for manual control (start/stop yourself)."""
    Console, *_, Status = _rich()
    return Status(text, spinner="dots", console=console())


# ---- Pattern 2: Progress bars ----

def progress(
    items: Sequence[Any],
    description: str = "Processing",
    transient: bool = False,
) -> Generator[Any, None, None]:
    """Iterate over items with a live progress bar.

    Example:
        for chunk in progress(documents, "Ingesting"):
            store.add(chunk)

    Args:
        items: Sequence of items to iterate over.
        description: Label shown next to the progress bar.
        transient: Remove the progress bar after completion.

    Yields:
        Each item, one at a time.
    """
    Console, *_, Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn = _rich()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console(),
        transient=transient,
    ) as progress_bar:
        task = progress_bar.add_task(description, total=len(items))
        for item in items:
            yield item
            progress_bar.advance(task)


def progress_download(
    total_bytes: int,
    description: str = "Downloading",
) -> Any:
    """Create a download-style progress bar with transfer speed.

    Returns a tuple of (progress_bar, task_id). Call
    progress_bar.advance(task_id, bytes_downloaded) as chunks arrive.

    Example:
        pb, tid = progress_download(file_size, "Fetching model")
        for chunk in response.iter_bytes():
            f.write(chunk)
            pb.advance(tid, len(chunk))
    """
    Console, *_, Progress, TextColumn, BarColumn, TransferSpeedColumn = _rich()

    progress_bar = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/1MB"),
        TransferSpeedColumn(),
        console=console(),
    )
    progress_bar.start()
    task_id = progress_bar.add_task(description, total=total_bytes)
    return progress_bar, task_id


# ---- Pattern 3: Colored tables ----

def table(
    title: str,
    rows: Sequence[tuple[Any, ...]],
    columns: Sequence[str] | None = None,
) -> None:
    """Print a colored table to the console.

    Example:
        table("Terms Due", [("async", 0.85), ("closure", 0.92)], ["Term", "Mastery"])

    Args:
        title: Table caption.
        rows: Sequence of row tuples.
        columns: Column headers. Auto-generated from the first row if None.
    """
    Console, *_, Table = _rich()
    tbl = Table(title=title, title_style="bold", border_style="dim")

    if columns is None and rows:
        columns = [f"Column {i+1}" for i in range(len(rows[0]))]

    for col in (columns or []):
        tbl.add_column(col, style="cyan", header_style="bold cyan")

    for row in rows:
        tbl.add_row(*[str(cell) for cell in row])

    console().print(tbl)


def panel(
    content: str,
    title: str = "",
    border_style: str = "blue",
) -> None:
    """Print content inside a styled panel.

    Example:
        panel("Hello, Kitty!", title="Greeting")
    """
    Console, Panel, *_ = _rich()
    p = Panel(content, title=title, border_style=border_style)
    console().print(p)


def rule(title: str = "") -> None:
    """Print a horizontal rule with an optional title.

    Example:
        rule("Knowledge Stats")
    """
    console().rule(title, style="dim")


# ---- Pattern 4: Live display ----

@contextlib.contextmanager
def live_display() -> Generator[Any, None, None]:
    """Context manager for live-updating displays.

    Example:
        with live_display() as live:
            for i in range(100):
                live.update(f"Progress: {i}%")
                time.sleep(0.05)
    """
    Console, *_, Live = _rich()
    with Live(console=console(), refresh_per_second=10) as live:
        yield live


# ---- Pattern 5: Syntax highlighted code ----

def syntax(code: str, language: str = "python") -> None:
    """Print syntax-highlighted code.

    Example:
        syntax('print("hello")')
    """
    Console, *_, Syntax = _rich()
    console().print(Syntax(code, language, theme="monokai"))


# ---- Pattern 6: Markdown rendering ----

def markdown(text: str) -> None:
    """Render Markdown to the terminal.

    Example:
        markdown("# Hello\n\nThis is **bold**")
    """
    Console, *_, Markdown = _rich()
    console().print(Markdown(text))


# ---- Pattern 7: Interactive prompt ----

def ask(question: str, default: str = "") -> str:
    """Ask the user a question with a prompt.

    Example:
        name = ask("What is your name?", default="Kitty")
    """
    Console, *_, Prompt = _rich()
    return Prompt.ask(question, default=default) if default else Prompt.ask(question)


def confirm(question: str, default: bool = True) -> bool:
    """Ask the user for a yes/no confirmation.

    Example:
        if confirm("Delete all data?"):
            wipe()
    """
    Console, *_, Prompt = _rich()
    return Prompt.ask(f"{question} [y/n]", choices=["y", "n"], default="y" if default else "n") == "y"


# ---- Pattern 8: Status line (single-line progress) ----

def status_line(text: str, done: bool = False) -> None:
    """Print or update a status line.

    Example:
        status_line("Loading model...")
        time.sleep(2)
        status_line("Loading model... done!", done=True)
    """
    icon = "✓" if done else "•"
    console().print(f" {icon} {text}", style="green" if done else "dim")
