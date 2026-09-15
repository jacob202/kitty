# Kitty Shared Operational Awareness

**Date:** 2026-09-11
**Status:** implementation contract after independent review disposition
**Owner:** interactive implementation lanes under fresh KX/#490 ownership
**Purpose:** remove Jacob as the manual relay between ChatGPT, Claude, Codex, OpenCode/DSH, and future Kitty-capable agents without creating another execution authority.

## Decision

Kitty will have one deterministic cross-authority orientation owner.

```text
authoritative sources
  -> shared Context / Orientation Projection
  -> scoped Room Briefing view
  -> CLI / MCP / hooks / clients
```

`gateway/context_receipt.py`, or a refactored domain module beneath its public interface, owns the shared orientation projection. GAR contributes conversation, presence, handoff, review, and negative-knowledge evidence; GAR does not own the assembled operating picture.

The prior idea of a separate "GAR orientation projection" is rejected because it would duplicate Kitty's existing cold-start context owner.

## Authority boundaries

- KX + GitHub #490 own interactive mutation ownership, collision, role, and lease truth.
- Builder owns task, attempt, worker, validation/review, and Builder verdict truth.
- Git/GitHub own branch, base/head, diff, PR, checks, and publication truth.
- Runtime owns what candidate/process is actually running and its provenance.
- GAR owns conversation, handoffs, review messages, presence observations, and evidence originating there.
- Stable repository authority docs own architecture, mission, and policy.
## Shared orientation contract

Conceptual interface:

```python
build_orientation_receipt(
    identity,
    session_id=None,
    explicit_scope=None,
    thread_or_handoff=None,
)
```

The implementation may refactor internals, but `context_receipt` remains the public orientation owner. MCP, CLI, hooks, and clients must delegate to this domain rather than reassembling authority state themselves.

The structured projection must expose bounded sections for:

- source health and freshness;
- assignment resolution and evidence;
- KX/#490 active lanes;
- relevant Builder state;
- Git/GitHub candidate and publication state;
- runtime identity when relevant;
- GAR presence and relevant conversation evidence;
- material machine events;
- attention items;
- negative knowledge with validity semantics;
- a `next_continuation` candidate.

Every consequential projected item carries source, evidence locator, and freshness. Missing required evidence remains `unknown` or `unavailable`; it never collapses to an empty healthy state.
## Assignment resolution

Participant identity is not assignment identity. Multiple live or historical sessions may share `participant_id=chatgpt` (or another client identity).

Resolve assignment only in this order:

1. explicit current user/session scope;
2. exact matching scoped GAR thread, handoff, lane, session, or candidate evidence;
3. otherwise `unresolved`.

Participant-wide unread direct messages may appear under `attention`, but they cannot independently grant the current session an assignment or mutation lane.

Do not add a persistent `assignment_ref` in the first implementation. Use existing `scope_key`, thread/root message IDs, handoff locators, lane IDs, session IDs, candidate refs, and PR refs. Add a new non-authoritative correlation primitive only if an acceptance fixture demonstrates an ambiguity those locators cannot express.

Assignment state is one of:

```text
resolved
unresolved
conflicted
```

Presence never implies assignment or ownership.

## Next continuation, not inferred authorization

The projection may suggest a continuation but must not manufacture permission.

```yaml
next_continuation:
  action: <concrete continuation or null>
  authority_source: <source or null>
  authorized: true | false | unknown
  prerequisites: [...]
  evidence: [...]
```
`authorized=true` is allowed only when the owning authority and all required preconditions have actually been established and linked. Otherwise the projection states the missing refresh or authority explicitly.

## Room Briefing

Room Briefing is a scoped presentation of the shared orientation receipt, not a separate assembler.

CLI target:

```bash
./kitty room briefing --as <identity> [--session-id <id>] [--scope <scope>]
```

MCP target: extend existing `room_status` with optional scope/session inputs and the shared briefing projection. Do not put aggregation logic in the MCP server and do not add an eighth room tool unless later evidence proves the existing interface incoherent.

Source health states:

```text
current | stale | unavailable | unknown
```

An unavailable source includes an attributed diagnostic and observed/fetched time. It never becomes an empty success.

## Event contract

