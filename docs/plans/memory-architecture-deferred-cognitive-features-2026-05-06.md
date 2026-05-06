# Deferred Cognitive Features For Memory Architecture

Date: 2026-05-06
Status: parked, non-authorized for current implementation
Owner: unassigned
Source: Jacob's v4 Blueprint and Cognitive Sharpening Layer discussion

## Purpose

This file parks the remaining human-centric "second brain" and cognitive sharpening ideas so they are not lost while the memory architecture decision and bake-off proceed.

These ideas are intentionally preserved as future product material, not approved scope. They must not be implemented during the current memory architecture work unless Jacob explicitly approves a new spec after the source ledger, memory router, quarantine foundation, and bake-off tasks are complete.

## Reevaluation Trigger

Reevaluate these ideas only after all of the following are true:

1. The memory architecture bake-off report is complete.
2. The decision doc has selected or deferred the retrieval backend direction.
3. The first foundation build is complete: source ledger, memory router, and quarantine queue.
4. The foundation can preserve raw source data, source provenance, candidate state, durable memory state, and soft-delete or hard-delete decisions.
5. Jacob explicitly asks to open a new spec for cognitive features, autonomy governance, trust UI, or proactive coaching.

## Current Boundary

Current memory architecture work is limited to deciding and planning the foundation:

- Source ledger for raw and durable records.
- Memory router for storage and retrieval policy.
- Quarantine queue for low-confidence, conflicting, sensitive, or interpretive candidates.
- Bake-off comparison of current Kitty stack, LanceDB-style embedded retrieval, and Cognee-style ingestion and graph lifecycle.

The following are not authorized now:

- Implementing proactive coaching or nudging.
- Building a new trust dashboard.
- Adding autonomy behavior or scheduled reflection loops.
- Replacing the live memory backend before the bake-off decision.
- Expanding MCP.
- Migrating memory stores.
- Adding external packages to runtime dependencies.
- Changing runtime source for these parked ideas.

## Ideas That Influence The Current Bake-Off Only As Requirements

The parked feature set should influence the bake-off as future-readiness requirements, not as implementation scope.

Use these requirements when scoring memory candidates:

- Provenance: every retrieved fact, belief, insight, or action recommendation must be traceable to source records.
- Temporal memory: the system must support timestamps, version history, supersession, and "what changed over time" queries.
- Candidate lifecycle: extracted facts, beliefs, emotions, contradictions, and insights must be able to start as staged candidates before becoming durable memory.
- Quarantine: low-confidence, conflicting, sensitive, personal, or interpretive memory must be isolated from normal context until reviewed.
- Confidence: retrieval results, extracted facts, suggested actions, and autonomy decisions should be able to carry confidence scores.
- Action audit: future autonomous actions need a durable action log with input, output, confidence, tool, timestamp, and possible rollback or review metadata.
- Self-model readiness: the schema must be able to represent preferences, values, beliefs, goals, projects, and changes over time without forcing them into unreviewed durable memory.
- Relationship readiness: the architecture should support graph-style links between people, projects, tools, topics, beliefs, sources, and decisions.
- Exportability: durable personal model data should remain portable and not trapped inside one retrieval engine.
- Privacy: sensitive introspection and personal memory must be supportable under stricter review and deletion rules than project facts.

These requirements should be reflected in the bake-off rubric under recall quality, source/provenance quality, automated ingestion quality, conflict/quarantine handling, maintenance/local-first fit, and autonomy-readiness.

## Feature Inventory

### Boredom / Serendipity Engine

Status: parked

Potential shape:
Periodic random walk through old knowledge graph nodes, stale topics, or neglected notes. Surfaces a forgotten item and asks whether it connects to current projects.

Why parked:
This is proactive nudging and depends on stable graph links, source provenance, and user-controlled notification boundaries.

Bake-off influence only:
Requires relationship traversal, last-seen timestamps, topic aging, and source-backed resurfacing.

### Future You Simulator

Status: parked

Potential shape:
Monthly generated letter or scenario from a projected future self based on goals, values, projects, and historical patterns.

Why parked:
This is highly interpretive personal memory. It must wait for reviewed self-model storage and strong labeling that output is speculative.

Bake-off influence only:
Requires temporal self-model support, evidence-backed values/goals, confidence labels, and separation of facts from generated reflections.

### Emotional Guardrails

Status: parked

Potential shape:
Detect potentially distressing or sensitive content during onboarding or review, then offer choices such as explore, postpone, quarantine, or forget.

Why parked:
Sensitive personal classification needs careful UX, privacy rules, and review boundaries. It must not silently label or inject emotional claims.

