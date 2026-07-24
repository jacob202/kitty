# Archive Manifest — 2026-07-24 docs/ consolidation

**Approved by:** Jacob, 2026-07-24 ("archive instead of delete, go through every document").
**Method:** every top-level doc and folder inventoried (last-commit date, size); live references checked (code, tests, AGENTS.md, START_HERE.md, CLAUDE.md, scripts); durable value extracted to canonical homes BEFORE any move.

## Canonical homes going forward

| Information type | Canonical home |
|---|---|
| Architecture truth | `docs/ARCHITECTURE.md` + `docs/codemap/` (+ `docs/audit/architecture-honesty-2026-07-24.md` as latest verified snapshot) |
| Decisions | `docs/adr/` + `docs/DECISIONS.md` |
| Lessons | `docs/LEARNINGS.md` (kitty) / `~/kb/wiki/kitty-lessons-index.md` (cross-tool pointer) |
| Active plans | `docs/PLANS.md` + `docs/plans/` + `docs/planning/` |
| Work units | `docs/packets/` (never archive — history) |
| Cross-tool/agent context | `~/kb/` (INDEX → NOW → identity → wiki) |
| Session state | `.claude/STATE.md` + `.claude/HANDOFF.md` |

## Moved to archive (this pass)

### `archive/audits-2026-07/` — audit/harvest reports, extracted then archived
Extraction: `~/kb/wiki/2026-07-24-unconsumed-audit-recommendations.md` (parked decisions, unconsumed packets DTH/IMG/FAR, 14-item adapt register). IMG-01 verified DONE (migrations 023–026).

- AUDIT_DEEPTUTOR_ARCHITECTURE_HARVEST_2026-07-20.md
- AUDIT_IMAGELAB_ARCHITECTURE_HARVEST_2026-07-20.md
- AUDIT_FEATURE_ADJACENT_ARCHITECTURE_HARVEST_2026-07-20.md
- AUDIT_COMPANION_LAYER_HARVEST_2026-07-23.md
- AUDIT_KITTY_FRONTEND_EXPERIENCE_HARVEST_2026-07-20.md
- AUDIT_FULL_ENGINEERING_2026-07-20.md
- AUDIT_ENGINEERING_LEVERAGE_2026-07-14.md
- AUDIT_EXTERNAL_ARCHITECTURE_2026-07-14.md
- AUDIT_UI_REVIEW_2026-07-23.md (synthesis also in `~/kb/wiki/2026-07-23-ui-review-synthesis.md`)
- RECON_KITTY_AGENT_LEVERAGE_2026-07-17.html (superseded by `docs/recon/repo-landscape-2026-07-24.md`)
- kb-skill-audit.md (canonical copy in `~/kb/wiki/skill-audit.md`)

### `archive/` root — dead, superseded, or ephemeral

| File | Why archived |
|---|---|
| AGENT_HANDOFF.md | Tombstone (handoffs moved to `.claude/HANDOFF.md` 2026-07-03); pointer now in AGENTS.md |
| AGENT_RUNTIME.md | Superseded by AGENTS.md; unique facts extracted to `~/kb/wiki/2026-07-24-skills-layout-agent-runtime-extract.md`. Note: its pre-commit-hook claims were stale — no hook installed |
| KITTY_HUB.md | kitty_hub module no longer exists in the codebase |
| USER_PREFS.md | Content extracted to `~/kb/identity.md` (explanation style) |
| memory-stale.md (+ plans/ copy) | Ephemeral mem0 maintenance reports (2026-06-22, 2026-07-20), not docs |
| skill-improvement-queue.md (+ plans/ copy) | Ephemeral audit output |
| ref_023_image_jobs_pr210.* (3 files) | Reference copies of shipped PR #210; real code in migrations 023–026 |
| KITTYBUILDER_ORCHESTRATOR_PHASE1A.md | Self-declared "Superseded historical baseline" |
| KITTYBUILDER_PHASE1A_PR4_CLI_TASK.md | Phase 1A shipped |
| IMPLEMENTATION_PLAN_2026-07-14.md | Dated blueprint; recommended work implemented (see its bridge note) |
| council-routing-design.md, tutor-design.md | Design records for shipped features; behavior of record is the code |
| fable-context/ | Codex audit handoff bundle (2026-07-11), consumed |

