# Kitty Runtime Context Pack

Generated from canonical project docs. This file is read-only runtime context, not a source of authority.

## Current Focus
Source: CURRENT_FOCUS.md

# Current Focus
Last updated: 2026-04-28

## Active Phase

Phase 4 — Consolidation and Cleanup

## Current Task

Build chat log consolidation pipeline (dry-run first).

## Allowed Work

- chat log consolidation dry-run
- extract decisions/tasks/parked/features/preferences/open loops
- file tree snapshot and cleanup candidates
- update SESSION_SUMMARY.md with Phase 3 results
- mark Phase 3 complete in all tracking files

## Forbidden Work

- wiring Phase 3 modules to web.py
- MCP expansion
- QLoRA
- proactive nudging
- Kelly bodywork
- UI polish
- memory migration
- deleting raw chat logs

## Phase 3 Complete

- Morning brief module ✅ (10 tests pass)
- Task tracker + done handler ✅ (10 tests pass)
- /stuck command ✅ (6 tests pass)
- All specs created: morning-brief.spec.md, task-tracker.spec.md, stuck-command.spec.md
- Validation: 65 passed, 26 Phase 3 tests passed

## Next Action
Last updated: 2026-04-29

## Allowed Work
- Follow CURRENT_FOCUS.md.

## Forbidden Work
- wiring Phase 3 modules to web.py
- MCP expansion
- QLoRA
- proactive nudging
- Kelly bodywork
- UI polish
- memory migration
- deleting raw chat logs

## Recent Decisions
Source: docs/DECISIONS.md

# Decisions

Last updated: 2026-04-29

This file records durable project decisions. New work should follow these rules unless a later dated decision explicitly supersedes them.

## D-0001: Current App Stays Put

Status: accepted

`/Users/jacobbrizinski/Projects/kitty` is the current runnable app. Do not move it, rename it, split it, or physically migrate files during Phase 0.

Rationale: the app is actively changing, and uncontrolled moves would make it hard to distinguish real regressions from path and import breakage.

## D-0002: `kitty-system` Separation Is Planned, Not Started

Status: accepted

The future architecture may separate stable system/control material from the runnable app, using a future `kitty-system` boundary. That separation is pending controlled migration.

Required before migration:

- Approved migration spec.
- Full file inventory.
- Explicit move map.
- Rollback plan.
- Verification commands.
- Completion report.

## D-0003: Intake Before Builder Work

Status: accepted

Builder tasks must enter through `docs/BUILDER_INTAKE.md` and `intake/`. A task is not ready for implementation until it has:

- A named owner or worker lane.
- Scope summary.
- Allowed files.
- Forbidden files.
- Acceptance tests.
- Smoke test.
- Rollback plan.

## D-0004: Separate Control Docs From Product Code

Status: accepted

Control documents describe how work is allowed to proceed. They do not authorize product behavior changes by themselves.

Control-doc changes may update:

- `CURRENT_FOCUS.md`
- `docs/DECISIONS.md`
- `docs/PARKED_FEATURES.md`
- `docs/FILE_GOVERNANCE.md`
- `docs/FILE_MANIFEST.md`
- `docs/BUILDER_INTAKE.md`
- `specs/_template.md`
- `intake/`

Product changes require a separate spec.

## D-0005: Park, Do Not Opportunistically Build

Status: accepted

Interesting ideas discovered during focused work must go to `docs/PARKED_FEATURES.md` or an intake note. They must not be implemented inside an unrelated task.

## D-0006: Protected Files Require Explicit Permission

Status: accepted

Protected files and directories are listed in `docs/FILE_GOVERNANCE.md`. Workers must check that file before editing and must not touch protected runtime paths unless their assigned spec explicitly allows it.

## D-0007: Builder Requires Explicit Project And Spec

Status: accepted

`kittybuilder` must not start an open-ended interactive builder by default. It requires:

- `--project`
- `--spec`
- dry-run by default
- `--execute` before any future write-capable builder path

The spec must live inside the project, and every run must end with a completion-report checklist.

Rationale:
Raw builder launch is too easy to confuse with runtime Kitty startup and can lead to uncontrolled edits.

## D-0008: Canadian-First Assistant Persona Candidate

