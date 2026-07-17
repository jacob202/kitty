# Handoff — 2026-07-17 — `chore/engineering-leverage-phase-8-9`

## Mission

The dogfooding loop is the highest-leverage move: make KittyBuilder strong
enough to use on itself, surface the useful state in Kitty UI, and stop as
soon as the next step stops paying back the tokens. Keep EL packaging and
Builder Phase 2 work in the same branch **only if a concrete task explicitly
combines them** — this branch (`chore/engineering-leverage-phase-8-9`)
already carries both.

## Current Truth

- **Branch:** `chore/engineering-leverage-phase-8-9`
- **Base SHA:** `6cd464fe6f867b6cd90a7f8d5e6c63ac8239c753` (origin/main)
- **Branch ahead of origin/main by 13 commits**
- **Working tree:** clean (zero uncommitted, zero untracked)
- **CodeGraph:** last sync reported `Already up to date`
- **Doctor JSON:** `codegraph:daemon` shows WARN (expected — daemon not running in this sandbox)
- **Builder queue:** `kb_mrm5ru85_9ea7` is **cancelled** — do not claim or restart it

## What This Branch Already Carries

- 13 commits ahead of `origin/main`, all EL + Phase 2 alignment work + the
  Doctor --spend flag and KittyBench skeleton (which were applied by a
  concurrent worker onto this same branch).
- 23 of ~25 audit recommendations from
  `docs/AUDIT_ENGINEERING_LEVERAGE_2026-07-14.md` §10 now have a `✓` row
  with a commit SHA in the Section 10 status column.
- H1-H6 owner decisions are recorded in the audit's HUMAN DECISION table.
- The 3 xfailed tests in `tests/test_builder_loop.py::TestLeaseIdentityIntegration`
  (`test_wrong_branch_execution_rejected_by_identity`,
  `test_foreign_commits_rejected`,
  `test_clean_in_scope_execution_succeeds`) document the **single largest
  remaining wiring gap**: `bl.run_packet` still calls `ba.start_attempt`
  instead of `ba.claim_and_start_attempt`, and has no post-worker git
  identity / commit-marker verification. `xfail strict=True` means these
  flip to failing-on-pass the moment that wiring lands.

## Active Worktrees / Preserve

These are live and should be left alone unless the task explicitly switches scope:

- `/Users/jacobbrizinski/Projects/kitty/.worktrees/campaign-p1-05` on `codex/campaign-p1-05`
- `/Users/jacobbrizinski/Projects/kitty/.worktrees/reconcile-builder-campaign` on `reconcile-builder-campaign`
- `/Users/jacobbrizinski/Projects/kitty/.worktrees/reconcile-phase2-p104` on `codex/reconcile-phase2-p104`
- `/Users/jacobbrizinski/Projects/kitty/.worktrees/reconcile-wip-campaign` on `feat/wip-campaign-and-runtime`

## What Is Left To Do (highest-leverage first)

1. **Audit D2 / A1** — Subclass-by-subclass reference check on the
   5 root temp files (`KITTY 2.md`, `PLAN.html`, `tokens 2.css`,
   `Design system philosophy reimagine.zip`, `kitty-studio-handoff.tar.gz`).
   For each one, `git grep -l <name>` and git log history. If zero
   references, propose archive or `git rm`. If any reference, leave.
2. **Audit A2 / H5** — Archive the 8 generic agent skills from the
   active registry (already listed in `SKILL_REGISTRY.md`):
   extract-wisdom, first-principles, iterative-depth,
   iterative-self-review-meta-optimization, red-team,
   root-cause-analysis, science-method, systems-thinking.
   Per H5 decision: don't delete permanently — move to
   `docs/archive/skills/` and keep the SKILL.md content.
3. **Audit D4 / A3 / H2** — `scripts/curation/` has 21 files. Per H2
   decision: migrate any unique logic into Builder, then
   `git rm -r scripts/curation/`. If no unique logic after audit,
   archive.
