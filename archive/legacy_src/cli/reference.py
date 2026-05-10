#!/usr/bin/env python3
"""Terminal Quick Reference — Rich rendered, multi-column, color-coded.

Usage:
    python3 -m src.cli.reference          # full reference
    python3 -m src.cli.reference git      # filter by section/term
    python3 -m src.cli.reference kitty    # show only KITTY section
"""

import sys
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# ── Raw section data (title, rows, color) ──────────────────────────────
SECTIONS: list[tuple[str, list[tuple[str, str]], str]] = [
    ("NAVIGATION", [
        ("ls", "List files (eza icons)"),
        ("ll", "Sizes, dates, perms"),
        ("cd <dir>", "Change directory"),
        ("cd ..", "Up one level"),
        ("cd ~", "Go home"),
        ("pwd", "Print working dir"),
        ("z <name>", "Fuzzy jump"),
        ("tree", "Directory diagram"),
    ], "green"),

    ("FILES", [
        ("cat <file>", "Read file (colorised)"),
        ("cp <a> <b>", "Copy file"),
        ("mv <a> <b>", "Rename / move"),
        ("rm <file>", "Delete permanently"),
        ("rm -r <dir>", "Delete directory"),
        ("mkdir <dir>", "Create directory"),
        ("open .", "Open Finder here"),
        ("open <file>", "Default app"),
    ], "blue"),

    ("SEARCH", [
        ("fzf", "Fuzzy file search"),
        ("Ctrl+R", "Search history"),
        ("↑ / ↓", "Previous commands"),
        ("Tab", "Autocomplete"),
        ("history", "All commands"),
    ], "yellow"),

    ("KEYBOARD", [
        ("Ctrl+C", "STOP / panic"),
        ("Ctrl+Z", "Pause (fg resumes)"),
        ("Ctrl+L", "Clear screen"),
        ("Ctrl+A", "Jump line start"),
        ("Ctrl+E", "Jump line end"),
        ("Ctrl+W", "Delete word back"),
        ("Cmd+T", "New terminal tab"),
        ("Cmd+D", "Split pane"),
    ], "magenta"),

    ("WHEN STUCK", [
        ("Ctrl+C", "Frozen? Press first"),
        ("q", "Quit viewer (man, log)"),
        (":q!", "Force quit vim"),
        ("exit", "Close this tab"),
        ("which <cmd>", "Find executable"),
        ("echo $PATH", "Show search paths"),
        ("tldr <cmd>", "Human-friendly help"),
    ], "red"),

    ("SYSTEM", [
        ("btop", "CPU / memory monitor"),
        ("df -h", "Disk space"),
        ("du -sh <dir>", "Folder size"),
        ("lsof -i :<port>", "What's on port?"),
        ("kill <PID>", "Stop process"),
    ], "orange1"),

    ("GIT", [
        ("lazygit", "Visual interface"),
        ("git status", "Changed files"),
        ("git diff", "Line-by-line diff"),
        ("git add .", "Stage all"),
        ("git commit -m", "Save snapshot"),
        ("git log --oneline", "History"),
        ("git stash", "Hide changes"),
        ("git stash pop", "Restore"),
    ], "white"),

    ("AI TOOLS", [
        ("claude", "Claude Code"),
        ("ai1", "Ollama llama3.2 (local)"),
        ("ai2", "DeepSeek V3 (cheap)"),
        ("ai3", "R1 plan + DeepSeek code"),
        ("air", "R1 chain-of-thought"),
        ("aider-kitty", "Aider in project"),
        ("mlx_lm.chat", "Apple GPU chat"),
        ("crush", "AI assistant (config)"),
    ], "cyan"),

    ("KITTY", [
        ("kitty", "Start + open browser"),
        ("kitty stop", "Shut down"),
        ("kitty restart", "Reload changes"),
        ("kitty logs", "Realtime server log"),
        ("kitty status", "Running? URLs"),
        ("kitty ref", "This reference"),
    ], "bright_magenta"),
]


def _section(title: str, rows: list[tuple[str, str]], color: str = "cyan") -> Panel:
    cmd_w = max(len(c) for c, _ in rows)
    desc_w = max(len(d) for _, d in rows)
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column("cmd", style=f"bold {color}", width=cmd_w, no_wrap=True)
    t.add_column("desc", style="white", width=desc_w)
    for cmd, desc in rows:
        t.add_row(cmd, desc)
    return Panel(t, title=f"[bold {color}]{title}[/bold {color}]",
                 border_style=f"dim {color}", padding=(0, 1),
                 width=cmd_w + desc_w + 8)


