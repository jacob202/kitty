# Parked Features

Last updated: 2026-04-28

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

### Feature: Bank App Cash Flow Integration

Status: parked
Source: 2026-04-27 session logs
Owner: unassigned
Priority: medium

Problem:
Users need automated financial leak detection and budget management within the assistant.

Proposed shape:
Pull transaction data from bank apps or emails (Shop.ca, Amazon.ca, Canadian Tire, etc.) and identify "nice to haves" to cut.

Why parked:
Privacy/security implications and current focus on core stabilization.

Dependencies:
Secure bank API integration, email parsing logic, and a privacy spec.

Risks:
Data privacy, credential handling, API breakage.

Acceptance sketch:
Assistant correctly identifies and categorizes $500+ non-essential expenses from a transaction sample.

Revival trigger:
Core runtime stabilization complete and privacy framework approved.

Minimum safe version:
Phase 7+

### Feature: Canadian Real Estate Analysis Engine

Status: parked_candidate
Source: 2026-04-27 session logs
Owner: unassigned
Priority: low

Problem:
Quick identification of high-cash-flow rental properties in Canadian cities is a manual, high-friction process.

Proposed shape:
Filter listings for cash flow > $1k/mo, vacancy < 5%, and specific landlord conditions.

Why parked:
Requires specialized data scraping/APIs and is outside core assistant focus.

Dependencies:
MLS or similar real estate data source access.

Risks:
Data accuracy, market volatility, scraper maintenance.

Acceptance sketch:
Assistant returns top 3 matches for a specific city based on cash flow criteria.

Revival trigger:
Specialist domain expansion phase.

Minimum safe version:
Phase 8+