4. **Builder Phase 2 identity gap** — wire
   `ba.claim_and_start_attempt` into `bl.run_packet` and add
   post-worker identity verification. Flips 3 xfailed tests
   green. Concrete, bounded, and unblocked now that the
   `branch_leases` schema and `release_branch_lease` exist.
5. **One small UI surface** — make builder state (runs, attempts,
   leases, last failure string) actually visible in the Kitty
   chat UI. Do this **after** #4 so the UI surfaces real state,
   not placeholder state.

## What Not To Do

- Do not re-claim `kb_mrm5ru85_9ea7` — it's cancelled.
- Do not restart the EL initiative from scratch — the audit's
  Section 10 status column is the authoritative source of what
  landed. Read it before any audit-row work.
- Do not delete branches unless they are fully superseded
  elsewhere and have no active worktree.
- Do not spend tokens on broad repo archaeology unless you have
  a new concrete reason.
- Do not touch the 8 generic agent skills' content — only move
  the files to `docs/archive/skills/` per H5.

## Verification So Far

- `python3.12 -m pytest tests/test_doctor.py -q --tb=short` → `55 passed`
- `python3.12 -m pytest tests/test_builder_loop.py -q --tb=short` → `34 passed, 3 xfailed`
- `python3.12 -m pytest tests/test_success_criteria.py -q --tb=short` → `9 passed`
- `python3.12 -m pytest tests/test_run_gates_script.py -q --tb=short` → `15 passed`
- `python3.12 -m pytest tests/bench/ -q --tb=short` → `11 passed`
- `ruff check gateway/ tests/` → passed
- `mypy gateway/doctor.py gateway/builder.py gateway/builder_attempt.py gateway/builder_queue.py gateway/builder_loop.py gateway/builder_initiative.py gateway/builder_isc.py gateway/context_assembler.py --ignore-missing-imports` → no issues
- `vulture gateway/ --min-confidence 80 --exclude gateway/kitty-chat/` → exit 0
- `lychee --root-dir docs docs/` → 102 OK / 0 errors
- `git diff --check origin/main..HEAD` → exit 0

---

## Sol Prompt

You are continuing the KittyBuilder / Kitty convergence work in
`/Users/jacobbrizinski/Projects/kitty` on branch
`chore/engineering-leverage-phase-8-9`. This branch already carries
the EL packaging + the Builder Phase 2 alignment work. **Treat the two
as merged on this branch** — they are not separate lanes here.

Your goal: get the most leverage per token and the farthest useful
forward movement, not a polished recap.

### Read first (one time)

- `AGENTS.md` — repository contract
- This `.claude/HANDOFF.md` (you're reading it now)
- `.claude/STATE.md` — what landed this session
- `docs/AUDIT_ENGINEERING_LEVERAGE_2026-07-14.md` §10 status column —
  authoritative source of which audit rows landed. **Do not redo work**
  marked `✓`.
- `tests/test_builder_loop.py::TestLeaseIdentityIntegration` — three
  `xfail` markers document the exact next Builder Phase 2 wiring gap.

### Rebuild live state once (no repeats)

```
git status --short --branch
git worktree list --porcelain
git for-each-ref --format='%(refname:short) %(objectname:short) %(committerdate:short) %(subject)' refs/heads
./kitty doctor --json 2>&1 | head -50
```

### Pick one strong move

Priority order:

1. **One** audit item from "What Is Left To Do" above (D2/A1,
   A2/H5, D4/A3/H2) **or** the Builder Phase 2 identity gap.
2. A small, ugly, shippable UI surface — only if #1 is blocked.
3. **Never** polisher work — no broad doc rewrites, no "let me also..."

### Hard boundaries

- Do not touch live worktrees (see list above).
- `kb_mrm5ru85_9ea7` is cancelled — do not claim it.
- Do not delete branches or files outside the audited sets above.
- Do not push, force-push, or merge.
- If the audit §10 row is `✓` or `⏸`, do **not** redo it. Read the
  Status column carefully.
- Do not over-engineer. Ship the smallest thing that proves the
  move.

### What I want back

- The concrete next action you chose and why it wins on leverage.
- Exact files touched.
- Exact verification (commands + counts).
- Blockers, if any.
- The next thing the next model should do.
