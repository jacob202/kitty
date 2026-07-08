# Session Handoff — 2026-07-07 (Fable UX phase, slices 1–2)

## Status

- Branch `claude/fable-ux-phase` in `.worktrees/fable-ux-phase`, 5 commits, **unpushed** (git auth still broken for this box).
- Full log + remaining slices: `docs/planning/kitty-next-evolution-working-notes.md` (also committed on the branch).

## What landed

- next/font self-hosting (no Google CDN at first paint; PWA/offline safe); compat token aliases deleted, all components on real v2 tokens.
- ~90 usages of undefined old-palette CSS vars fixed (were silently unstyled).
- New `GET /logs/tail` (whitelisted, bounded) + tests; TerminalStrip tails the real gateway log — it previously invented random log lines.
- Chat: runStream extraction, retry-last-reply, hover copy/retry actions, cat state honestly bound (o_o streaming / ^_^ done / :[ broke); fake TopBar state chips removed.
- Verified in the running app with gateway down: honest error path end-to-end. UI 95/95, build green. Pytest 1310 pass; 3 pre-existing env failures (mem0, google.auth modules missing in local env), not from this diff.

## Next

1. Push + PR `claude/fable-ux-phase` (watch conflicts with packet-018's dirty UI files: DocumentsPanel, ProjectsPanel, queries.ts).
2. Slice 3: home cockpit click-throughs (017 deadlines, 016 next-step hero).
3. Slice 4 perf, Slice 5 mobile/PWA — sketched in the working notes.

---

# Session Handoff — 2026-07-07 (Kitty Builder port Phase 4)

## Status

- Work continued in `.worktrees/feat-port-kittybuilder` on branch `feat/port-kittybuilder`.
- Kitty Builder port Phases 1–4 are **complete and committed** in that worktree.
- Full Python suite: **1365 passed, 1 skipped**.
- Push to origin is blocked: the active `gh` OAuth token (`gho_...`) is rejected for git operations. Use SSH or a `ghp_...` personal access token to push.

## What landed in Phase 4

- `gateway/builder_cli.py` with `run`, `loop`/`repl`, `delegate`, `brief`, `contract validate`
- `gateway/builder/contract.py` for ISC contract validation/execution
- `gateway/doctor.py` extensions: worker probe checks, `llm:fallback_rate`, `llm:stream_untracked`
- `gateway/routes/builder.py` with `POST /builder/delegate`, `POST /builder/loop`, `GET /builder/budget`, `GET /builder/session/{id}`
- `./kitty builder <subcommand>` wired into the umbrella script
- Tests: `tests/test_builder_cli.py`, `tests/test_builder_contract.py`, `tests/test_doctor.py` additions

## Next

- Phase 5 cleanup: delete `~/Projects/kitty-salvage/kittybuilder/`, update `docs/ARCHITECTURE.md` + `AGENTS.md`, write ADR.
- Fix git auth and push `feat/port-kittybuilder`.

---

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
# Session Handoff — 2026-07-06 (PR #112 merge attempt)

## Status — PR #112 is CONFLICTING, needs merge resolution

## Completed this session

- **Fixed lint errors** in `gateway/deadline_store.py`, `tests/test_deadline_extractor.py`, `tests/test_deadline_sweep.py`, `tests/test_deadline_watch.py`, `tests/test_loops_insights_defake.py` — unused imports, unsorted imports, unused variable.
- **Fixed PR description** — added `## Test plan` section (check-description was failing).
- **Restored `gateway/prefetcher.py`** — C3-2 commit removed it, but main has `8f0fadd` that expects it. Restored from main.
- **Fixed `tests/test_cron.py::TestLegacyImport`** — `test_legacy_import_copies_rows` asserted `LEGACY_CRON_DB.exists()` (the real path) instead of `tmp_legacy_db.exists()` (the fixture path). Import was also stale — `LEGACY_CRON_DB` was captured before monkeypatch.
- **Renamed migration** `013_deadlines.sql` → `014_deadlines.sql` — main added `013_memory_weave.sql` in the meantime.
- **Pushed 5 commits** to `claude/packet-017-benefits-rails`:
  - `43b9c2f`: fix(lint): unused imports, import sorting, restore prefetcher.py
  - `2e46483`: fix(test): lint import sorting, legacy import assert uses tmp_legacy_db
  - `05a36ef`: chore: trigger CI
  - `74a8d60`: fix(migration): rename 013 -> 014 to avoid conflict with main's 013_memory_weave

## Still failing / blocking

### 1. Merge conflict — PR #112 is CONFLICTING

The PR's `mergeStateStatus` is `DIRTY`. The migration rename (013→014) should have resolved the file collision, but it's still conflicting. Likely suspects:

- **`gateway/prefetcher.py`**: The branch deleted it in C3-2 (`d286e02`), then I restored it from main (`main:gateway/prefetcher.py`). Main added it in `40be1ce`. Git sees both sides "adding" the file from different starting points — this may need manual resolution.
- **`tests/test_memory_graph.py`**: Main's `8f0fadd` adds `from gateway import prefetcher` + `_isolate_prefetch_cache` fixture back. The branch's version (from C3-2) doesn't have these. No merge conflict per se (main's change is additive from the base), but it depends on `prefetcher.py` existing.

### 2. Git repo has macOS Icon file corruption

Hundreds of `Icon` files (from macOS metadata) are scattered through `.git/` directories. These cause `fatal: bad object refs/Icon?` errors when running git operations from the worktree. Fetching and merging from the main repo directory also fails.

### 3. CI didn't trigger for latest commits

The last CI run was for `43b9c2f6` and it FAILED (lint had 1 error I001, test_cron had the legacy assert bug). My subsequent fixes (`2e46483`, `74a8d60`) never triggered CI — possibly because the conflict prevents PR CI from running.

## Next actions

1. **Resolve merge conflict** — the best approach is probably:
   - Close PR #112
   - Rebase the branch onto `main`, resolve conflicts in `gateway/prefetcher.py` and `tests/test_memory_graph.py`
   - Force-push and re-open PR
   - OR: use `gh pr merge` with a merge strategy that works around the conflict
2. **Clean up the git repo's Icon files** — `find .git -name "Icon" -delete` was run but may not have caught everything. The worktree's `.git` might still be affected.
3. **Trigger CI** — once the conflict is resolved, CI should run automatically on push.
4. **Verify all checks green** — then merge.

## Commits pushed (visible on GitHub)

```
3117859 feat(benefits): deadline rails, extractor, watch cron, sweep, routes
43b9c2f  fix(lint): unused imports, import sorting, restore prefetcher.py
2e46483  fix(test): lint import sorting, legacy import assert uses tmp_legacy_db
05a36ef  chore: trigger CI
74a8d60  fix(migration): rename 013 -> 014 to avoid conflict with main's 013_memory_weave
```
