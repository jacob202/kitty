# Memory Architecture Decision Draft - 2026-05-06

## Status

Draft for research and bake-off. This is not a production implementation approval.

## Purpose

Choose Kitty's long-term memory architecture without prematurely migrating live memory stores. The decision must support strong recall, automated ingestion, source traceability, low maintenance, and future autonomy while preventing polluted durable memory.

## Decision Summary

Kitty should not choose a final backend yet. The next step is a mini bake-off against a stable memory contract:

`Source Ledger -> Candidate Extraction -> Quarantine/Review -> Durable Memory -> Rebuildable Indexes`

The stable investment is the source ledger, routing policy, provenance model, confidence metadata, review lifecycle, and anti-pollution rules. Retrieval backends remain replaceable adapters until the bake-off proves which engine is worth wiring into production.

## Current Recommendation

Use the current Kitty stack as the live baseline for now:

- LightRAG for domain knowledge and graph-style retrieval.
- ChromaDB for vector fallback.
- SQLite-backed stores for journal, tasks, corrections, and system state.
- MemoryWeave for temporal/entity-style memory, pending persistence verification.

Add no production migration during the bake-off. Build no Boredom Engine, Future You Simulator, autonomous coach, or cognitive feature before the memory foundation is settled.

## Locked Product Priorities

1. Best recall.
2. Automated ingestion.
3. Low maintenance as a hard constraint.
4. Local ownership where possible.
5. Autonomy later, but the memory architecture must not block it.

## Recall Contract

Best recall means all four modes are supported:

- Semantic recall: retrieve related meaning even when wording differs.
- Timeline recall: recover what happened before, after, during a phase, crash, or handoff.
- Exact source recall: point to the source file, session, log, commit, or chunk.
- Relationship recall: connect people, projects, tools, beliefs, decisions, and domains.

Semantic and timeline recall are highest priority. Exact source and relationship recall are second priority, but required.

## Ingestion Contract

Ingestion order:

1. Project/session history: handoffs, tasks, decisions, commits, session excerpts, logs.
2. Books/docs/manuals.
3. Personal captures.
4. Live activity later, after privacy and autonomy boundaries are explicit.

Ingestion mode:

- Auto-scan and stage candidates.
- Auto-promote only project/system facts with direct source evidence.
- Require review for personal, sensitive, interpretive, health, finance, identity, preference, or emotional claims unless Jacob explicitly saves them with `/remember`.

## Safety Contract

The architecture must prevent polluted durable memory above all else.

Required lifecycle states:

- `raw_source`: permanent source text or pointer to source.
- `candidate`: extracted chunk, fact, entity, insight, or relation.
- `quarantined`: low-confidence, conflicting, sensitive, or unsupported candidate.
- `durable`: trusted memory allowed into normal context.
- `retired`: no longer injected, kept for audit unless privacy-deleted.

Deletion policy:

- Soft-delete by default.
- Hard-delete only for explicit privacy deletion.
- Raw logs are not deleted unless the request clearly targets them.

## Cognitive-Governance Requirements From v4 Ideas

The user's v4 blueprint and Cognitive Sharpening Layer contain many future features. Most are parked, but several influence the memory architecture now:

- Confidence metadata must exist on candidates, durable facts, extracted beliefs, and autonomous action proposals.
- Source evidence must be first-class: source path, source type, source timestamp, chunk id, and snippet.
- Conflicts must be represented explicitly, not hidden in summaries.
- Review queues must be human-readable first and agent-processable second.
- Action logs must support future graduated autonomy: tool, input, output, confidence, threshold, status, timestamp, and reversible action metadata where available.
- Temporal self-modeling must be possible later: values, preferences, goals, beliefs, and identity-like records need timestamps, source evidence, confidence, and change history.
- Emotional/cognitive features must not bypass durable-memory review. They may stage candidates, not silently promote them.

These are architecture requirements, not approval to build the features now.

## Backend Candidates For Mini Bake-Off

### Candidate A: Current Kitty Stack

LightRAG + ChromaDB + SQLite stores behind a future StorageRouter.

Strengths:

- Already present in the repo.
- Preserves graph-style retrieval and Chroma fallback.
- Lowest immediate migration risk.

Risks:

- Store boundaries are currently enforced by convention.
- LightRAG and Chroma overlap.
- Direct backend imports can cause wrong-routing bugs.

### Candidate B: LanceDB-Style Embedded Hybrid Retrieval

Embedded local retrieval engine for vector, metadata, and full-text style access.

Strengths:

- Lower maintenance than a server database.
- Strong candidate for local-first semantic retrieval.
- Could simplify Chroma/sqlite-vec overlap later.

Risks:

- Needs prototype evidence before runtime dependency approval.
- Relationship and timeline layers still need explicit schema.

### Candidate C: Cognee-Style Pipeline

Use Cognee as a reference pattern for automated ingestion, graph extraction, memory lifecycle, and recall/improve/forget style operations.

Strengths:

- Closest conceptual match to automated second-brain ingestion.
- Strong influence for candidate extraction and graph memory.

Risks:

- May be too much dependency surface for Kitty's B-launch path.
- Must not become the source of truth unless proven maintainable.

### Deferred Candidates

- pgvector/Postgres: evaluate only if embedded/local options fail scale, query, or durability requirements.
- Qdrant: evaluate only if local embedded retrieval is too weak or slow.
- Hosted all-in-one platforms: deferred unless local-first constraints are explicitly relaxed.

## Mini Bake-Off Rule

Run a prototype-only bake-off before choosing the production retrieval backend.

Scope:

- Isolated scripts and fixtures are allowed.
- New packages are allowed only in isolated prototype environments.
- No production rewiring.
- No memory migration.
- No runtime dependency changes until a winner is approved.

## Scoring Rubric

- Recall quality: 35%.
- Source/provenance quality: 20%.
- Automated ingestion quality: 15%.
- Maintenance/local-first fit: 15%.
- Conflict/quarantine handling: 10%.
- Autonomy-readiness: 5%.

Passing thresholds:

- Overall score at least 75/100.
- Recall at least 8/10.
- Provenance at least 7/10.
- Maintenance/local-first at least 6/10.

If no candidate passes, keep the current Kitty stack and build only the source ledger, memory router, and quarantine queue.

If the best-recall candidate is too hard to maintain, keep the current stack and borrow its patterns.

## First Build After Research

After the decision and bake-off report, the first production build should be:

`Source Ledger + Memory Router + Quarantine Queue`

This must land before replacing Chroma, LightRAG, sqlite-vec, or any live ingestion route.

## Explicit Non-Goals

- No Redis.
- No OB1/Supabase/Postgres migration.
- No Chroma/LightRAG replacement.
- No autonomous Mac-control memory.
- No cognitive-coach features.
- No live activity ingestion.
- No broad memory migration.

## Required Artifacts

1. Bake-off report: `docs/audits/memory-architecture-bakeoff-2026-05-06.md`.
2. Deferred feature parking file: `docs/plans/memory-architecture-deferred-cognitive-features-2026-05-06.md`.
3. Accepted decision record: this draft can either be promoted into `docs/DECISIONS.md` after the bake-off or superseded by a final dated decision section.
4. Later implementation plan: `docs/superpowers/plans/2026-05-memory-architecture.md`.

## Recommended Next Action

Run the mini bake-off with a balanced Kitty seed dataset. Do not modify production memory wiring until the bake-off report exists and Jacob approves the resulting architecture direction.
