# Session Handoff — 2026-07-05 (Fable overnight/day session)

## What happened (in order)

1. **Shipped the packet run:** 015 phone channel (#103), 021 project
   registry (#106), 016 next-step navigator (#107) — each built, tested,
   manually verified against a real gateway, PR'd, merged.
2. **Jacob went live.** First time Kitty actually ran for him:
   - Fixed his stale local main (two macOS `Icon\r` files inside `.git/`
     broke pulls — `find .git -type f -iname 'Icon*' -delete`).
   - LiteLLM wouldn't start: `~/kitty-services/venv-litellm` was missing
     the proxy extras → `pip install 'litellm[proxy]'` fixed it (plus its
     cold start is now slow — doctor can race it; re-run doctor).
   - Another `Icon\r` inside the project venv broke chromadb — same fix.
   - Gmail OAuth completed (Desktop-app client), `PUSH_IMESSAGE_RECIPIENT`
     set. **Doctor: pass=11 warn=1 fail=0.** First real B generated.
3. **Wave-3 hardening from watching him live** — PR #109: refresh degrades
   instead of 500ing when the model is down (D9 shape), PATCH /projects,
   `./kitty project add|list|refresh|next|set-path`, doctor `env:parse`
   (his `.env` line 1 has a stray quote — still there, cosmetic), source
   timeout 5→10s.
4. **Docs close-out + wave 4 open** — this PR: 016 flipped to shipped;
   021/022 numbering collision from #101/#102 fixed (files renumbered
   023/024, registered, L-CAND-12 written, intake gate now names the
   rule); **017 authored executor-ready** (Wave 4 = move-in day);
   **025 authored** (imagegen v2 — Jacob's explicit request).

## Live warnings for the next session

- **Jacob pasted his entire `.env` (all API keys) into chat twice.**
  Advised rotating GITHUB_PAT + legacy token at minimum. Not done as of
  handoff — worth a gentle check-in, not a lecture.
- His live imagen checkout is under `~/Projects/`, NOT this repo's
  `mcp/imagen/` copy ("it's in projects not kitty") — 025 step 0 covers
  the reconciliation. Do not build imagen features into this repo's copy
  without doing that preflight.
- `python-dotenv could not parse statement starting at line 1` on every
  command on his Mac = the stray quote, not a real failure. #109's doctor
  check names it; the fix is deleting one character in `.env` line 1.
- Codex's 008-remainder worktree claim is from 2026-07-04 and hasn't been
  heard from — verify before treating it as taken.

## The thread (D13 context, do not lose)

Jacob's sequencing, his words: build the basic thing, verify it works,
THEN "magic kitty" — cross-project insight (packet 022). 016's week of
real Bs is the verification step. Magic comes next, not never, and not
smuggled into 016.

## Open PRs at handoff

- #109 wave-3 hardening (CI was running; merge when green)
- wave-4 docs PR (this branch)
- #108 registry flip — superseded by the docs PR; close it
# Session Handoff — 2026-07-06 (long opencode session: Track B + C + salvage port)

## Status

- 016 reviewed — already merged (#107), awaiting Jacob's real-Bs review to close out.
- 017 authored, built, PR #112 open.
- C3 cron DB consolidation **live on main** (direct push, no PR — per Jacob's "leave it").
- Prefetcher landed (other model).
- Memory Weave ported from `~/Projects/kitty-salvage/memory/memory_weave.py` (all 11 methods + 17 tests).
- `main` ahead of `origin/main` by 0 (all pushed).

## Completed this session

- **Track B (full)**: docs/adr/ (14 ADRs), docs/codemap/ (5 lens docs), docs/plans/, npm ELOOP fix (gateway/kitty-chat/.npmrc with `script-shell=/bin/sh`), pre-commit Icon block (scripts/check-no-macos-metadata.sh + .pre-commit-config.yaml), repair_gateway_envs.sh `${HOME}` brace fix, DECISIONS.md slimmed to index, SIRI_SHORTCUT.md rewritten, PROJECT_STATUS.md test-state refresh. 1133 tests pass at Track B close.
- **Track C (full, mostly)**: C1 Removed Modules (6 modules), C2 LEARNINGS.md L-CAND-2 closed, C4 codemap (already in Track B), C5 context_assembler tightened, C6 doc sprawl (other model), C7 codemap_test.py (104 modules tested).
- **C3 cron DB consolidation**:
  - C3-0 dry run: `docs/phases/PHASE_C3_PLAN.md` + `scripts/dry_run_c3.py` + `gateway/migrations/012_cron_schedules.sql`.
  - C3-2: `gateway/cron.py` rewritten to use `kitty.db` (table `cron_schedules`) with one-shot legacy import shim. 22 cron tests + 1242 total.
  - C3-3 live run: dry run green (0 rows), final snapshot saved, `kitty up` succeeded, `kitty doctor --json` returns 11 pass / 2 warn / 0 fail, `kitty backup` includes `cron_schedules` in kitty.db, legacy `data/cron_schedules.db` kept as rollback source.
  - Committed and pushed **direct to main** (Jacob said "leave it" when offered the PR route).
- **Prefetcher** (other model, committed and pushed by me): `gateway/prefetcher.py` (188 LOC), wraps `unified_context` in `gateway/memory_graph.py`, `prefetch.warm` cron action. 8 tests.
- **Memory Weave port** (from salvage): migration 013 (`gateway/migrations/013_memory_weave.sql`), `gateway/memory_weave.py` (all 11 public methods + 4 private helpers), `tests/test_memory_weave.py` (17 tests). 1269 tests pass.

## In flight (left for next session)

- **017 (PR #112 open)** — benefits/admin deadline rails. Review/merge when CI green.
- **C3-4 cleanup** — delete `data/cron_schedules.db`, drop `_import_legacy_cron_once` shim. **Defer ~1 week** from C3-3 (2026-07-06) per `docs/phases/PHASE_C3_PLAN.md`. Target window: 2026-07-13+. Verify: 7 days of clean `./kitty doctor` + no consumer of the legacy path.
- **MemoryWeave integration** — module is landed + tested but not wired into the call paths (`unified_context`, `context_assembler`, the prefetcher's predictive layer). The salvage dig says weave is "the fabric the prefetcher builds on" — wiring it in would unlock adaptive learning from the prefetched queries.
- **Salvage port queue** (per `~/Projects/kitty-salvage/README.md` dig verdict):
  - `correction_memory.py` (931 LOC) — "highest long-term value," self-correcting memory.
  - `context_hierarchy.py` (284) — hierarchical context assembly. **Smallest pick** if a quick port is wanted next session.
  - `kitty_builder.py` (3,678) — old tool, would need re-homing onto `gateway/builder.py` + cron store. Different subsystem from Memory Weave.

## Gotchas

- `main` and `origin/main` are in sync (last push: `d114e09 feat(memory-weave): port remaining 6 public methods + tests`).
- C3 cron is on main as a **direct push, not a PR**. The user knows and chose this ("the difference between a poll and a push is the poll gets a review first" — he said "leave it" after I offered the revert+PR route).
- Other model did some work in parallel during this session (prefetcher, doc renames, packet 017 spec). Both committed to main cleanly.
- The `unified_context` wrapper in `memory_graph.py` has a cache-pollution failure mode for tests. `test_memory_graph.py` now has an autouse fixture to clear `prefetcher._cache` between tests.
- `feab407` and `feab407` corrupt remote refs (`refs/heads/Icon?` etc.) were cleaned up earlier in the session. If new ones appear, `find .git/refs -name '*Icon*' -delete`.
- C3 plan's non-goals (per `docs/phases/PHASE_C3_PLAN.md`): autonomy_state.db is its own plan, todos.db is already migrated, model_digest.db is explicitly deferred.
- MemoryWeave module is a port; not yet wire-up. Adding to `unified_context` would be a small, well-scoped change but needs a test or two.

## Cross-references

- Plan: `docs/plans/chore-master-fix-and-deepen.md` (3 tracks, all 7 of C done).
- Codemap: `docs/codemap/README.md` + 5 lens docs (overview, capabilities, dataflow, codemap, domain).
- ADRs: `docs/adr/README.md` + 14 numbered decisions.
- C3 plan: `docs/phases/PHASE_C3_PLAN.md`.
- Salvage dig: `~/Projects/kitty-salvage/README.md` (4.7K) and `~/Projects/kitty-archive-dig.html` (full verdict).
- Lessons: `docs/LEARNINGS.md` (L-CAND-2 closed 2026-07-06).
- Pre-commit: drops ruff-format/ruff --fix/prettier auto-fix hooks (commit 1abfcef) to avoid the index-corruption loop the salvage session was stuck in. Keep end-of-file-fixer (adds trailing newline, low risk).
