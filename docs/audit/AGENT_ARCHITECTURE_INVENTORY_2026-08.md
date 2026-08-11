# Agent architecture inventory — AAA-0 (#390)

Pinned source for this review: `FareedKhan-dev/all-agentic-architectures@cf9d620a8cc55d59589399c30f305e6dfaa428ec` (release line 0.3.0), as pinned by #390.

Scope: map Kitty's existing code to the pattern catalogue in #390. This is
inventory only — no `ADOPT`/`ADAPT`/`DEFER`/`REJECT` disposition and no
KittyBench comparison. Those are AAA-1 through AAA-4, sequenced separately in
#390 and out of scope here.

Status legend: `EXISTS` (real, working), `PARTIAL` (present but incomplete or
mixed with other responsibilities), `ABSENT` (no equivalent), `SUPERSEDED`
(Kitty already solved the underlying problem a different way), `NOT NEEDED`
(pattern doesn't fit Kitty's product shape).

## Cross-cutting: deterministic-picker discipline (#390 A1)

**Status: PARTIAL, already the dominant style.**

- `gateway/action_queue.py` — every action carries a `risk_tier` (T0/T1/T2)
  loaded read-only from `config/action_tiers.json` and enforced in the
  executor registry, not inferred by a model per-call.
- `gateway/compute_governor.py:158,235` — `DispatchRecord.risk_class` is a
  closed enum (`RISK_CLASSES`), validated (`compute_governor.py:235-236`),
  and a `blocker` class requires named evidence (`compute_governor.py:252`),
  not a numeric confidence.
- No `score: 1-10` or bare `confidence: float` pattern found driving routing,
  approval, merge, or escalation anywhere in `gateway/*.py` (checked via
  grep across the module). `gateway/tutor.py`'s 1-3 rating is a user-entered
  recall rating, not a model self-score, and doesn't drive an action.
- Gap: `gateway/domain_router.py` is a plain keyword scorer (deterministic
  already) but its evidence/coverage is thin per its own docstring — the
  issue explicitly says to improve this separately from AAA work, not fold
  it in here.

**AAA-1 (decision audit) can start from a short list, not a blank page.**

## A2 — StrategyResult contract

**Status: ABSENT as a named, shared contract.**

Kitty has several per-domain result shapes that carry overlapping fields
(status, evidence, cost) but no single `StrategyResult` envelope:

- `gateway/builder_attempt.py` — attempt records carry an implementation
  result and an independent review result, both size-capped, but the schema
  is Builder-specific.
- `gateway/verifier.py` — `verify()` / `verify_with_review()` return ad hoc
  dicts (test results + review), not a shared envelope.
- `gateway/compute_governor.py:158` — `DispatchRecord` is the closest thing
  to a shared decision-envelope today, but it covers dispatch/authorization,
  not strategy output.

AAA-2 (registry spike) has real material to wrap, not a greenfield build.

## A3 — Pre-action Dry-Run boundary

**Status: EXISTS, in production shape already.**

`gateway/action_queue.py` is exactly this pattern, already durable:
`proposed → (approved|rejected) → executed|failed`, one row per action, T0
auto-executes, T1 drafts locally only, T2 needs explicit per-action approval.
This is stronger than the source repo's mocked dry-run — real state
transitions, not simulated ones. No further borrow needed here; #390 A3
should point at this file rather than propose a new one.

## A4 — Plan-Execute-Verify per-step evidence

**Status: EXISTS in KittyBuilder, PARTIAL elsewhere.**

- `gateway/builder_attempt.py` + `gateway/builder_queue.py` — durable
  attempts, lease fencing, worker transitions, expired-lease recovery. This
  already exceeds the source repo's in-memory PEV demo, per #390's own
  framing ("KittyBuilder already contains stronger... machinery").
- `gateway/builder_isc.py` — Ideal State Criteria: binary success criteria
  derived and checked per packet, shared between the 6-stage pipeline and
  the queue. This is the acceptance-gate half of PEV.
- `gateway/agent_runner.py` — sub-agents tag each step with an
  OBSERVE→ORIENT→DECIDE→ACT→VERIFY→LEARN phase, but (per its own docstring)
  this is a lighter-weight, non-durable loop distinct from Builder's.
  PARTIAL: no independent-review step, no lease/retry durability.

## B1 — Task-shape strategy selection / Meta-Controller

**Status: PARTIAL.**

- `gateway/domain_router.py` — deterministic keyword classifier over 5
  domains (`soul | repair | health | research | code`), used by both the
  context assembler and route selection. This is real, but coarse.
