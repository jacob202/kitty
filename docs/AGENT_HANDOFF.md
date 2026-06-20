# Agent Handoff

**Date:** 2026-06-20
**Branch:** `codex/phase-b-prep`
**Base:** `c6accd0`
**HEAD:** `e6a5712 docs+test(storage): rollback escape hatch (Phase C C5+C6)`

## What This Branch Is Doing

Preparing Kitty for Phase B by consolidating canonical docs, adding an agent wrap-up loop, and landing the first storage slices. **Phase B is fully shipped (B0–B5).** **Phase C chats is shipped (C0–C6)** — `data/kitty/chats.json` now lives in `data/kitty/kitty.db` via `gateway/chats_store.py`; the route reads and writes through it. It has not migrated journal, memory, ChromaDB, mem0, or broad user-facing episodic data. Todos are the first B3 seam. B4 has a thin write-side storage router for todo and plugin mutations. B5 has a local backup/restore drill for `data/kitty/`.

## Important Context

- Repo path: `/Users/jacobbrizinski/Projects/kitty`.
- Ignore stale app context pointing to `/Users/jacobbrizinski/Documents/Kitty`.
- Raycast wrapper work is preserved separately on `codex/raycast-quick-capture`.
- Dirty roadmap hunk was preserved in stash `phase-b-prep preserve roadmap deepening drift`.
- Latest local commit stack above `origin/main`: `0b44932` docs/agent handoff prep, `ca200f2` port text fix to `4000`, `a919901` SQLite foundation, `d39920f` plugin settings SQLite migration, `9fca1c0` todo SQLite seam, `742243c` db/plugin_registry formatting.

## Current Files Of Interest

- `START_HERE.md`
- `AGENTS.md`
- `CLAUDE.md`
- `CODEX.md`
- `docs/PHASE_B_ARCHAEOLOGY_REPORT.md`
- `docs/PROJECT_STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/PHASE_B_PLAN.md`
- `docs/STORAGE_MIGRATION_PLAN.md`
- `docs/AGENT_RUNTIME.md`
- `docs/LEARNINGS.md`
- `docs/DECISIONS.md`
- `gateway/db.py`
- `gateway/migrations/001_foundation.sql`
- `gateway/migrations/002_plugin_settings.sql`
- `gateway/migrations/003_todos.sql`
- `gateway/plugin_registry.py`
- `gateway/storage_router.py`
- `gateway/todo_store.py`
- `gateway/routes/extended.py`
- `gateway/routes/integrations.py`
- `gateway/chats_store.py`
- `gateway/routes/chats.py`
- `gateway/migrations/004_chats.sql`
- `scripts/kitty_backup.py`
- `scripts/pre-commit.template`
- `scripts/install-pre-commit.sh`
- `kitty`
- `tests/test_db.py`
- `tests/test_kitty_backup.py`
- `tests/test_kitty_launcher.py`
- `tests/test_plugin_registry.py`
- `tests/test_storage_router.py`
- `tests/test_todo_store.py`
- `tests/test_chats_store.py`
- `tests/test_chats_route.py`
- `scripts/agent_wrapup.py`

## Current Git State

```text
## codex/phase-b-prep
e6a5712 (HEAD -> codex/phase-b-prep, origin/codex/phase-b-prep) docs+test(storage): rollback escape hatch (Phase C C5+C6)
200e18a feat(storage): add one-time JSON import to chats_store (Phase C C4)
858a97d feat(routes): migrate /chats route to chats_store (Phase C C3)
c92a264 feat(storage): add chats_store read/write module (Phase C C2)
9f6a6b4 feat(storage): add chats table migration (Phase C C1)
5eaf699 docs(phase-c): plan for migrating chats to kitty db
209e7cb chore(hooks): add tracked pre-commit template + installer
1e7a7df chore(docs): migrate handoff to docs/AGENT_HANDOFF.md
5e22c7a feat(observability): record every chat call to JSONL (Lane E)
afbcd9f feat(gateway): central config + typed error hierarchy (Lane D)
900ac1a feat(storage): JSON import/export round-trip for migrated stores (Lane C)
f7ce8c9 chore(agent): ruff hook on .py writes, 3 phase skills, preflight script
b6045fa refactor: tighten path seam and dedup poll helper in builder/task_runner
0eb70c5 fix(brief): honest theme detection + journal source (issue #30)
4f4160a feat(storage): add kitty data backup drill
c6accd0 (origin/main, origin/HEAD, main) fix: repair broken-merge state on main (scrambled doctor.py + duplicated port) (#25)
```

Generated wrap-up logs under `.agent/session_logs/*.md` are ignored. Do not commit those generated logs unless Jacob explicitly asks.

## Verification To Run Before Commit

```bash
python3.12 -m py_compile scripts/agent_wrapup.py
python3.12 -m pytest tests/test_check_continuity_state.py tests/test_run_gates_script.py -q --tb=short
python3.12 -m pytest tests/ -q --tb=short
```

Latest local verification (2026-06-20, after Phase C chats migration):