Bake-off influence only:
Requires sensitivity labels, quarantine state, source evidence, user review, and hard-delete support for private data.

### Memory Playback / Remix

Status: parked

Potential shape:
Weekly "this week in your brain" recap with key insights, mood shifts, and surprising connections. Optional remix into blog post, poem, task list, or other artifact.

Why parked:
Requires stable timeline recall and reviewed insight generation. Remixing is a product feature, not memory foundation.

Bake-off influence only:
Requires timeline reconstruction, source-backed summaries, and explicit separation between source records and generated artifacts.

### Cognitive Debt Tracker

Status: parked

Potential shape:
Tracks topics Jacob intended to revisit but did not. Later asks whether to drop, schedule, or deepen them.

Why parked:
This is proactive task and attention management. It depends on durable task/topic modeling and opt-in nudging rules.

Bake-off influence only:
Requires topic extraction, status fields, timestamps, and reviewable candidate promotion.

### Confidence Thresholds

Status: parked

Potential shape:
Every future tool or action has a confidence threshold. Low-confidence actions go to pending approval instead of executing.

Why parked:
Action thresholds require a mature tool runtime, calibrated confidence estimates, and approval UX.

Bake-off influence only:
Requires confidence metadata on memory extraction, retrieval, suggestions, and future action proposals.

### Graduated Autonomy

Status: parked

Potential shape:
Autonomy level changes by domain or tool based on correction history. Frequent corrections reduce autonomy from autonomous to suggest-first.

Why parked:
Autonomy behavior is explicitly later work and must not be wired before the memory foundation and action audit are stable.

Bake-off influence only:
Requires action logs, correction history, tool/domain labels, review outcomes, and autonomy-readiness scoring.

### Debate / Sparring

Status: parked

Potential shape:
Periodically challenges a belief or decision using Jacob's own saved evidence and public facts.

Why parked:
Depends on reviewed beliefs, contradiction handling, source traceability, and user-controlled entry points.

Bake-off influence only:
Requires belief records, source links, confidence, and support for counter-evidence retrieval.

### Temporal Self-Model

Status: parked as product feature; requirement for architecture readiness

Potential shape:
Stores preferences, values, goals, and inferred changes over time with timestamps and source causes.

Why parked:
The self-model is sensitive and interpretive. It must not auto-promote personal claims without review.

Bake-off influence only:
Requires append-only or versioned records, supersession, confidence, and provenance.

### Contradiction Resolution

Status: parked as product feature; requirement for architecture readiness

Potential shape:
Detects conflicting beliefs, preferences, project facts, or source claims. Lets Jacob mark one superseded, keep both as historical, or decide later.

Why parked:
Automated contradiction resolution can corrupt durable memory if implemented before quarantine and review.

Bake-off influence only:
Requires conflict detection, candidate quarantine, source comparison, and resolution state.

### Identity Export

Status: parked

Potential shape:
Portable folder export of values, beliefs, relationships, projects, and graph links.

Why parked:
Needs stable schema and privacy review before exporting a personal self-model.

Bake-off influence only:
Requires portable source ledger and self-model records that can be exported without depending on one retrieval engine.

### Proactive Coach

Status: parked

Potential shape:
Notices patterns in work, routine, goals, or avoidance and suggests small changes using Jacob's own evidence.

Why parked:
Proactive nudging is forbidden in the current focus. Coaching requires opt-in cadence, emotional safety, and reviewed personal memory.

Bake-off influence only:
Requires pattern evidence, source links, confidence, and ability to distinguish suggestion from fact.

### Error-Tolerant Scraping

Status: parked

Potential shape:
Stores raw HTML snapshots before summarization, retries failed extraction with another engine, and deduplicates by content hash.

Why parked:
Scraping behavior is not part of the current foundation implementation and may require external services or dependency review.

Bake-off influence only:
Requires raw source preservation, source hashes, extraction status, retry metadata, and separable summaries.

### Sandboxed Code Execution

Status: parked

Potential shape:
Runs generated code in a constrained sandbox or subprocess with allowed paths and binaries. Generated tools land outside core runtime until reviewed.

Why parked:
This is autonomy and tool-runtime work, not memory architecture foundation.

Bake-off influence only:
Requires action audit records and future tool provenance, but no code execution should be implemented now.

### Trust Dashboard

Status: parked

Potential shape:
Dashboard showing pending approvals, recent autonomous actions, confidence, contradiction alerts, knowledge map, mood timeline, and API spend.

Why parked:
UI work is not approved for this lane. The current task is documentation and architecture planning.

Bake-off influence only:
Requires machine-readable queue states and metadata that a later UI can render.

### Narrative Journaling

Status: parked