- `gateway/council.py` — `ANALYZE → ROUTE → VERIFY → SYNTHESIZE`: routes
  decomposed sub-tasks to specialist agents and always ends in one
  synthesized reply. Closer to a Meta-Controller than `domain_router.py`,
  but scoped to conversational fan-out, not general task routing.
- No shared strategy registry (identifier, version, capability, cost/risk
  envelope, acceptance gate) exists across these — each router owns its own
  ad hoc rules. B1 in #390 would consolidate, not invent from nothing.

## C1 — Self-Discover

**Status: ABSENT.** No module selects/adapts reasoning modules before
solving. `gateway/agent_runner.py`'s `planner` preset breaks a goal into
ordered steps but doesn't choose *how* to reason first.

## C2 — Reflection

**Status: PARTIAL.** `gateway/verifier.py`'s `verify_with_review()` is a
bounded reflect-and-check pass (verify + review), gated on real test output
— exactly the condition #390 sets for keeping Reflection ("only when a
deterministic verifier can detect improvement"). No general-purpose
reflection loop exists outside this path.

## C3 — Adaptive / Corrective / Self-RAG

**Status: PARTIAL.** `gateway/researcher.py`'s `DeepResearcher` combines
search, scraping, and ingestion, but per its docstring is a single fixed
pipeline — no evidence-grading step, no retry/fallback on insufficient
retrieval, no no-retrieval/single-hop/multi-hop routing. `gateway/tutor.py`
is RAG-shaped (ingest → ask → review) but also fixed, not adaptive; its
"NEVER guesses" rule is a hard-coded refusal, not a graded retry.

## C4 — Episodic + semantic memory / MemGPT patterns

**Status: EXISTS, via a different substrate than the source repo.**

- `gateway/memory_weave.py` — temporal knowledge graph with provenance,
  confidence decay, and conflict resolution; explicitly designed to learn
  from corrections and tool failures. This is closer to what C4 is
  hypothesizing than a from-scratch MemGPT port would be.
- `gateway/honcho.py` — weekly pattern mirror over gateway traces (semantic
  summarization of episodic history).
- `gateway/journal.py` — ambient + intentional episodic capture.
- `gateway/memory_graph.py` is the unified read boundary over all of the
  above (per `CLAUDE.md`). #390's own instruction applies directly: treat
  MemGPT-style stores only as a hypothesis to test against what's already
  here, not a default adoption.

## C5 — SWE-Agent bounded action vocabulary

**Status: SUPERSEDED for Kitty's own execution, relevant only for weak/free
worker adapters.** `gateway/builder_adapters.py` plus the queue/attempt/lease
machinery already give Builder a controlled, auditable action surface far
past `list/read/write/run_check/answer`. The narrow bounded vocabulary is
still worth referencing if/when a genuinely weak model is wired in as a
Builder worker adapter — not for Builder's own control plane.

## C6 — STORM multi-perspective research

**Status: ABSENT.** `gateway/researcher.py` and `gateway/council.py` do not
run multiple perspectives against one research question. No current need is
documented; #390 already gates this behind explicit budget approval.

## Defer/reject list from #390 — confirmed nothing preempts these

Checked for accidental prior adoption; found none:

- No LangGraph import anywhere in `gateway/`.
- No always-on Meta-Controller — `council.py` and `domain_router.py` are the
  two routing surfaces, both bounded/deterministic-first.
- No Tree of Thoughts / LATS / Debate / Blackboard / graph-memory-as-primary
  implementation.
- `memory_weave.py` is a temporal graph used as one signal inside
  `memory_graph`'s unified read path, not a competing retrieval platform —
  consistent with the reject condition on GraphMemory-as-replacement.

## Net finding

Kitty is further along on AAA-0's own criteria than #390 assumed when
written: the dry-run boundary (A3) and the deterministic-picker discipline
(A1) are already in production, not gaps to fill. The real open work is
consolidation (B1's registry, A2's shared result contract) and the two
genuinely absent patterns (C1 Self-Discover, C6 STORM) that #390 already
gates behind evaluation, not immediate adoption.

## Next step

AAA-1 (decision audit) has a short, named starting list from the section
above rather than a blank search: confirm `action_queue.py` risk tiers and
`compute_governor.py` risk classes are the only two decision surfaces in
scope, and check whether any narrower module (routes, tool selection) has a
numeric-score decision this pass missed before calling AAA-1 done.