Status: needs_user_confirmation

Do not treat the Canadian-first assistant persona as accepted canon yet.

Rationale:
The evidence in `docs/imports/gemini_intake_20260428.md` comes primarily from assistant-authored session text. It is useful as a candidate preference, but not strong enough to become a durable project decision without Jacob confirming it.

Consequences:
Kitty should keep the accepted direct/practical/no-fluff style, but Canadian sourcing and budget-first behavior should be used only when the user asks for it or confirms this as a permanent preference.

Review trigger:
Jacob confirms whether Canadian-first sourcing/budget behavior is a permanent assistant preference.

## Open Tasks
Source: TASKS.md

# Tasks

Last updated: 2026-04-29

## Verified Done

- Phase 0/1 control docs, intake, builder contract, file governance, context pack.
- Phase 3 runtime utilities now have passing tests and live route wiring:
  - `/api/brief`
  - `/api/command` with `/stuck`
  - task/done tracking modules
- Phase 4 chat-log consolidation tests pass.
- Phase 5 response quality critic tests pass.
- Phase 6 memory/vector/specialist focused tests pass.
- Phase 6+ security scanner pure utility implemented and tested.
- Phase 6+ builder write/command security enforcement implemented and tested.
- Phase 6+ eval dashboard backend implemented and tested.
- Live route smoke completed for `/api/brief` and `/api/command`.
- Live `/api/chat` empty-response bug fixed and smoke-tested.
- Chat-log consolidation dry-run processed `data/sessions` without errors.
- Chat-log consolidation CLI implemented and verified: `20 passed`.
- Control gates verified after builder security enforcement: `83 passed`.
- Full suite verified: `333 passed, 2 warnings`.
- Tiny generated-cache cleanup completed under `specs/tiny-generated-cache-cleanup.spec.md`.
- Builder security enforcement verified: `53 passed`.
- Gemini/chat-log candidate intake imported and reviewed; weak assistant-authored claims were demoted to open loops or rejected/noisy.
- Eval dashboard UI panel spec written, component implemented in Garage UI, and failed-check object rendering fixed.
- `/api/chat` real provider response implementation completed (fallback logic improved and errors passed clearly).
- Gemini/chat-log candidates reviewed; only durable preferences/safety rules were accepted, and uncertain items remain open loops.
- `./kitty status` command fixed to correctly report server state based on port 5001 usage.
- UI panel regression coverage added for eval dashboard failed-check rendering (using Vitest and React Testing Library).

## Next Smallest Action

- Checkpoint the reviewed candidate disposition and current verified docs.

## Delegation Queue

- Cleanup worker: only read-only/spec-first for remaining candidates; do not clean protected-tree metadata or tracked deletions.

## Blocked Without New Spec

- physical `kitty-system/kitty-app` repo move
- memory migration beyond current focused modules
- QLoRA/model training
- MCP expansion
- proactive idle nudging
- UI polish
- deletion of raw chat logs
- deletion inside protected `src/` paths for metadata files without waiver

---

# Previous Imported Tasks

Last updated: 2026-04-28#

This file is the control-layer task list for the current Kitty stabilization pass.#

## Done##!

- Phase 0 — Structural separation and control files ✅__
- Phase 1 — Intake and builder contract ✅__
- Phase 2 — P0 Stabilization and Gates ✅__
- Phase 3 — Core Runtime Utility ✅__
  - Morning brief module (10 tests pass)__
  - Task tracker + done handler (10 tests pass)__
  - /stuck command (6 tests pass)__
  - All specs created: morning-brief, task-tracker, stuck-command__
- Phase 3+4 Wiring ✅__
  - Morning brief route (brief_bp) — 3/3 tests pass)__
  - Commands route (commands_bp) — 4/4 tests pass)__
  - Blueprints registered in `src/api/__init__.py`__
- Phase 4 — Consolidation and Cleanup ✅__
  - Chat log consolidation pipeline (15 tests pass)__
  - Spec: chat-log-consolidation.spec.md__
  - Report template: docs/CHAT_LOG_CONSOLIDATION_REPORT.md__
- Phase 5 — Skills and Quality ✅__
  - Response quality critic (10 tests pass)__
  - Self-correction skill exists (SKILL.md)__
  - Spec

