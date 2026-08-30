# Packet 006 — Project Resume / Continuity

**Status:** Ready to build
**Date:** 2026-07-02
**Depends on:** nothing (001 shipped)

---

## Problem

Every agent session starts with doc archaeology: read START_HERE → PROJECT_STATUS → AGENT_HANDOFF → scan DECISIONS → check open PRs. This takes 3–5 minutes of context and still misses orphaned branches. The symptom is visible: the audit that produced this packet queue was itself a 30-minute archaeology session.

The gap isn't missing state — it's that state is scattered across 6+ docs with no single "pick up exactly where you left off" entrypoint.

---

## What We're Building

A `./kitty resume` command (or `/resume` skill alias) that produces a single-screen orientation block:

```
Kitty — 2026-07-02

Branch:       main (clean)
Open PRs:     #65 — action queue + tier sheet [WAITING: Jacob's sign-off]
Tests:        803 passed / 4 failed (continuity gate) / 1 collection error
Services:     down (run ./kitty up)

Active packet: 003 (PR #65 merge) → then 004 (mascot state)
Blocked:       005 (Jacob picks mail path), 007 (needs 003)
Local-only:    codex/raycast-quick-capture, backup-local-main-0628 [at risk]

Last session:  2026-07-02 — doc cleanup + packet queue created
```

Agents read this instead of doing archaeology. Jacob reads this instead of asking "where were we."

---

## Acceptance Criteria

- [ ] `./kitty resume` (or `python3.12 scripts/resume.py`) prints the orientation block above
- [ ] Block includes: branch + dirty state, open PRs (via `gh pr list`), test pass/fail counts (fast run), service state (`./kitty doctor`), current blocking packet, local-only branches
- [ ] Output is under 30 lines
- [ ] Runs in under 10 seconds on a cold Mac (services down)
- [ ] `/resume` alias in the Claude Code skill system calls the same script
- [ ] One test: `test_resume_script.py` — asserts the script exits 0 and output contains branch name and today's date

---

## Implementation Sketch

```python
# scripts/resume.py
# ponytail: single file, no deps beyond stdlib + gh CLI + git

import subprocess, json, datetime, sys

def run(cmd): return subprocess.run(cmd, capture_output=True, text=True)

branch = run(["git", "branch", "--show-current"]).stdout.strip()
dirty  = bool(run(["git", "status", "--porcelain"]).stdout.strip())
prs    = json.loads(run(["gh", "pr", "list", "--json", "number,title,state"]).stdout or "[]")
doctor = json.loads(run(["./kitty", "doctor", "--json"]).stdout or "{}")
# fast test count: pytest --co -q, count lines
tests  = run(["python3.12", "-m", "pytest", "tests/", "-q", "--co",
              "--ignore=tests/test_llm_client_alt_ua.py"]).stdout

# read last-session note from .agent/session_logs/ most recent file
# read current packet from docs/packets/README.md (parse first 🔄 row)

print(f"Kitty — {datetime.date.today()}\n")
print(f"Branch:  {branch}{'  [dirty]' if dirty else ''}")
# ... etc
```

---

## What's Not In This Packet

- Persistent session log (the `.agent/session_logs/` hook already writes these; this packet just reads the latest)
- Honcho sync or cloud state
- Interactive TUI — plain text output only

---

## Follow-on (name it, don't build it)

After `resume` is working, the natural next step is wiring it into the Stop hook so it prints on session end, not just start. That's a one-liner in `.claude/hooks/stop.sh` — note it for packet 006b if Jacob wants it.