### `docs/planning/` — vision/strategy moved (NOT archived, still direction-relevant)
FUTURE_CAPABILITIES.md, FUTURE_REASSESSMENT_SIMULATION.md, UNFAIR_ADVANTAGE_AND_HARNESS.md, KITTYBUILDER_SELF_BUILDING_MVP.md.

## Deliberately KEPT (with reasons)

- `phases/` — live references: `gateway/cron.py` (PHASE_C3_PLAN), `scripts/mempalace_preflight.py` + `migrate_mem0_to_mempalace.py` (MEMPALACE_MIGRATION_RUNBOOK). **Open question: is the mempalace migration done?** If yes, phases/ can be re-reviewed.
- `superpowers/` — 4 gateway modules cite `specs/2026-06-24-gateway-deepening-program-design.md` as design rationale in docstrings.
- `examples/` — `kitty_alpha_initiative.example.json` referenced by `tests/test_builder_initiative.py:755`.
- `retired/` — already retired.
- All canonical docs listed in the table above.

## Strays rounded up

- Duplicate packet numbers in `docs/packets/` (021, 022, 026 ×2 each) — known lesson ("packet numbers double-assigned 3×"); registry table is source of truth. Not a docs problem; no action.
- `.DS_Store` in docs/ — left in place (harmless, gitignored).
- Pre-commit hook not installed (`scripts/install-pre-commit.sh` exists) — flagged, not installed (Jacob's call).

## Follow-ups for Jacob

1. ~~Ratify or kill the parked audit decisions~~ — **DONE 2026-07-24: ADR-0019** (3 defer, 8 ratify, zero new work).
2. Mempalace migration status → if done, phases/ re-review.
3. Install pre-commit hook or delete the installer script.

---

## Second pass (same day): vision consolidation + codebase sweep

### Vision → `docs/planning/vision-horizons.md` (canonical), originals → `archive/vision-2026-07/`
FUTURE_CAPABILITIES, FUTURE_REASSESSMENT_SIMULATION, UNFAIR_ADVANTAGE_AND_HARNESS merged into one horizon catalog (5 user-facing ideas, 7 experience laws, 10 horizons with stress-test verdicts, 20 harness levers). KITTYBUILDER_SELF_BUILDING_MVP archived — superseded by `planning/kittybuilder-redesign-2026-07-24.md`.

### Codebase sweep → `archive/codebase-sweep-2026-07/`

| Item | What it was | Why moved |
|---|---|---|
| `backend/` | Pre-gateway Kitty orchestrator (Open WebUI endpoint) | Unreferenced anywhere; D2 made gateway the product |
| `soul/` | 8 specialist personas + kitty.md | Unreferenced (config/SOUL.md is canonical persona). If council needs them later, they're here |
| `design-system/` | Standalone design workspace (77 files: chats, v2-reference, tokens.css) | Unreferenced by kitty-chat |
| `TASKS.md` | Self-declared "Superseded Status Ledger" | Superseded by ACTIVE_MISSION/PROJECT_STATUS |
| `TODOS_NEXT.md` | Plan referencing a retired doc | Stale |
| `PR_DESCRIPTION.md` | Description for merged branch (leverage-phase-8-9) | Leftover |
| `kb/` (nested) | Fork KB created by parallel session | Content fully ported to `~/kb` (L-13–17) |
| `origin` (root) | Broken self-referential symlink (created 07-24 15:16 by unknown process) | Removed via os.unlink |

### Kept after verification
- `contracts/` — imported by 5+ gateway modules (shared schemas)
- `prompts/` — PROMPTS_DIR, load_prompt reads it
- `mcp/` — auxiliary; ⚠️ no CI lint/type coverage (known lesson: broke invisibly before)
- `notebooks/` — 1 colab notebook (image pipeline), harmless
- `CODEX.md`, `run.sh`, `vercel.json` (inert), `hermes.env.example`, `SKILL_REGISTRY.md` — live entry points/templates
- `phases/`, `superpowers/` — live code references (see first pass)

### Boundary of this sweep
`gateway/` internals and `gateway/kitty-chat/` were NOT swept — the 2026-07-24 architecture-honesty audit covers gateway subsystems, and the UI is mid-refactor by a parallel session. `scripts/` dead-script hunt is a future pass (needs per-script reference checks).
