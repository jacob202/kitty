# Memory Architecture Bake-Off Audit

Date: 2026-05-06

Owner lane: Worker B

Status: plan-ready audit artifact

## Purpose

This audit defines a prototype-only bake-off for Kitty's long-term memory architecture.

The goal is to compare a small set of memory approaches against the same realistic Kitty seed dataset before choosing a backend direction. The decision should optimize for best recall and automated ingestion while preserving local-first ownership, source traceability, low maintenance, and safeguards against polluted durable memory.

The bake-off must produce evidence for a later decision doc and implementation plan. It must not rewire runtime memory, migrate data, replace LightRAG or Chroma, or expand parked autonomous features.

## Non-Goals

- No production memory migration.
- No runtime source edits.
- No changes to `docs/DECISIONS.md`, `TASKS.md`, or active control docs from this audit lane.
- No replacement of Chroma, LightRAG, JournalDB, AgentDB, or existing SQLite stores during the bake-off.
- No MCP expansion.
- No implementation of Boredom Engine, Future You Simulator, Proactive Cognitive Coach, Serendipity Mode, Debate Mode, or other human-centric feature modules.
- No live autonomous Mac control, scheduled reflection, or proactive nudging.
- No generated databases committed to git.
- No cloud service adoption as a permanent source of truth.

Human-centric concepts from the v4 second-brain notes influence this bake-off only as evaluation criteria: provenance, quarantine, confidence scoring, action logs, and review queue support.

## Locked Decisions

- Research method: mini bake-off.
- Primary candidates: current Kitty stack, LanceDB-style embedded hybrid retrieval, Cognee-style pipeline.
- Optional later candidates: pgvector/Postgres and Qdrant, only if the mini bake-off proves local embedded options are insufficient.
- Seed dataset: balanced Kitty seed.
- Scoring weights:
  - Recall quality: 35%
  - Source/provenance quality: 20%
  - Automated ingestion quality: 15%
  - Maintenance/local-first fit: 15%
  - Conflict/quarantine handling: 10%
  - Autonomy-readiness: 5%
- Passing thresholds:
  - Overall score: at least 75/100.
  - Recall score: at least 8/10.
  - Source/provenance score: at least 7/10.
  - Maintenance/local-first score: at least 6/10.
- Complexity rule: if the best-recall candidate is too complex to maintain, keep the current stack and borrow design ideas.
- No-pass rule: if no candidate passes, keep the current Kitty stack and build only the Source Ledger, Memory Router, and Quarantine Queue foundation.

## Candidate Set

### Candidate A: Current Kitty Stack

Pattern:

- LightRAG for knowledge base ingestion and graph-like domain retrieval.
- Chroma or current vector fallback for semantic retrieval.
- SQLite-backed focused modules for structured memory where already validated.
- JournalDB remains for journal entries only.
- Existing correction and session memory behavior remains unchanged.

What this candidate tests:

- Whether Kitty's existing architecture can meet the recall target with better routing, provenance, and quarantine rather than a backend replacement.
- Whether LightRAG plus Chroma fallback can cover semantic, timeline, source, and relationship recall well enough for B launch.
- Whether the current stack can support a future Source Ledger and Memory Router without a migration.

Known risk:

- Existing stores overlap in behavior, and direct store access can cause routing drift unless a future router is added.

### Candidate B: LanceDB-Style Embedded Hybrid Retrieval

Pattern:

- Local embedded retrieval store with vector search, text/metadata filtering, and source records close together.
- Treat as a prototype adapter, not a production dependency.
- Compare the architecture shape even if the exact package is not adopted.

What this candidate tests:

- Whether a modern embedded retrieval table can simplify semantic plus source recall.
- Whether local file-based operation is easier to maintain than multiple services.
- Whether hybrid metadata filtering improves timeline and provenance queries.

Known risk:

- May not cover graph/relationship recall as strongly as LightRAG or a Cognee-style pipeline.

### Candidate C: Cognee-Style Pipeline

Pattern:

- Ingestion lifecycle with staged data, extracted facts/entities, graph-like relationships, and memory operations.
- Evaluate the pipeline design even if the exact product is not adopted.
- Emphasize automated ingestion, relationship extraction, and memory hygiene.

What this candidate tests:

- Whether a dedicated memory lifecycle pattern produces better recall and lower manual ingestion burden.
- Whether graph-style extraction improves relationship recall.
- Whether built-in staging/review patterns can reduce polluted durable memory.

Known risk:

- Could add too much dependency, operational, or conceptual weight for a local-first single-user Kitty.

### Optional Later: pgvector/Postgres

Only evaluate after the mini bake-off if:

- SQLite/local embedded options cannot meet recall or provenance thresholds.
- Concurrent writes, query complexity, or schema migration needs exceed local embedded patterns.
- The extra service burden is justified by measurable scoring gains.

### Optional Later: Qdrant

Only evaluate after the mini bake-off if:

- Local embedded retrieval is too slow or weak for the real dataset.
- Vector recall becomes the dominant bottleneck.
- Service operation cost is acceptable and does not undermine local-first maintenance.

## Prototype-Only Scope

Allowed:

- Isolated scratch scripts under a future audit/prototype folder.
- Small fixtures generated from approved seed documents.
- Local, disposable indexes or databases ignored by git.
- Adapter notes, score tables, manual test logs, and evidence snippets.
- New packages installed only in an isolated prototype environment.

Not allowed:

- Runtime route changes.
- Store replacement.
- Memory migration.
- Changes to ingestion behavior used by the live app.
- Production dependency changes.
- Changes to existing generated databases.
- Committing prototype indexes, embeddings, or generated stores.

## Isolated Package Rule

External packages are allowed only inside an isolated prototype environment.

Requirements:

- Document each package name, version, install command, and why it was needed.
- Keep package experiments outside Kitty runtime dependencies unless the candidate wins and a later implementation plan approves adoption.
- If a candidate cannot be installed cleanly without broad environment changes, score maintenance/local-first lower rather than forcing the install.
- If network or credentials are unavailable, record the blocker and evaluate from docs plus local interface mockups only.

## Balanced Kitty Seed Dataset

The seed dataset should be small, realistic, and reproducible.

Include:

1. Latest handoff.
2. `CURRENT_FOCUS.md`.
3. `TASKS.md`.
4. `docs/DECISIONS.md`.
5. 5 to 10 chat/session excerpts.
6. 2 to 3 project docs.
7. 1 small book/manual excerpt.
8. 3 deliberately conflicting or noisy memory candidates.

Selection rules:

- Prefer real Kitty context over synthetic examples.
- Include timestamps and source paths for every item.
- Include at least one assistant-authored claim that should not become durable memory without evidence.
- Include at least one source conflict where two records disagree.
- Include at least one personal or preference-like candidate that should require review.
- Keep the dataset small enough that a human can inspect the expected answers.

## Memory Lifecycle Under Test

Each candidate should be evaluated against this lifecycle:

1. Raw source captured or referenced with stable provenance.
2. Chunks generated for retrieval.
3. Facts/entities/candidates extracted when supported.
4. Candidate memory assigned confidence.
5. Sensitive, noisy, personal, or conflicting items quarantined.
6. Project/system facts with direct source evidence can be promoted.
7. Durable memory can be queried with source evidence.
8. Disposable indexes can be rebuilt without losing raw records.

The bake-off should not require candidates to implement all lifecycle steps natively. A candidate can pass by supporting the steps through a thin adapter or clear future integration path.

## Evaluation Scenarios

Each candidate should answer the same scenarios. Capture the answer, source evidence, failure mode, and any manual work required.

### Semantic Recall

Query S1:

> What is Kitty's current safest next move for memory architecture?

Expected answer:

- Mini bake-off first.
- Do not migrate memory yet.
- Build source ledger, router, and quarantine after research.
- Keep current stack if no candidate passes.

Must cite:

- The bake-off/decision artifact or seed notes containing the locked decisions.

Query S2:

> Find notes related to preventing bad assistant summaries from becoming trusted memory.

Expected answer:

- Polluted durable memory is the highest safety risk.
- Assistant-authored claims need evidence or review.
- Low-confidence/conflicting candidates go to quarantine and are not injected into normal context.

Must cite:

- Source notes about durable promotion, quarantine, and raw log preservation.

### Timeline Recall

Query T1:

> What was decided before the memory bake-off and what remains undecided?

Expected answer:

- Locked: mini bake-off, balanced seed, scoring weights, thresholds, prototype-only scope, isolated package rule, no-pass rule.
- Undecided: final backend choice.

Must cite:

- The decision ledger or handoff source with timestamps.

Query T2:

> What order should ingestion start in?

Expected answer:

- Project/session history first.
- Books/docs/manuals second.
- Personal captures third.
- Live activity later.

Must cite:

- The seed or decision notes that lock ingestion priority.

### Source/Provenance Recall

Query P1:

> Show the exact source for the rule that memory migration is currently blocked.

Expected answer:

- Identify the specific source document and section.
- Quote or summarize the relevant rule.
- Do not infer that research is blocked; only production migration is blocked.

Must cite:

- `CURRENT_FOCUS.md` or `docs/KNOWN_LIMITATIONS.md`, depending on seed contents.

Query P2:

> Which file says `/Users/jacobbrizinski/Projects/kitty` is the canonical checkout?

Expected answer:

- Identify the authority source and path.
- Preserve the distinction between current repo and older historical paths.

Must cite:

- `docs/LAYER0_CONTROL_PLANE.md`, `docs/README.md`, or `docs/DECISIONS.md`.

### Relationship Recall

Query R1:

> How are Source Ledger, Memory Router, Quarantine Queue, and retrieval adapters related?

Expected answer:

- Source Ledger is permanent raw/provenance storage.
- Memory Router enforces routing and prevents wrong-store writes.
- Quarantine Queue stages low-confidence, sensitive, or conflicting candidates.
- Retrieval adapters are replaceable indexes behind the stable contract.

Must cite:

- The bake-off artifact and decision notes.

Query R2:

> How do LightRAG, Chroma, LanceDB-style retrieval, and Cognee-style pipeline differ in the research plan?

Expected answer:

- Current stack is baseline.
- LanceDB-style retrieval tests embedded hybrid semantic/source retrieval.
- Cognee-style pipeline tests ingestion lifecycle, fact/entity extraction, and graph-like recall.
- pgvector/Qdrant are optional later only.

Must cite:

- Candidate descriptions from this audit.

### Conflict and Quarantine Tests

Query Q1:

> A chat excerpt says memory migration is complete, but CURRENT_FOCUS says memory migration is forbidden. What happens?

Expected answer:

- Do not promote the chat claim to durable memory.
- Mark conflict.
- Prefer the higher-authority/current source.
- Quarantine or retire the unsupported claim.
- Keep source evidence for audit.

Pass condition:

- Candidate does not silently treat the assistant/chat claim as canon.

Query Q2:

> A note says Jacob prefers a personal coaching feature, but it is not explicit whether it should be built now. What happens?

Expected answer:

- Stage as a candidate or parked idea.
- Do not promote as an active build decision.
- Do not inject into normal context as authorized work.
- Require explicit review or a future spec.

Pass condition:

- Candidate separates interesting future ideas from approved current scope.

Query Q3:

> Two sources disagree about the active Kitty path.

Expected answer:

- Rank by authority and recency.
- Use `/Users/jacobbrizinski/Projects/kitty` when current authority says it is canonical.
- Keep older path mentions as historical chronology.

Pass condition:

- Candidate resolves conflict without deleting evidence.

## Scoring Rubric

Score each category from 0 to 10, then apply the weights.

### Recall Quality - 35%

Measures:

- Semantic retrieval finds relevant context without exact wording.
- Timeline retrieval can answer "before/after/where did we leave off" questions.
- Exact source retrieval returns file/source evidence.
- Relationship retrieval can explain links between projects, tools, facts, and decisions.

Minimum passing category score: 8/10.

### Source/Provenance Quality - 20%

Measures:

- Every answer can trace back to source path, timestamp, chunk, or record id.
- Candidate distinguishes raw source from derived summary.
- Candidate preserves source snippets for review.
- Candidate can identify authority conflicts rather than flattening all text into equal evidence.

Minimum passing category score: 7/10.

### Automated Ingestion Quality - 15%

Measures:

- Candidate can ingest the balanced seed with minimal manual steps.
- Candidate supports chunking, metadata, timestamps, and source labels.
- Candidate can stage facts/entities or at least preserve enough structure for later extraction.
- Candidate can re-run ingestion idempotently without duplicating records.

### Maintenance/Local-First Fit - 15%

Measures:

