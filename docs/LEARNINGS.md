# Learnings

**Date:** 2026-06-20

## Durable Lessons

1. A writer without a reader kills the habit loop. Quick Capture only matters because inbox entries resurface through Kitty.
2. Stale handoffs are worse than no handoff. They create false confidence and waste the next session.
3. Abandoned paths need cleanup in the same phase. OpenWebUI leftovers caused port, doc, and test drift.
4. Localhost is not a security boundary. Keep gateway auth and host assumptions explicit.
5. Do not broaden architecture because the product feels exciting. Phase B is consolidation, not expansion.
6. Test counts must come from a command actually run in the current context.
7. Agent hooks must be simple enough to inspect; a hook with unreachable blocks is theater.

## Candidate Lessons (recovery session 2026-06-20)

### L-CAND-1 — Codex CLI runs concurrently and races the opencode agent on the same branch

- **Status:** candidate
- **Date:** 2026-06-20
- **Source session:** post-crash recovery on `codex/phase-b-prep`
- **Problem:** The host crashed with three opencode sessions + Codex CLI running. Codex came back to life after the crash and continued scaffolding B1 (`gateway/db.py` + `tests/test_db.py`) on the same branch. The opencode recovery session's pre-commit hook blocked one commit because `tests/test_db.py` was mid-edit and `from gateway import db` was racing.
- **Evidence:** `git log --oneline` shows `a919901 feat(storage): add phase b sqlite foundation` (Codex) landing at 19:40 — 6 minutes after the user thought "codex is done." `tests/test_db.py` and `gateway/db.py` mtime: 19:40:20–19:40:46, while the opencode session's first baseline pytest was at ~19:25 (got 544 passed, no `test_db.py`).
- **Scope:** repo-wide for any branch where the user runs Codex CLI alongside another agent.
- **Lesson:** Before staging a commit, check `ps -ef | grep codex` (or the equivalent) and `git status` for files you did not create. If another agent is mid-edit, stash your work and wait for it to land, then `git stash pop` and rerun tests.
- **Action for future agents:** Document the "Codex may be running concurrently" check in `docs/AGENT_RUNTIME.md` (done). Add a script under `scripts/` that asserts no other agent is writing to the repo before `git add` if this recurs.
- **Confidence:** high
- **Review trigger:** any future commit-blocked-by-mid-edit-elsewhere event.
- **Promotion target:** AGENT_RUNTIME if a second instance occurs.
- **Notes:** This is the underlying cause of the original 0b44932 scramble. Worth a stable rule.

### L-CAND-2 — D9 #1 "memory_graph shim collapse DONE 2026-06-18" overstates completion

- **Status:** candidate
- **Date:** 2026-06-20
- **Source session:** recovery session, when applying the D9 deepening-candidates hunk from stash
- **Problem:** The hunk claims D9 #1 is DONE 2026-06-18, but the six module-level `_XxxAdapter` shims (`gateway/memory_graph.py:393–399`) are still present, and `GraphResult._get_adapters()` (line 442–456) still falls through to `_default_adapters()`. The work is small and unblocking; the "DONE" label is wrong.
- **Evidence:** `git grep -n "_MemoryAdapter\|_KnowledgeAdapter\|_JournalAdapter\|_TracesAdapter\|_TodosAdapter\|_InboxAdapter" gateway/` returns the six shim definitions. `sed -n '442,456p' gateway/memory_graph.py` shows the `_get_adapters` fall-through. No external importers use the shims (verified by `git grep "_MemoryAdapter\|..."` excluding the shim file itself).
- **Scope:** local to `memory_graph.py` and any D9 deepening list referencing it.
- **Lesson:** When stashing/preserving a "done" claim across a crash, the next agent should verify the claim against the current tree before propagating it. The verification is cheap: read the lines you would touch.
- **Action for future agents:** When applying a stashed status-update hunk, run a quick `git grep` for the actual artifact (shim names, function names, version strings) and downgrade the status to "in progress" if any piece is still present.
- **Confidence:** high
- **Review trigger:** next D9 review pass.
- **Promotion target:** none (the lesson is narrow).
- **Notes:** Captured in `docs/PROJECT_STATUS.md` and the handoff.

### L-CAND-3 — `gh` "error connecting to github.com" is a misleading 401 mask

