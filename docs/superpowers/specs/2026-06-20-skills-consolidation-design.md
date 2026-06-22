---
date: 2026-06-20
topic: Skills Consolidation
status: PENDING_APPROVAL
---

# Skills Consolidation Plan

## Executive Summary

49 skills across project + global; 6 are exact duplicates, 4 more are near-identical,
4 are MCP-dependent dead weight if the graph MCP is not wired. Net result after this
plan: ~38 skills, cleaner triggers, workflow chains that auto-advance, and the best
project skills promoted globally.

No changes happen until user approves.

---

## Phase 1 — Delete (6 skills, zero content loss)

These are either exact duplicates or fully absorbed by a better version.

| # | Delete | Location | Reason |
|---|--------|----------|--------|
| 1 | `ship` | global `~/.claude/skills/ship/` | Project version is identical + has handoff step |
| 2 | `pr-review` | global `~/.claude/skills/pr-review/` | Project version has parallel specialist agents (168L vs 83L) |
| 3 | `tune` | project `.claude/skills/tune/` | Identical to global version; redundant copy |
| 4 | `autonomy_tune` | project `.claude/skills/autonomy_tune/` | Absorbed into consolidated `loop-tune` (Phase 2) |
| 5–8 | `debug-issue`, `explore-codebase`, `refactor-safely`, `review-changes` | project (all 4) | **Conditional on user**: these 4 wrap `code-review-graph` MCP tools. If that MCP is not active, they are dead. Delete if unused; keep if MCP is wired. |

> User must confirm items 5–8 before I touch them.

---

## Phase 2 — Merge (3 pairs → 3 superSkills)

### 2A. `loop_tune` (global) + `autonomy_tune` (project) → consolidated `loop-tune`

What each contributes:
- `loop_tune`: Diagnosis protocol, pattern table (stall/infinite/exit/goal), 6× testing ritual, 80% gate
- `autonomy_tune`: Kitty-specific loop context, fix-then-verify pattern, explicit commit step

Result: global `loop-tune` gets `autonomy_tune`'s Kitty context + explicit commit step added
to the existing pattern table. Project `autonomy_tune` deleted.

### 2B. `worktree` (global) + `worktree-clean` (global) → enhanced `worktree`

What each contributes:
- `worktree`: Create isolated branch+worktree, symlink gitignored files
- `worktree-clean`: Remove worktree + local branch, handle unclean state

Result: one `worktree` skill with two explicit modes triggered by argument:
- `/worktree create <feature>` → current create flow
- `/worktree clean [branch]` → current clean flow
- Natural sequence hint in description so it auto-suggests clean after ship

`worktree-clean` deleted after merge.

### 2C. `judge` (global) + `sparring` (global) → `deep-review`

What each contributes:
- `sparring`: Adversarial attack on assumptions (BLOCKING/MAJOR/MINOR tags)
- `judge`: Independent expert panel, 3 reviewers, credibility filter, verdict scale

Result: new `deep-review` skill. Protocol: sparring first (find cracks) → judge second
(weigh severity). One invocation, two stages. Better pre-ship gate than either alone.
Both originals deleted after merge.

---

## Phase 3 — Workflow Wiring

Add `## Flows` section to 6 skills so the agent knows what naturally comes next.
These are *hints*, not hard redirects — agent announces the suggestion, user decides.

| Skill | Trigger condition | Suggested next |
|-------|------------------|----------------|
| `tdd-loop` | escalation (stuck / >5 files / 10 iters) | → `/debug-fix` with context |
| `phase-runner` | all tasks `done` + gate green | → `/ship` |
| `catchup` | detects in-progress phase in handoff | → `/phase-runner N` |
| `worktree` (create) | when `ship` completes on branch | → `/worktree clean` |
| `debug-fix` | fix committed + tests green | → `/tdd-loop` to verify |
| `audit` | all dimensions merged + gate green | → `/qg` full run |

---

## Phase 4 — Trigger Deepening

Add or sharpen trigger keywords in frontmatter `description` for 4 skills that currently
have weak auto-fire:

| Skill | Add triggers |
|-------|-------------|
| `catchup` | `"what was I working on"`, `"just ran /clear"`, `"fresh session"`, `"catch me up"`, `"resume work"` |
| `tdd-loop` | `"make this test pass"`, `"fix the failing test"`, `"iterate until green"` |
| `phase-runner` | `"work on phase"`, `"resume phase"`, `"kick off phase N"`, `"checkpoint phase"` |
| `deep-review` | `"pressure test this"`, `"challenge my approach"`, `"expert review"`, `"am I missing anything"` |

---

## Phase 5 — Global Sync

Promote 5 project-only skills to global so any future project gets them:

| Skill | Why global |
|-------|-----------|
| `catchup` | Useful in any long-running project session |
| `phase-runner` | Generic enough for any phased work |
| `phase-swarm` | Generic parallel-worktree coordinator |
| `tdd-loop` | Universal test-fix loop |
| `second-opinion` | Already marked AUTOMATIC; should be everywhere |

Method: copy SKILL.md to `~/.claude/skills/<name>/SKILL.md`. Project copies remain as
thin re-exports or are deleted after confirming global version is identical.

---

## Scope / Out of Scope

**In scope:**
- Delete exact duplicates
- Merge the 3 pairs above
- Add `## Flows` hints to 6 skills
- Sharpen 4 trigger descriptions
- Sync 5 skills globally

**Out of scope (not touching):**
- The 12 audit-dimension skills — they're designed as a pipeline, already well-scoped
- `aura` — 558-line orchestration engine, owns its own ecosystem
- `aura-guard`, `aura-compact` — internal to aura loop
- `commit` — intentionally minimal; ship is the full version, commit is the fast alias
- `pr` — creates PRs; `pr-review` reviews them; different directions, keep both

---

## Net Effect

| | Before | After |
|---|---|---|
| Total skills | 49 | ~38 (if MCP skills deleted) / ~42 (if kept) |
| Duplicates | 6 | 0 |
| Skills with workflow hints | 0 | 6 |
| Skills with sharp triggers | ~60% | ~90% |
| Project-only skills | 14 | ~5 (rest promoted globally) |

---

## Execution Order

1. Phase 1 deletions (no content risk)
2. Phase 2A: loop-tune merge
3. Phase 2B: worktree merge
4. Phase 2C: deep-review merge
5. Phase 3: workflow wiring (6 skills)
6. Phase 4: trigger deepening (4 skills)
7. Phase 5: global sync (5 skills)
8. Run `/qg` on skills (verify skill files parse correctly)

**Pending user decision before starting:** are the 4 MCP-dependent project skills
(`debug-issue`, `explore-codebase`, `refactor-safely`, `review-changes`) in use?