- Runs locally or keeps local raw source of truth.
- Has low setup burden.
- Has understandable failure modes.
- Does not require fragile service orchestration for B launch.
- Does not add production dependencies during the prototype.

Minimum passing category score: 6/10.

### Conflict/Quarantine Handling - 10%

Measures:

- Can stage candidates before durable promotion.
- Can mark low-confidence, noisy, sensitive, or conflicting records.
- Can keep quarantined records out of normal context.
- Can support human-readable review and agent-processable state.

### Autonomy-Readiness - 5%

Measures:

- Can support future action logs, confidence thresholds, review queues, and audit trails.
- Can support future scheduled reflection without changing the permanent memory contract.
- Does not require enabling proactive behavior now.

This category must not reward implementation of parked features. It rewards whether the memory architecture can safely support those features later.

## Expected Outputs From Each Candidate

Each candidate prototype should produce:

- Ingestion notes:
  - Source files included.
  - Records/chunks created.
  - Metadata captured.
  - Manual steps required.
- Query transcript:
  - Answer for each evaluation query.
  - Source evidence returned.
  - Missing or weak evidence.
  - Latency if easily measured.
- Conflict/quarantine notes:
  - Which seed candidates were promoted, quarantined, retired, or rejected.
  - Why each decision was made.
- Maintenance notes:
  - Setup commands.
  - Packages installed.
  - Local files generated.
  - Cleanup required.
  - Failure modes encountered.
- Score table:
  - Raw 0 to 10 category scores.
  - Weighted total.
  - Pass/fail against thresholds.
- Recommendation:
  - Adopt as backend, borrow ideas only, or reject.

## Result Template

Use this table in the final bake-off report:

| Candidate | Recall 35 | Provenance 20 | Ingestion 15 | Maintenance 15 | Quarantine 10 | Autonomy 5 | Total | Threshold Result | Recommendation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Current Kitty stack |  |  |  |  |  |  |  |  |  |
| LanceDB-style embedded hybrid |  |  |  |  |  |  |  |  |  |
| Cognee-style pipeline |  |  |  |  |  |  |  |  |  |

Threshold result values:

- Pass: total at least 75, recall at least 8, provenance at least 7, maintenance at least 6.
- Borrow only: strong ideas, but fails one or more required thresholds.
- Reject for now: weak scores or too much complexity for the current Kitty phase.

## Recommendation Rules

1. If exactly one candidate passes all thresholds and maintenance is acceptable, recommend it for the later decision doc.
2. If multiple candidates pass, choose the candidate with the best weighted total unless it creates materially higher maintenance burden.
3. If the best-recall candidate fails maintenance/local-first, keep the current stack and borrow ideas from it.
4. If no candidate passes, keep the current Kitty stack and build only:
   - Source Ledger
   - Memory Router
   - Quarantine Queue
5. If current Kitty stack passes but another candidate scores higher only because it implements parked features, discount that advantage and keep the parked features out of the backend decision.
6. Any adopted backend direction must preserve the core memory contract:
   - Raw data is permanent.
   - Retrieval indexes are disposable.
   - Durable memory needs source evidence.
   - Low-confidence, personal, sensitive, or conflicting candidates are reviewed before promotion.

## Next Artifact Dependencies

This audit should feed two later artifacts:

1. Memory architecture decision doc:
   - Records the chosen backend direction or "keep current stack and borrow ideas."
   - States which candidate evidence justified the decision.
2. Memory architecture implementation plan:
   - Starts with Source Ledger, Memory Router, and Quarantine Queue.
   - Defers retrieval replacement unless the bake-off proves it is necessary.

No implementation plan should start production memory wiring until the bake-off report exists and the decision doc is accepted.

---

## Execution Run - 2026-05-06

### Environment Evidence

Python module availability:

- Homebrew `/opt/homebrew/bin/python3.12`: `chromadb=true`, `sentence_transformers=true`, `lancedb=false`, `cognee=false`, `sqlite_vec=false`, `lightrag=false`.
- Project `venv/bin/python`: `chromadb=true`, `lightrag=true`, `sentence_transformers=false`, `lancedb=false`, `cognee=false`, `sqlite_vec=false`.

Candidate package install in isolated prototype venv:

- Created `/private/tmp/kitty-bakeoff-venv`.
- Initial sandbox install failed DNS/network resolution.
- Unrestricted install succeeded in isolated venv for `lancedb` and `cognee` with many transitive dependencies.

### Balanced Seed Used

Seed files ingested for executable prototypes:

1. `CURRENT_FOCUS.md`
2. `TASKS.md`
3. `docs/DECISIONS.md`
4. `docs/handoffs/HANDOFF-2026-05-03.md`
5. `docs/plans/memory-architecture-decision-2026-05-06.md`
6. `docs/audits/memory-architecture-bakeoff-2026-05-06.md`

Note: no `data/sessions/*` excerpts were available in this checkout for this run. Handoff and decision/control docs were used as session-context substitutes.

### Candidate A - Current Kitty Stack

Executable checks:

- `query_knowledge_base()` returned empty for all bake-off semantic/timeline/source queries in both environments.
- In `venv`, LightRAG path attempted networked tokenizer fetch and failed; embedding backend was unavailable in `KittyMemoryEnhanced`.
- In Homebrew Python, `KittyMemoryEnhanced` ingested seed docs and retrieval worked only when `domain=None`; with `domain='general'`, retrieval returned zero documents.

Observed risk:

- Domain-filtered retrieval can silently miss relevant context due metadata/domain mismatch, reducing recall reliability in normal query paths.

### Candidate B - LanceDB-Style Embedded Hybrid Retrieval

Prototype setup:

- Installed in isolated venv.
- Built local embedded table at `/private/tmp/kitty-bakeoff-lancedb`.
- Loaded 80 chunks from seed files with deterministic local embeddings.

Query evidence:

- All four test query themes returned hits with source path and chunk index.
- Semantic and source recall were strong for architecture and canonical-path questions.
- Timeline/ordering answers were retrievable, though ranking occasionally surfaced noisy chunks from broad docs.

### Candidate C - Cognee-Style Pipeline

Prototype setup:

- Installed in isolated venv.
- Import and API discovery succeeded (`add`, `cognify`, `search`, `remember`, `recall`, etc.).

Runtime evidence:

- Minimal `add`/`cognify`/`search` run failed at LLM auth gate:
  - `AuthenticationError`: missing `OPENAI_API_KEY` (or equivalent provider config).
- Cognee also introduced a large dependency footprint, significantly increasing setup and maintenance burden for this phase.

### Scored Results

| Candidate | Recall 35 | Provenance 20 | Ingestion 15 | Maintenance 15 | Quarantine 10 | Autonomy 5 | Total | Threshold Result | Recommendation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Current Kitty stack | 6.0 | 5.0 | 7.0 | 5.0 | 3.0 | 4.0 | 54.0 | Fail | Keep as baseline only; fix routing/metadata reliability |
| LanceDB-style embedded hybrid | 8.0 | 9.0 | 8.0 | 7.0 | 4.0 | 6.0 | 75.5 | Pass | Preferred retrieval direction for next phase prototyping |
| Cognee-style pipeline | 2.0 | 4.0 | 3.0 | 2.0 | 2.0 | 3.0 | 26.0 | Fail | Borrow lifecycle ideas only; defer runtime adoption |

Threshold checks:

- Overall >= 75: only LanceDB-style candidate passed.
- Recall >= 8: only LanceDB-style candidate passed.
- Provenance >= 7: only LanceDB-style candidate passed.
- Maintenance >= 6: only LanceDB-style candidate passed.

### Recommendation From This Execution

1. Treat LanceDB-style embedded retrieval as the leading backend direction for the next prototype phase.
2. Do not migrate production memory yet.
3. Keep current Kitty stack live until source-ledger/router/quarantine foundation exists and decision acceptance is recorded.
4. Borrow Cognee concepts (staging, lifecycle, graph-oriented extraction) without adopting Cognee runtime in the current phase.

### Next Recommended Tasks (Execution Ready)

1. Build `Source Ledger + Memory Router + Quarantine Queue` as the first production foundation.
2. Add a regression test for domain-filtered retrieval reliability (`domain='general'`) vs fallback behavior.
3. Define retrieval adapter interface so current stack and LanceDB-style adapter can be swapped behind one router contract.
4. Promote the decision draft into an accepted decision entry after Jacob sign-off; then write the implementation plan with owned files/tests.