- **Status:** candidate
- **Date:** 2026-06-20
- **Source session:** PR #27/#28/#29 close pass
- **Problem:** `gh` returned `error connecting to github.com / check your internet connection` but curl could reach `github.com` and `api.github.com` in <1s. The actual problem was an invalid `GITHUB_TOKEN` env var shadowing the working keyring token. `gh auth login` would not have fixed it because env vars beat the keyring.
- **Evidence:** `gh auth status` showed "Failed to log in to github.com using token (GITHUB_TOKEN) — The token in GITHUB_TOKEN is invalid" and "Logged in to github.com account jacob202 (keyring) — Active account: false." After `unset GITHUB_TOKEN`, `gh api user --jq .login` returned `jacob202` and `gh pr list` worked.
- **Scope:** any session that uses `gh` and has `GITHUB_TOKEN` set in the env (kitty/.env or shell rc).
- **Lesson:** When `gh` says "check your internet," run `gh auth status` first. If a `GITHUB_TOKEN` is in env and marked invalid, `unset GITHUB_TOKEN` to fall through to the keyring.
- **Action for future agents:** None required at the runtime-rules level; this is operator-side. Note in the operator runbook.
- **Confidence:** medium
- **Review trigger:** any future `gh` "connection" error.
- **Promotion target:** none.
- **Notes:** Worth a paragraph in `docs/AGENT_RUNTIME.md` if this recurs, but not a stable operating rule.

### L-CAND-4 — Test counts vary between runs of the same suite (warnings count specifically)

- **Status:** candidate
- **Date:** 2026-06-20
- **Source session:** B0 baseline capture
- **Problem:** `python3.12 -m pytest tests/ -q --tb=short` returned 4 warnings on one run and 3 on another of the same checkout. The +1 is a `DeprecationWarning: builtin type swigvarlink has no __module__ attribute` from CPython that varies by Python build state. Pretending the warning count is stable leads to false "test count regressed" alarms.
- **Evidence:** Run 1 (post-prep): 544 passed, 2 deselected, 4 warnings. Run 2 (after B1): 547 passed, 2 deselected, 4 warnings. PROJECT_STATUS.md at one point claimed "3 warnings" — that was a transient.
- **Scope:** any pytest gate that compares warning counts.
- **Lesson:** Track passed/ deselected only. Treat warning counts as approximate. If a new warning type appears, that's a signal; +/-1 of an existing warning is not.
- **Action for future agents:** When you write a pytest gate or a "test count regressed" check, compare `passed` and `deselected` only, never `warnings`.
- **Confidence:** medium
- **Review trigger:** any new pytest gate.
- **Promotion target:** none (narrow).
- **Notes:** Not currently a rule anywhere; just a note.

### L-CAND-5 — `make agent-wrap` was not run for the recovery session; the handoff was filled manually

- **Status:** candidate
- **Date:** 2026-06-20
- **Source session:** recovery session
- **Problem:** The wrap-up protocol says "run `make agent-wrap`" but the recovery session filled `.agent/session_logs/20260620T012911Z-handoff.md` by hand because running `make agent-wrap` in mid-recovery would have created a handoff before the actual work was done.
- **Evidence:** The `.gitkeep` and the timestamped handoff were created at 19:29 by the prep commit (the handoff is gitignored, but its mtime shows it was written before the recovery session's first tool call). The recovery session rewrote the handoff body manually.
- **Scope:** any session that is itself a recovery.
- **Lesson:** The wrap-up script is for normal sessions. Recovery sessions can either rewrite the existing handoff in place (what we did) or run the script at the very end. Either is fine; the handoff just needs to be filled in before the session ends.
- **Action for future agents:** No code change. The exit-protocol section of `docs/AGENT_RUNTIME.md` could mention "or, for recovery sessions, edit the most recent `session_logs/*.md` in place." Optional.
- **Confidence:** low
- **Review trigger:** next recovery session.
- **Promotion target:** none.
- **Notes:** The script is fine; this is just a usage note.

## Candidate Lessons (rejected or not promoted)

Empty — nothing rejected this session that was strong enough to mention. The five above are the full candidate set.

## Promotion criteria (do not change these)

- Promote to `docs/AGENT_RUNTIME.md` only if: repeated, high-risk, repo-wide, clearly useful as an operating rule.
- Promote to `docs/DECISIONS.md` only if: actual architecture or workflow decision, alternatives were considered, rationale and tradeoffs recorded.
- Archive a learning if: stale, contradicted by current code, too narrow, duplicates another lesson, caused agent over-correction.