def _greedy_columns(panels, console, padding=(0, 1)):
    """Pack panels into rows using greedy width-fitting algorithm.

    Each row becomes an independent Columns renderable with only the
    panels that fit together within console.width.  This avoids Richʼs
    built‑in newspaper-column distribution which forces a single column
    when the widest items in each column overflow together.
    """
    rows = []
    current_row = []
    current_w = 0
    gap = padding[1] if len(padding) > 1 else 0
    for p in panels:
        w = getattr(p, "width", None)
        if w is None:
            w = console.measure(p).maximum
        needed = w + (gap if current_row else 0)
        if current_row and current_w + needed > console.width:
            rows.append(Columns(current_row, equal=False, padding=padding))
            current_row = [p]
            current_w = w
        else:
            current_row.append(p)
            current_w += needed
    if current_row:
        rows.append(Columns(current_row, equal=False, padding=padding))
    return rows


def print_reference(filter_term: str = "") -> None:
    """Print color-coded multi-column terminal reference, optionally filtered."""
    term = filter_term.strip().lower()

    # ── Title ──
    console.print()
    label = f"🐱  TERMINAL QUICK REFERENCE" + (f"  ·  [yellow]{filter_term}[/yellow]" if term else "")
    console.print(Panel(f"[bold cyan]{label}[/bold cyan]",
                  border_style="cyan", padding=(0, 1)))

    # ── Filter sections if requested ──
    panels = []
    for title, rows, color in SECTIONS:
        if not term:
            panels.append(_section(title, rows, color))
            continue
        if term in title.lower():
            panels.append(_section(title, rows, color))
        else:
            matching = [(c, d) for c, d in rows if term in c.lower() or term in d.lower()]
            if matching:
                panels.append(_section(title, matching, color))

    if not panels:
        console.print(f"\n  [yellow]No matches for '[bold]{filter_term}[/bold]'[/yellow]")
        console.print(f"  [dim]Try: kitty ref git | kitty ref kitty | kitty ref search[/dim]\n")
        return

    console.print()

    # ── Render sections in columns ──
    for row in _greedy_columns(panels, console):
        console.print(row)

    # ── Bottom panels (side-by-side when room) ──
    if not term:
        console.print()

        modes = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        modes.add_column("mode", style="bold", width=14)
        modes.add_column("model", style="white", width=36)
        modes.add_column("desc", style="dim", width=28)
        modes.add_row("⚡ FAST", "OpenRouter free router", "Responsive · zero-cost default")
        modes.add_row("◈ BALANCED", "Configured online model", "Cheap/free · long context")
        modes.add_row("★ MAX", "DeepSeek R1 (remote)", "Full reasoning")
        modes.add_row("THINK", "Toggle chain-of-thought", "See how it reasons")

        cmds = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        cmds.add_column("cmd", style="bold bright_magenta", width=20)
        cmds.add_column("desc", style="white", width=50)
        cmds.add_row("/brief", "Morning brief — where you left off")
        cmds.add_row("/stuck [task]", "ADHD rescue — one concrete next step")
        cmds.add_row("/bench <mode>", "Work mode (sansui, ridgeline, …)")
        cmds.add_row("/capture <thought>", "Quick brain dump")
        cmds.add_row("/review", "Show all captures + facts")
        cmds.add_row("/clear", "Wipe conversation history")
        cmds.add_row("/help", "Full command list")

        for row in _greedy_columns([
            Panel(modes, title="[bold cyan]CHAT MODES[/bold cyan]",
                  border_style="dim cyan", padding=(0, 1)),
            Panel(cmds, title="[bold bright_magenta]SLASH COMMANDS[/bold bright_magenta]",
                  border_style="dim bright_magenta", padding=(0, 1)),
        ], console):
            console.print(row)

    console.print("  [dim]Type [bold]kitty ref[/bold] any time to see this again · "
                  f"Phone: http://172.16.1.161:5001 (same WiFi)[/dim]")
    console.print()


if __name__ == "__main__":
    term = sys.argv[1] if len(sys.argv) > 1 else ""
    print_reference(term)