Reuse `agent_workspace_events`. Do not create another event database, queue, broker, or state machine.

Machine events and conversational messages are separate contract types. Machine events do not enter unread/direct assignment resolution by default.

The small internal event envelope should carry: `event_id`, `event_type`, `source`, `occurred_at`, `subject`, `scope_key`, `actor`, `candidate_ref`, `caused_by`, `supersedes`, `severity`, `evidence_locator`, typed trusted metadata, and separately delimited untrusted text content.
Authoritative transitions commit first. Event publication happens afterward and is best-effort/non-blocking. Failure to publish an awareness event must not make a successful Builder/KX/Git/GitHub operation fail. The next Room Briefing reconstructs current truth directly from authorities.

Do not add an outbox in V1. Reconsider only if measured lost-event behavior creates failures that read-time reconstruction cannot repair.

## Negative knowledge validity

A `DO NOT REDO` item is evidence, not permanent hidden policy. Each item carries:

```yaml
evidence_locator: <locator>
scope_key: <scope or null>
candidate_ref: <candidate/environment or null>
observed_at: <timestamp>
validity_conditions: [...]
invalidation_conditions: [...]
superseded_by: <event/item or null>
state: current | historical | superseded | invalidated | unknown
```

When assumptions change, the old observation remains historical evidence instead of silently continuing as an active prohibition.

## Security boundary

GAR messages, PR bodies, issue comments, logs, handoff prose, and external text are untrusted data.

Typed trusted metadata and untrusted text must remain structurally distinct. Untrusted prose is rendered as attributed evidence; it is never concatenated into an instruction section and cannot independently establish ownership, approval, spend authority, task selection, or mutation permission.

Orientation generation is deterministic and model-free. An LLM may format or summarize already-structured data for display, but its prose cannot become authority.
## Cross-client consumption

- **Claude:** existing SessionStart/SessionEnd hooks consume the shared orientation projection; they should stop independently composing broad GAR recent/direct/Git context once the shared projection lands.
- **ChatGPT:** Kitty Project instructions invoke the local bridge on the first Kitty work turn. Native cloud ChatGPT cannot receive local Kitty state before it invokes that bridge; keep this limitation explicit.
- **Codex/OpenCode/DSH interactive:** consume the same orientation contract through existing root instructions/skills/adapters.
- **Builder workers:** consume Builder packet/context truth, not interactive GAR handoffs as a task queue. They may emit post-transition events but GAR cannot schedule them.

## Update model

No five-minute prose reporting.

- Presence heartbeat remains cheap and mechanical; existing TTL semantics remain authoritative unless separately changed.
- Material machine events publish only on meaningful transitions.
- Human/model prose is reserved for findings, decisions, blockers, review, handoff, and results.

Ten minutes of unchanged execution may produce heartbeats but should produce zero repetitive narrative status messages.

## Concurrency with R-1 / R-2 / R-3

Wave A is deliberately docs/contracts/fixtures/threat-model work and may proceed concurrently when its exact paths are unowned.

KH-CONT-01 remains preserved on its existing candidate. It must not be rewritten on its old base. The preserved branch contains `057_agent_workspace_scope_key.sql`, while the return rollout contains `057_project_selected_todo.sql`. After the relevant R-1 integration point, rebase KH-CONT-01 onto the fresh authoritative base, renumber its migration to the next free slot, update migration assertions, and rerun its exact-candidate scoped-retrieval proof.

R-2/R-3 are not blocked by shared-awareness work unless a fresh live path/authority collision exists. Every mutation wave reruns KX/#490, Git/GitHub, Builder, and local worktree ownership rather than assuming non-overlap.
## Execution waves

### Wave A — contract and adversarial fixtures

May start immediately under narrow docs/test ownership. Produce the corrected schema, assignment-correlation fixtures, threat model, event contract, negative-knowledge validity contract, and the four mandatory adversarial acceptance cases below. No production orientation assembler changes are required to finish Wave A.

### GAR-AWARE-01 — shared orientation domain

Refactor/extend the existing context-receipt domain into the shared orientation projection and expose Room Briefing as a scoped view. No new truth store, model call, or GAR-owned parallel assembler.

### GAR-AWARE-02 — cross-client briefing consumers