[truncated]

## Parked Items Not To Build
Source: docs/PARKED_FEATURES.md

# Parked Features

Last updated: 2026-04-29

Parked features are ideas worth keeping but not authorized for current implementation. Parking an idea preserves it without letting it hijack focused work.

## Template

Use this shape for every new parked feature:

```md
### Feature: <short name>

Status: parked
Source: <where this came from>
Owner: unassigned
Priority: low | medium | high

Problem:
<What user pain or system gap this addresses.>

Proposed shape:
<What the feature might do, without committing to implementation.>

Why parked:
<Why this is not part of the current focus.>

Dependencies:
<Docs, services, migrations, APIs, or design decisions required first.>

Risks:
<Data loss, privacy, UX, cost, runtime, or maintenance risks.>

Acceptance sketch:
<What would prove this works in a future spec.>

Revival trigger:
<The concrete condition that makes this safe to revisit.>

Minimum safe version:
<Earliest phase or version where this belongs.>

Allowed future files:
<Likely files, still subject to the future spec.>

Forbidden during unrelated work:
<Files or behaviors that must not be touched opportunistically.>
```

## Initial Parked List

### Feature: Physical `kitty-system` Split

Status: parked
Source: Phase 0 planning
Owner: unassigned
Priority: high

Problem:
Kitty needs clearer separation between durable system/control docs and the runnable app.

Proposed shape:
Create a controlled `kitty-system` boundary for governance, specs, intake, and durable operating context while preserving the runnable app path.

Why parked:
No physical repo move is allowed in Phase 0.

Dependencies:
File manifest, migration spec, import/path audit, rollback plan, and verification gates.

Risks:
Broken imports, lost local state, stale launch commands, duplicated docs, and workers editing the wrong checkout.

Acceptance sketch:
The runnable app still launches from `/Users/jacobbrizinski/Projects/kitty`; migrated files are listed in a move map; rollback restores the previous layout.

Allowed future files:
Future migration spec only, until approved.

Forbidden during unrelated work:
No `mv`, deletion, path rewrite, package rename, or launch-command rewrite.

### Feature: Full Builder Automation From Intake

Status: parked
Source: Phase 0 planning
Owner: unassigned
Priority: medium

Problem:
Builder tasks need a repeatable way to turn intake notes into safe implementation lanes.

Proposed shape:
Generate specs from intake records, validate allowed/forbidden files, execute approved builder tasks, and produce completion reports.

Why parked:
The current control layer only provides deterministic intake classification and an explicit builder contract. Full automatic spec generation and write-capable builder execution remain parked.

Dependencies:
Stable `docs/BUILDER_INTAKE.md`, `docs/BUILDER_DIRECTIVE.md`, `specs/_template.md`, and agreement on worker lane ownership.

Risks:
Automation could over-authorize edits or hide missing acceptance tests.

Acceptance sketch:
A dry run produces a spec draft without modifying protected files.

Allowed future files:
Builder tooling spec, then the exact files approved there.

Forbidden during unrelated work:
No edits to `scripts/`, `src/`, tests, or UI files.

### Feature: Repo Cleanup And Archive Pruning

Status: parked
Source: Dirty tree and existing archive docs
Owner: unassigned
Priority: medium

Problem:
The checkout contains stale, generated, archived, and active files that need clearer boundaries.

Proposed shape:
C

[truncated]

## Open Loops
Source: docs/OPEN_LOOPS.md

# Open Loops

Last updated: 2026-04-29

## Active

- Confirm whether "Canadian-first" sourcing and budget-conscious recommendations should become a permanent Kitty preference.
- Confirm whether `$129/month` is a real product/business target, a generated artifact, or irrelevant.
- Decide whether bank transaction / budget leak analysis should be rejected entirely or parked behind a privacy spec and manual-paste-only boundary.

## Waiting

- Approved spec for any runtime source changes.

## Project Context
Source: KITTY_CONTEXT.md

# Kitty Context

Last updated: 2026-04-28

This top-level file is a concise runtime/control pointer. The fuller historical context remains in `docs/KITTY_CONTEXT.md`.

## Current Authority

Follow this order when files conflict:

