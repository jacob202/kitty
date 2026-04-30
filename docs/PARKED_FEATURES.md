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

### Feature: KnowledgeGetter MCP Server

Status: parked_unverified_dirty_tree
Source: uncommitted worker lane found 2026-04-29
Owner: unassigned
Priority: medium

Problem:
Kitty may eventually need a standalone research/indexing tool that can search, scrape, and retrieve indexed knowledge.

Proposed shape:
A future MCP server wrapping search, retrieval, and domain reporting with durable local indexes.

Why parked:
The active focus forbids MCP expansion. The current dirty implementation is Phase 6+ work and has not passed the current master-plan sequence, source-grounding review, dependency review, or storage-routing review.

Dependencies:
Approved Phase 6+ spec, source-grounded specialist boundaries, storage routing review, dependency/cost review, and generated-data governance.

Risks:
Credential handling, web scraping scope creep, generated database commits, dependency bloat, duplicated knowledge storage, and violating local-first cost controls.

Acceptance sketch:
Future review proves the server imports without optional dependency crashes, keeps generated indexes out of git, documents required env vars, and has tests beyond import smoke.

Revival trigger:
Phase 0-4 control work is stable and Jacob explicitly approves MCP expansion through intake.

Minimum safe version:
Phase 6+

Allowed future files:
Future spec only until approved. Existing dirty files must be reviewed before adoption.

Forbidden during unrelated work:
Do not mark MCP expansion complete, remove the MCP block, commit generated `knowledge_db/`, or wire the tool into runtime routes.

### Feature: Phase 6+ MCP Agent Bundle

Status: parked_unverified_dirty_tree
Source: uncommitted worker lane found 2026-04-29
Owner: unassigned
Priority: medium

Problem:
Kitty may eventually benefit from standalone agents for research, cataloging, code review, brainstorming, and overnight session processing.

Proposed shape:
Five future MCP-style agents: KnowledgeGetter, Librarian, VisionGuide, CodeReviewer, and Overnighter.

Why parked:
The active focus forbids MCP expansion. The bundle appeared as dirty work outside the approved phase sequence and changed task-board docs to claim completion before validation.

Dependencies:
Approved Phase 6+ intake/spec, dependency review, generated-data governance, storage routing review, subprocess safety review, and real tests.

Risks:
Import-time crashes from missing optional dependencies, generated database commits, broad subprocess execution through code-review tooling, uncontrolled LLM calls, source-routing drift, and cost creep.

Acceptance sketch:
Each agent has tests beyond import smoke, optional dependencies are lazy or documented, generated stores are ignored, no runtime route is wired without a spec, and dangerous subprocess tools are gated.

Revival trigger:
Jacob explicitly approves MCP expansion after workspace separation preflight is clean.

Minimum safe version:
Phase 6+

Allowed future files:
Future MCP review spec and narrowly approved agent files only.

Forbidden during unrelated work:
Do not accept the dirty agent bundle as complete, remove the MCP block, or commit generated `knowledge_db/` / `librarian_db/`.

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
Create a review-first cleanup plan that identifies active, archived, generated, duplicate, and delete-candidate files.

Why parked:
Cleanup is destructive if done casually and is outside Worker A ownership.

Dependencies:
File manifest, archive manifest review, and owner approval.

Risks:
Deleting live imports, losing handoff context, or masking active work from other workers.

Acceptance sketch:
Cleanup spec lists every deletion candidate with evidence and rollback instructions.

Allowed future files:
Cleanup spec and reviewed docs.

Forbidden during unrelated work:
No deletions, `git reset`, source moves, or archive pruning.

### Feature: Budget Leak Finder Skill

Status: parked_candidate (confidence: medium)
Source: CHAT_LOG_CANDIDATE_REVIEW_2026-04-29.md
Owner: unassigned
Priority: low

Problem:
Users might want to identify budget leaks from financial data.

Proposed shape:
A new runtime skill for budget leak finding.

Why parked:
This could become a skill later, but only after a privacy spec and skills-system validation.

Dependencies:
Privacy spec, skills-system validation.

Risks:
Handling sensitive financial data.

Acceptance sketch:
Privacy boundaries are enforced and skill validation passes.

Revival trigger:
Approved privacy spec.

Minimum safe version:
Phase 7+

### Feature: Audio specialist KB candidate from AU-7900 session text

Status: parked_candidate (confidence: medium)
Source: CHAT_LOG_CANDIDATE_REVIEW_2026-04-29.md
Owner: unassigned
Priority: low

Problem:
The logs contain Sansui/AU-7900 troubleshooting text that could be useful.

Proposed shape:
Specialist KB.

Why parked:
Specialist knowledge must be source-grounded before it becomes canonical KB.

Dependencies:
Source-grounded specialist engine.

Risks:
Hallucination without source grounding.

Acceptance sketch:
The knowledge is successfully source-grounded and integrated into a specialist KB.

Revival trigger:
Source-grounding engine is complete.

Minimum safe version:
Phase 6+

