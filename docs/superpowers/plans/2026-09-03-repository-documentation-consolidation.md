# Repository Documentation Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make Kitty's repository documentation easy to enter, truthful, non-duplicative, and clearly separated into current authority, supporting reference, execution input, dated evidence, and history.

**Architecture:** Preserve a small set of current authorities and front doors; make supporting documents point inward rather than compete; move clearly superseded current-looking root material into explicit history; retain ADR/decision evidence; validate navigation mechanically and with a fresh-reader review. Historical bulk is classified/indexed rather than rewritten.

**Tech Stack:** Markdown, Git/GitHub, Python documentation tests, shell/link checks, Kitty GAR coordination.

**Spec:** This file captures Jacob's approved 2026-09-03 repository-documentation consolidation program and is the binding implementation specification for this lane.

**Implementation status:** Tasks 1–6 implemented on the consolidation branch on 2026-09-03. Task 7 is deliberately external/exact-head: publication, CI/review, merge, merged-main proof, and GAR/#490 closeout must be completed after this content is finalized.

## Global Constraints

- Never mutate another active lane or canonical dirty checkout.
- `README.md`, `.env.example`, `gateway/doctor.py`, and `tests/test_doctor.py` remain excluded until `COLD-START-SETUP-CONTRACT-20260903` releases/merges.
- Preserve accepted ADRs and unique historical evidence; do not rewrite history to make old work look current.
- Do not modernize hundreds of historical packet/audit/research files individually.
- No runtime/product/Builder/coordination-kernel behavior changes.
- No paid/provider calls.
- Current documentation must not claim live/runtime facts without supported evidence.
- One semantic owner per major kind of current truth.

---

### Task 1: Repository-wide disposition inventory

**Files:**
- Inspect: all tracked Markdown
- Scratch only: `.superpowers/sdd/repository-documentation-consolidation-20260903/*`

- [x] Run independent front-door, authority, operator, history, structural, and adversarial audits on the same exact main SHA.
- [x] Build a disposition ledger covering every tracked Markdown family and every current-looking top-level doc.
- [x] Record rulings for canonical/supporting/historical/merge/archive/delete decisions.

### Task 2: Current authority and navigation simplification

**Files:**
- Modify: `START_HERE.md`
- Modify: `docs/README.md`
- Modify if evidence requires: `docs/AUTHORITY_MAP.md`
- Modify: `docs/archive/README.md`

- [x] Give README, START_HERE, and docs/README distinct non-overlapping jobs.
- [x] Ensure the authority map names only genuine current owners or explicitly historical compatibility pointers.
- [x] Make archive semantics explicit and remove current navigation into superseded material unless evidence requires it.
- [x] Run documentation-authority tests and link checks.

### Task 3: Agent/developer guidance consolidation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `CODEX.md`
- Modify as evidence requires: `CONTRIBUTING.md`, `TESTING.md`, `TASKS.md`, `SKILL_REGISTRY.md`
- Preserve: `AGENTS.md` as shared engineering/agent rules unless a contradiction requires a focused edit.

- [x] Remove duplicated shared policy from provider-specific adapters.
- [x] Preserve only genuinely provider/tool-specific guidance in CLAUDE/CODEX.
- [x] Make superseded ledgers/catalogs identify themselves as such or move them out of the front door.
- [x] Verify no command/test/merge rule contradicts current repository behavior.

### Task 4: Retire misleading top-level legacy documents

**Files:**
- Move/archive only high-confidence superseded `docs/*.md` material identified by Task 1.
- Repair all tracked inbound references affected by moves.

- [x] Move clearly dated/superseded architecture, OpenWebUI-primary, old Builder redesign, old planning/status, and one-off report material out of the current docs root when it has no current authority role.
- [x] Keep compatibility pointers only where code/tests/external workflows require stable paths.
- [x] Do not move current packet contracts, ADRs, or useful supporting references merely to reduce counts.
- [x] Verify every moved file retains discoverable historical provenance.

### Task 5: Structural prevention

**Files:**
- Modify: `tests/test_documentation_authority.py`
- Add only narrowly necessary documentation checks; no new framework.

- [x] Enforce canonical reading/navigation invariants.
- [x] Catch links from current navigation to explicitly retired authority catalogs.
- [x] Catch resurrection of known duplicate authority surfaces where deterministic.
- [x] Exclude vendored/upstream Markdown from Kitty-authored link expectations.

### Task 6: Integrate fresh-start README truth

**Files:**
- Modify: `README.md` only after active cold-start ownership is released or merged.

- [x] Merge current main after the cold-start and LiteLLM dependency contracts land.
- [x] Keep README concise: product, prerequisites, install, run/diagnose, verification, repository map, next-reading routes.
- [x] Remove archaeology/status prose that belongs in authorities/audits.
- [x] Exercise the documented fresh-start path as far as possible without credentials or paid calls.

### Task 7: Independent review, publication, and merged-main proof

- [ ] Run focused documentation tests, diff-check, current-doc link checks, stale-authority scans, and fresh-start command validation.
- [ ] Dispatch an independent adversarial whole-branch review on the most capable actually available worker route.
- [ ] Resolve findings, re-run exact-head verification, publish one reviewable PR (split only a mechanical history-move precursor if review size demands it).
- [ ] Require policy-gate/merge-gate and zero unresolved threads.
- [ ] Merge only exact reviewed head, then re-run the bounded documentation acceptance on exact merged main.
- [ ] Post GAR/#490 closeout with verified, changed, historical, unknown, and follow-up state.