1. `CURRENT_FOCUS.md`
2. active spec in `specs/`
3. this file
4. `docs/DECISIONS.md`
5. `docs/FILE_GOVERNANCE.md`
6. `docs/PARKED_FEATURES.md`
7. `SESSION_SUMMARY.md`
8. older docs, chat logs, and raw exports

## Current Rule

Raw ideas do not become code. They go through:

raw request -> `kittyintake` -> decision / clarification / parked feature / spec -> `kittybuilder` -> tests -> gates -> completion report -> canonical docs update

## Runtime Boundary

The active runnable checkout is:

`/Users/jacobbrizinski/Projects/kitty`

Do not treat `/Users/jacobbrizinski/Documents/Kitty` as the runnable repo for this pass.

## Interaction Rules

- Be direct.
- Avoid padding.
- Do not claim work is complete without fresh verification.
- Prefer one concrete next action over broad plans.
- Do not build parked features without an approved spec.

## User Interaction Rules
Source: docs/KITTY_CONTEXT.md

# Kitty — Curated Context

**Purpose:** Single source of truth for what Kitty is, what's been decided, and what corrections matter most. Read this before starting any new session.

---

## What Kitty Is

Kitty is Jacob's local-first personal AI assistant. It runs as a Flask + SocketIO web app (Python 3.12) with a chat UI, voice input, and a specialist framework for routing queries to domain experts. The goal is a private, always-on companion that learns Jacob's patterns over time.

**Entry point:** `web.py` → `create_app()` → blueprints + CoreOrchestrator  
**Run command:** `/opt/homebrew/bin/python3.12 web.py`  
**Test command:** `/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short`

---

## Codebase Map (Real Paths)

```
web.py                          # App factory + Flask entry point
kitty                           # Launcher script (start/stop/logs)
src/
  api/                          # HTTP/SocketIO routes & services
  core/                         # Orchestration, framework, specialists
  memory/                       # Memory subsystems (CorrectionMemory, etc)
  space_kitty/                  # Behavioral & reasoning orchestrators
  cli/                          # Terminal UI & reference tools
  tools/                        # Custom tool implementations
  autonomy/                     # Self-improvement engine
evals/                          # Smoke suite, personas, artifacts
tests/                          # pytest suite (~85 tests)
config/specialists/             # Per-specialist markdown configs
docs/                           # Context, tasks, plans, audits
skills/                         # Legacy, consolidated, & packaged skills
scripts/                        # Setup, eval, and maintenance scripts
data/                           # Databases, logs, checkpoints, budget
```

---

## Storage Routing (Never swap these)

| Data | System | Never use |
|------|--------|-----------|
| Knowledge base ingestion | LightRAG | JournalDB |
| Journal entries | JournalDB | LightRAG |
| MCP entities/relations | @modelcontextprotocol/server-memory | — |
| Eval artifacts | `evals/artifacts/*.json` | DB |
| Session memory | hybrid (in-memory + AgentDB) | — |

Routing violations are the #1 source of data-loss bugs in this project.

---

## Model Routing

| Need | Model | Notes |
|------|-------|-------|
| Fast / free / local | MLX Qwen3.5-4B | `enable_thinking=True` for reasoning |
| Cheap remote | deepseek-chat | wired for both large + small slots |
| Heavy reasoning | deepseek-reasoner | paid — use sparingly |

Local models are free. Always try them first.

---

## Validated Corrections (High Priority)

These are decisions that were tested and confirmed correct. Don't revert them.

**1. Context slot assignment must be direct, not positional.**  
`ContextBudget.add()` must always receive the named `ContextSlot` (IDENTITY, CORRECTIONS, RECENT, EPHEMERAL). Never use a positional list and index into it — when sections are empty the indices shift and corrections land in the wrong slot.

**2. Reasoning layer must be sourced from `current_app.orchestrator`.**  
`_get_reasoning_layer()` in `reasoning_routes.py` must check `current_app.orchestrator` first. `current_app.supervisor.orchestrator` is always `None` in web mode — the shim has no orchestrator attribute.

**3. `POST /api/memory/corrections` must return 400 when `item_id` is missing.**  
Currently returns 207. This validation gap is a known open bug.

---

## Eval Platform

Baseline:

[truncated]