- `python3.12 -m py_compile scripts/agent_wrapup.py` passed.
- `python3.12 -m pytest tests/test_chats_store.py tests/test_chats_route.py -q --tb=short` passed: 21 tests.
- `python3.12 -m pytest tests/test_db.py -q --tb=short` passed: 5 tests.
- `python3.12 -m pytest tests/test_kitty_backup.py tests/test_kitty_launcher.py -q --tb=short` passed: 11 tests.
- `make agent-wrap` is available; generated logs in `.agent/session_logs/*.md` are ignored unless Jacob explicitly asks to commit one.
- `python3.12 -m pytest tests/ -q --tb=short` passed: 654 passed, 2 deselected, 3 warnings.

## Known Open Work

- `codex/raycast-quick-capture` has useful unmerged Raycast wrapper work at `5a07744`.
- Older stashes remain for LLM routing and memory graph experiments; do not drop them without review.
- Pre-commit hook is now tracked via `scripts/pre-commit.template` and `scripts/install-pre-commit.sh`; the previously-unreachable code-review-graph block was removed. Resolved in `209e7cb`.
- Phase B B5 has a local `data/kitty/` backup drill. Phase C chats is shipped (C0–C6). Next: journal migration (Phase C B). Do not skip the explicit compat + rollback plan per `docs/PHASE_C_PLAN.md`.

## Next Implementation Prompt

Migrate journal to kitty.db (Phase C B) following the `docs/PHASE_C_PLAN.md` model: write a `docs/PHASE_C_JOURNAL_PLAN.md` with explicit compat + rollback before any code lands, then C1 schema, C2 read/write module, C3 route migration, C4 import, C5 backup verification, C6 rollback test. The chats migration (`5eaf699` through `e6a5712`) is the model.

## Source-of-Truth Audit (2026-06-20)

The Phase B prep master prompt asked for a review of `decisions.jsonl`, `corrections.jsonl`, and similar prior-agent artifacts. Audit results:

- `decisions.jsonl`: **does not exist** in this repo (searched via `git ls-files | grep -E "decisions|corrections"`, returned nothing).
- `corrections.jsonl`: **does not exist**.
- `memory/`, `project_logs/`, `decisions.jsonl`, `corrections.jsonl`: none present at the repo root.
- `~/.claude/projects/`, `~/.codex/sessions/`: contain historical Claude/Codex session files but are out-of-scope for the repo-level canonical docs and not portable across tools.

The history we do have, and what we used instead:

- **`~/.local/share/opencode/opencode.db`** — read-only source for prior opencode session transcripts. Used during the 2026-06-20 recovery to reconstruct what three concurrent opencode sessions were doing before the host crashed. The `message` and `part` tables are the canonical record of in-flight work.
- **`git log`, `git stash list`, `git worktree list`** — durable history of commits, stashes, and worktrees. `git log --all --oneline` is the most reliable cross-tool history.
- **`.agent/session_logs/*.md`** — gitignored, local-only session wrap-up logs generated by `make agent-wrap`. Not portable, but useful for "what did this machine do last week."
- **Branch names** (`codex/raycast-quick-capture`, `codex/phase-b-prep`, `feat/desktop-phase1`, etc.) — carry meaningful labels for in-flight work. Treat them as first-class metadata.

Action for future agents: when the master prompt asks to "review old decision and correction sources," run `git ls-files | grep -iE "decisions|corrections|memory|project_log"`. If empty, the audit is: "no such files exist; durable history is in git, opencode.db, and `.agent/session_logs/`." Do not invent source files.

## Review Required

This section captures auto-edits from the 2026-06-20 gap-fill pass so the next agent can audit them.

- **Docs changed automatically:**
  - `docs/AGENT_RUNTIME.md` — added "Active Skills (as of 2026-06-20)" section listing the 36 dotclaude skills and the `setupdotclaude@dotclaude` plugin, plus a note about Codex running concurrently.
  - `docs/LEARNINGS.md` — added 5 candidate lessons (L-CAND-1 through L-CAND-5) from the recovery session.
  - `docs/AGENT_HANDOFF.md` — this section.
- **Docs archived automatically:** none.
- **Agent files changed automatically:** none. `AGENTS.md`, `CLAUDE.md`, `CODEX.md` are untouched.
- **Skills/hooks/MCP changes:** documented in `docs/AGENT_RUNTIME.md` (passive, not changed in this pass).
- **Candidate lessons added automatically:** 5 (see `docs/LEARNINGS.md`).
- **Decisions imported or updated:** none. The `decisions.jsonl` source file does not exist; the prompt's import step was a no-op for this repo.
- **Items needing human review:** none yet — all 5 candidate lessons are scoped and evidence-backed.
- **Items needing second-agent review:** L-CAND-1 (Codex race) is the only one worth a second pair of eyes for promotion to `docs/AGENT_RUNTIME.md`. The rest are narrow enough to stay in candidate status.
- **Risk level:** low. No functional app code changed.
- **Suggested review command:** `git diff docs/AGENT_RUNTIME.md docs/LEARNINGS.md docs/AGENT_HANDOFF.md`.
- **Suggested review order:** AGENT_RUNTIME (skills list accuracy) → LEARNINGS (lesson phrasing + evidence) → AGENT_HANDOFF (this section).
