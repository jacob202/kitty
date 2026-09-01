#!/usr/bin/env python3
"""Print a one-screen orientation block for the current Kitty worktree.

Gathers branch state, open PRs, test-collection count, service health,
the current blocking packet, local-only branches, and the most recent
session note. No deps beyond the stdlib plus the `gh` and `git` CLIs.

Run: `python3.12 scripts/resume.py` or `./kitty resume`.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import subprocess as sp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# gh picks up a stale ambient GITHUB_TOKEN ahead of the keyring auth; drop it.
os.environ.pop("GITHUB_TOKEN", None)


def run(cmd: list[str], timeout: int) -> sp.CompletedProcess:
    """Run a command, returning a CompletedProcess even on timeout or a missing binary."""
    try:
        return sp.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=timeout)
    except sp.TimeoutExpired:
        return sp.CompletedProcess(cmd, -1, "", f"timeout after {timeout}s")
    except FileNotFoundError:
        return sp.CompletedProcess(cmd, -1, "", f"{cmd[0]}: not found on PATH")


def open_prs() -> list[str]:
    r = run(["gh", "pr", "list", "--json", "number,title,state", "--limit", "50"], 10)
    if r.returncode != 0:
        return [f"gh: {(r.stderr or r.stdout).strip().splitlines()[0] if (r.stderr or r.stdout).strip() else 'unknown error'}"]
    try:
        items = json.loads(r.stdout or "[]")
    except json.JSONDecodeError as exc:
        return [f"gh: bad JSON ({exc})"]
    return [f"#{p['number']} {p['title']}" for p in items] or ["none"]


def test_count() -> str:
    r = run(
        ["python3.12", "-m", "pytest", "tests/", "-q", "--co",
         "--ignore=tests/test_llm_client_alt_ua.py"],
        timeout=15,
    )
    blob = r.stdout + r.stderr
    match = re.search(r"\d+/\d+ tests collected", blob)
    if match:
        return match.group(0)
    if r.returncode == -1:
        return "collect timeout (pytest >15s)"
    return f"collect failed (exit {r.returncode})"


def doctor_summary() -> str:
    r = run(["./kitty", "doctor", "--json"], timeout=20)
    if r.returncode != 0 and not r.stdout.strip():
        return f"doctor failed (exit {r.returncode}: {(r.stderr or '').strip()[:60]})"
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return "doctor: bad JSON"
    s = data.get("summary", {})
    return f"pass={s.get('pass', 0)} warn={s.get('warn', 0)} fail={s.get('fail', 0)}"


def packet_state() -> tuple[str, list[str]]:
    """Return (active_packet, blocked_packets).

    The packet registry uses ✓/📋/⛔/✏️ rather than a literal 🔄. We treat
    the first non-shipped, non-blocked row as "active" and any ⛔ row as
    "blocked". Falls back to "(none)" and [] when the file is missing.
    """
    path = ROOT / "docs" / "packets" / "README.md"
    if not path.exists():
        return "(none)", []
    active = ""
    blocked: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4 or not re.match(r"\d{3}", cells[0]):
            continue
        status = cells[3]
        if "shipped" in status.lower():
            continue
        if "⛔" in status:
            blocked.append(f"{cells[0]} {cells[1]}")
        elif not active:
            active = f"{cells[0]} {cells[1]}"
    return active or "(none)", blocked


def branch_state() -> tuple[str, bool]:
    # --abbrev-ref returns the literal "HEAD" in detached state, so the output
    # is a stable string callers (and tests) can assert on.
    br = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], 5).stdout.strip() or "HEAD"
    dirty = bool(run(["git", "status", "--porcelain"], 5).stdout.strip())
    return br, dirty


def local_only_branches(current: str) -> list[str]:
    remote = {x[len("origin/"):] for x in
              run(["git", "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/"], 5)
              .stdout.split() if x.startswith("origin/")}
    local = run(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"], 5).stdout.split()
    return [b for b in local if b not in remote and b not in ("HEAD", current)]


def last_session_note() -> str:
    sd = ROOT / ".agent" / "session_logs"
    if not sd.is_dir():
        return "(none yet)"
    files = [p for p in sd.iterdir() if p.is_file() and p.name != ".gitkeep"]
    return files[-1].name[:32] if files else "(none yet)"


# ── ANSI helpers (stdlib only, no external deps) ──────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def section(title: str) -> None:
    """Print a bold cyan section header with an underline."""
    print(f"\n{BOLD}{CYAN}{title}{RESET}")
    print(f"{CYAN}{'─' * len(title)}{RESET}")


def status_badge(ok: bool, label: str = "") -> str:
    """Return a green ✓ or red ✗ badge, optionally with a label."""
    badge = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
    return f"{badge} {label}" if label else badge


def format_table(rows: list[tuple[str, str]], indent: int = 2) -> None:
    """Print a left-aligned two-column table with the first column padded."""
    if not rows:
        return
    pad = max(len(r[0]) for r in rows) + 2
    prefix = " " * indent
    for a, b in rows:
        print(f"{prefix}{a:<{pad}}{b}")


def main() -> int:
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        f_prs = ex.submit(open_prs)
        f_tests = ex.submit(test_count)
        f_doc = ex.submit(doctor_summary)
    branch, dirty = branch_state()
    active, blocked = packet_state()
    local = local_only_branches(branch)

    def join_short(items: list[str], limit: int = 10) -> str:
        if not items:
            return "none"
        if len(items) <= limit:
            return ", ".join(items)
        return ", ".join(items[:limit]) + f" (+{len(items) - limit} more)"

    # ── Header ────────────────────────────────────────────────────────
    print(f"{BOLD}Kitty{RESET} — {dt.date.today().isoformat()}")

    # ── Git & PRs ─────────────────────────────────────────────────────
    section("Git")
    format_table([
        ("Branch:", f"{branch} {YELLOW}[dirty]{RESET}" if dirty else f"{branch} (clean)"),
    ])

    prs = f_prs.result()
    pr_summary = "; ".join(prs) if prs else "(none)"
    format_table([
        ("Open PRs:", pr_summary),
    ])

    # ── Tests ─────────────────────────────────────────────────────────
    section("Tests")
    tests = f_tests.result()
    test_ok = bool(re.search(r"\d+ collected", tests)) and "failed" not in tests.lower()
    format_table([
        ("Collected:", f"{status_badge(test_ok)} {tests}"),
    ])

    # ── Services ──────────────────────────────────────────────────────
    section("Services")
    doctor = f_doc.result()
    # doctor summary is "pass=N warn=M fail=K"
    m = re.match(r"pass=(\d+) warn=(\d+) fail=(\d+)", doctor)
    if m:
        p, w, f = int(m.group(1)), int(m.group(2)), int(m.group(3))
        parts = []
        parts.append(f"{GREEN}{p} pass{RESET}" if p else f"{p} pass")
        parts.append(f"{YELLOW}{w} warn{RESET}" if w else f"{w} warn")
        parts.append(f"{RED}{f} fail{RESET}" if f else f"{f} fail")
        format_table([("Checks:", ", ".join(parts))])
    else:
        format_table([("Checks:", doctor)])

    # ── Packets ───────────────────────────────────────────────────────
    section("Packets")
    format_table([
        ("Active:", active),
        ("Blocked:", join_short(blocked)),
    ])

    # ── Misc ──────────────────────────────────────────────────────────
    section("Workspace")
    format_table([
        ("Local-only:", join_short(local)),
        ("Last session:", last_session_note()),
    ])

    return 0


if __name__ == "__main__":
    sys.exit(main())