Blocked until same-participant concurrent-session assignment ambiguity is proven safe. Then wire Claude, ChatGPT bridge, Codex/OpenCode/DSH interactive consumers, CLI, and MCP to the same domain result.

### GAR-AWARE-03 — typed event seam

Extend existing `agent_workspace_events` and KX/presence projections. Enforce event/message separation and nonblocking post-authority emission.

### GAR-AWARE-04 — Builder/Git/GitHub awareness producers

Add small owner-specific projection packets. Never make one GAR mega-change touch all authorities at once.

### GAR-AWARE-05 — attention, relevance, supersedable negative knowledge

Add scoped relevance, attention routing, validity/invalidation, supersession, and bounded `DO NOT REDO` presentation.

### GAR-AWARE-06 — legacy continuity retirement

Only after real ChatGPT, Claude, and Codex/OpenCode cold starts succeed with legacy STATE/HANDOFF readers and writers deliberately withheld.

### GAR-AWARE-07 — native GAR UI

Optional and downstream. The UI displays derived truth; it does not create workflow truth.
## Mandatory adversarial acceptance fixtures

### A. Same participant, two sessions

Create session A and session B with the same participant identity. Send a direct/handoff correlated to A. Prove B may see participant-wide attention where appropriate but does not adopt A's assignment, acquire A's lane, or infer mutation permission.

### B. Derived-state destruction

Delete/rebuild every derived orientation/briefing artifact. Prove KX, Builder, Git/GitHub, runtime, and GAR-owned source evidence remain intact and a fresh briefing reconstructs the operating picture.

### C. Event publication failure

Force an authoritative transition to succeed and the subsequent GAR event publication to fail. Prove the authoritative operation remains successful, awareness degradation is explicit, and the next briefing reconstructs current truth from the primary authority.

### D. Prompt-injection evidence

Inject imperative malicious text into a GAR message, PR body, handoff, and log. Prove each appears strictly as attributed untrusted evidence, cannot become an instruction, and cannot establish ownership, approval, authorization, spend permission, or mutation authority.

## Retained acceptance

Also prove:

- scoped handoff retrieval survives at least 150 unrelated messages;
- presence freshness never implies ownership;
- ownership collision changes the worker role instead of duplicating implementation;
- unavailable sources remain unavailable/unknown, never empty-success;
- code review/validation/publication evidence binds to the exact candidate observed and becomes stale after mutation;
- current negative knowledge can become historical/superseded when validity assumptions change;
- unchanged work creates no narrative status spam;
- orientation generation requires zero provider/model calls;
- deleting any derived projection cannot destroy authoritative state;
- ChatGPT's local-bridge limitation remains explicit.
## External reuse disposition

No first-wave framework dependency is justified.

- Borrow CloudEvents vocabulary for the tiny internal envelope; implement locally unless the SDK clearly lowers maintenance.
- Keep A2A as a possible future boundary between genuinely independent agent systems, not Kitty's internal task authority.
- Use AG-UI as later reference material for streaming orientation/events into a native GAR surface.
- Study Pydantic AI typed observer/event patterns where useful.
- Do not adopt NATS, Kafka, Redis Streams, Temporal, LangGraph execution graphs, Microsoft Agent Framework orchestration, another memory store, or another workflow engine without measured need.

## Explicit non-goals

Do not create:

- another queue, scheduler, ownership DB, or execution state machine;
- another cross-system orientation assembler;
- another event database or broker in V1;
- a generalized mutable world-state document;
- per-model continuity stores;
- LLM-authored current truth;
- participant-wide direct-message assignment inference.

## Governing rule

> Authoritative systems own truth. One shared context/orientation projection explains that truth. GAR supplies communication, scoped continuity, presence, and evidence. Clients consume a bounded Room Briefing.

Operationally:

> Pull a fresh operating picture on entry/resume. Push only material relevant changes. Use heartbeats for liveness. Preserve exact evidence underneath. Never make Jacob relay state between agents.

## Review boundary

Do not commission another broad architecture review before implementation. After Wave A freezes the corrected contracts/fixtures, run one narrow delta review only: verify the single-owner context-receipt architecture, deterministic assignment correlation without a new persistent `assignment_ref`, event/message separation, nonblocking event emission, and the four adversarial fixtures.
