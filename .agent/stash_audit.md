# Stash Audit — 2026-06-20

Inventory of all 15 stashes in this repo as of 2026-06-20. Generated during the
"triage 6+ older stashes" task on the `codex/phase-b-prep` branch. **No stashes
have been dropped** — per AGENTS.md and Jacob's preference, deletion needs
explicit OK. This document is the review packet.

## Stashes

| # | Ref | Branch | Subject | Age | Proposed action | Reason |
|---|---|---|---|---|---|---|
| 1 | stash@{0} | codex/raycast-quick-capture | backup llm routing drift during raycast wrapper | recent (this session area) | **KEEP** | Active branch work; may restore if the wrapper code is salvaged |
| 2 | stash@{1} | codex/quick-capture-shim | backup restored test adapter-name drift before rebase | pre-Phase B | **DROP** (after review) | The drift was the rename of adapter imports to underscore-prefix; those shims were just deleted (D9 #1); the test file `tests/test_memory_graph_unified.py` already uses the underscore names so the work is done |
| 3 | stash@{2} | codex/quick-capture-shim | backup restored memory_graph drift before rebase | pre-Phase B | **DROP** | Drift in memory_graph adapter module — already resolved by 2026-06-20 shim deletion |
| 4 | stash@{3} | codex/quick-capture-shim | backup restored drift after quick capture commit | pre-Phase B | **DROP** | Quick-capture work is abandoned; branch is stale |
| 5 | stash@{4} | codex/quick-capture-shim | backup unstaged adapter-underscore drift during quick capture | pre-Phase B | **DROP** | Same as #2 — work is now in tree |
| 6 | stash@{5} | main | backup stray llm_client memory_graph drift after main cleanup | pre-Phase B | **DROP** | LLM client work is stable; drift is obsolete |
| 7 | stash@{6} | main | backup dirty llm routing before main cleanup | pre-Phase B | **DROP** | LLM routing now has Lane E observability; this is stale |
| 8 | stash@{7} | main | codex WIP round 4 | pre-Phase B | **DROP** | Codex WIP rounds 2/3/4 are all superseded |
| 9 | stash@{8} | main | WIP codex round 3: half-rename test imports | pre-Phase B | **DROP** | Rename work done (or partially done) by D9 #1 commit |
| 10 | stash@{9} | main | WIP codex round 2: memory_graph + test_memory_graph + test_context_builder | pre-Phase B | **REVIEW** | May contain test improvements that didn't make it into a commit; needs `git stash show -p` to verify |
| 11 | stash@{10} | codex/code-sniping-inbox | WIP codex/code-sniping-inbox: rename adapters to private + new test_context_builder.py + memory_graph test updates | pre-Phase B | **REVIEW** | The rename-adapters-to-private work is the D9 #1 task — already in flight; the new test_context_builder may be valuable |
| 12 | stash@{11} | codex/code-sniping-inbox | WIP on codex/code-sniping-inbox: 104cc0e docs: add repository guidelines | pre-Phase B | **DROP** | The "add repository guidelines" content is in `AGENTS.md` (a later commit); this stash is the precursor attempt |
| 13 | stash@{12} | claude/phase-a-boring-to-operate | temp-pr17-fix2 | pre-Phase B | **DROP** | Phase A is done on main; PR #17 is closed; the temp fix is obsolete |
| 14 | stash@{13} | claude/refine-local-plan-N8b3p | a72340b docs(desktop): clean Gate 0 evidence formatting | pre-Phase B | **DROP** | Desktop Gate 0 evidence is finalized in main; this is an older formatting pass |
| 15 | stash@{14} | main | wip-before-mascot-checkout | old | **REVIEW** | Pre-mascot work — may have been the original mascot implementation; needs review |

## Summary

- **8 safe-to-drop** (after review): stash@{1}–8, stash@{11}–13
- **3 need review** before drop: stash@{9}, stash@{10}, stash@{14}
- **1 active** (do not drop): stash@{0} (codex/raycast-quick-capture)
- **2 already addressed by recent commits**: stash@{2} (shim deletion), stash@{9} (rename is partial)

## Recommended Next Action

1. Read each "REVIEW" stash with `git stash show -p stash@{N} | less` and decide.
2. After review, drop the "DROP" stashes with `git stash drop stash@{N}`.
3. Update this file with the result of the review.

## Verification

- `git stash list` should still show 15 stashes at the time of writing.
- No `git stash drop` has been run.
- `git status` is clean (no working-tree changes from the audit).

## Cross-References

- AGENTS.md "Git and PRs" — small commits, no rewriting history, no destructive operations without explicit OK.
- D9 #1 (this commit) — 6 module-level shims deleted from `memory_graph.py:393-398`; the test rename in `tests/test_memory_graph_unified.py` already uses the underscore-prefixed names so it should keep passing.
- CodeRabbit (this PR #32) — "centralized configuration and error handling into reusable modules" and "added LLM call observability and tracing" — the stash drop work is documentation only, not code.