Potential shape:
Morning or daily natural-language review of yesterday's activity, editable before durable storage.

Why parked:
Journal generation and personal reflection are product features and need review controls before storage.

Bake-off influence only:
Requires source timeline, draft state, user-edited final state, and separation of generated narrative from raw records.

### Sync / Privacy Toggle

Status: parked

Potential shape:
Optional sync of the memory database with lock files and conflict tracking. Privacy toggle routes sensitive work to local-only models or local-only processing.

Why parked:
Sync and privacy routing have runtime and security implications outside the current memory decision.

Bake-off influence only:
Requires local-first portability, conflict metadata, privacy labels, and replaceable processing layers.

### Socratic Mirror

Status: parked

Potential shape:
Reframes vague or loaded questions before answering and tracks question-quality patterns over time.

Why parked:
This changes chat behavior and depends on sensitive self-model analysis. It needs explicit UX approval.

Bake-off influence only:
Requires durable but reviewed records for question patterns, assumptions, and reframes.

### Decision Gym

Status: parked

Potential shape:
Structured `/decide` workflow for values, options, evidence, second-order effects, blind spots, bias checks, and pre-mortems.

Why parked:
This is a full product workflow and should wait until core memory can reliably retrieve source-backed personal/project evidence.

Bake-off influence only:
Requires values/goals records, decision records, source evidence, outcome follow-up, and timeline recall.

### Belief Stress Testing

Status: parked

Potential shape:
Selects important beliefs, gathers counter-evidence, asks what would change Jacob's mind, and tracks calibration over time.

Why parked:
Belief extraction and challenge must not run on unreviewed or polluted memory.

Bake-off influence only:
Requires belief table readiness, counter-evidence search, confidence, source provenance, and reviewed belief status.

### Mental Model Dojo

Status: parked

Potential shape:
Suggests mental models for current problems and runs practice sessions against real past situations.

Why parked:
Requires mature retrieval and an approved coaching mode.

Bake-off influence only:
Requires tagging situations, outcomes, and applied frameworks with source links.

### Blind Spot Illuminator

Status: parked

Potential shape:
Identifies underrepresented topics, value-action contradictions, or missing perspectives in Jacob's thinking.

Why parked:
This is interpretive and potentially sensitive. It must wait for review, consent, and careful presentation.

Bake-off influence only:
Requires graph density, topic distribution, values/action links, contradiction candidates, and quarantine.

### Socratic Dialogue

Status: parked

Potential shape:
Depth mode where Kitty asks questions, exposes assumptions, and summarizes at the end using Jacob's own context.

Why parked:
This changes conversation mode and depends on stable personal memory boundaries.

Bake-off influence only:
Requires session records, assumptions as candidates, source-backed summaries, and explicit mode labels.

### Wisdom Distiller

Status: parked

Potential shape:
Collects candidate lessons, presents monthly wisdom drafts, and lets Jacob approve durable principles linked to original experiences.

Why parked:
Permanent life-philosophy records are highly personal and must be manually reviewed.

Bake-off influence only:
Requires wisdom candidates, approval state, source links, timestamps, and supersession.

### Curiosity Compass

Status: parked

Potential shape:
Generates a weekly exploration list based on recent questions, projects, blind spots, and library contents.

Why parked:
This is recommendation/proactive behavior and should wait for opt-in rules and reliable retrieval.

Bake-off influence only:
Requires topic graph, recent-question history, knowledge gaps, and source-backed recommendations.

## Future Spec Notes

When this file is reopened, split future work into separate specs. Do not build the entire parked set at once.

Recommended future spec order:

1. Trust and review surfaces: review queue UI, confidence display, source evidence display.
2. Temporal self-model: preferences, values, beliefs, goals, versioning, and export.
3. Cognitive workflows: Decision Gym, Socratic Dialogue, Belief Stress Testing.
4. Reflective recaps: Narrative Journaling, Memory Playback, Wisdom Distiller.
5. Proactive systems: Boredom Engine, Cognitive Debt, Curiosity Compass, Proactive Coach.
6. Autonomy governance: confidence thresholds, graduated autonomy, action audit, sandboxed code execution.

Each future spec must define:

- What data can be auto-promoted.
- What data must be reviewed.
- What data is sensitive.
- What actions are allowed without approval.
- How the user can inspect, correct, retire, or hard-delete records.
- Which files may be edited.
- Which validation commands prove the feature works.

## Explicit Non-Approval

This parking file does not approve implementation of any listed feature.

This parking file does not approve runtime source edits.

This parking file does not approve dependency additions.

This parking file does not approve memory migration.

This parking file exists only to preserve ideas and convert the relevant parts into bake-off requirements.
