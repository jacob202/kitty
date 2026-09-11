# GAR-AWARE-01 — Shared orientation projection and Room Briefing view

**Program:** `docs/superpowers/plans/2026-09-11-shared-operational-awareness.md`
**Status:** authored contract only — implementation not activated by this file
**Execution owner:** interactive lane after fresh KX/#490 collision check
**Base authored against:** `origin/main` `46b46760353e3c0db0c51eff7fc276e0d7dd2157`
**Depends on:** Wave A contract/fixture freeze. KH-CONT-01 is required before the final old-handoff-volume acceptance but must be rebased/renumbered only after its R-1-safe integration point.

## User outcome

A fresh Kitty-capable interactive agent can ask one shared deterministic orientation domain for a bounded operating picture instead of Jacob copying context or each client rebuilding its own truth model.

## Architectural constraint

Do not create a GAR-owned orientation assembler.

`gateway/context_receipt.py`, or a refactored domain module beneath its public interface, is the single shared orientation owner:

```text
KX / Builder / Git / GitHub / runtime / GAR evidence
  -> shared orientation projection
  -> scoped Room Briefing view
  -> CLI / MCP / hooks / clients
```

GAR contributes evidence; it does not become execution authority.

## Intended implementation scope

- `gateway/context_receipt.py`
- a narrowly named orientation helper beneath that domain if decomposition is required;
- existing read-only authority adapters/projections only as necessary;
- focused orientation/context-receipt tests;
- Room Briefing view/serializer tests.
Explicitly out of scope for this packet:

- cross-client startup hook edits (GAR-AWARE-02);
- new event-store/schema work (GAR-AWARE-03);
- Builder/KX/Git/GitHub mutation semantics;
- legacy checkpoint deletion/retirement;
- GAR native UI;
- KH-CONT-01 migration repair on its old base.

## Required contract

The structured orientation result exposes source/freshness/evidence and bounded sections for assignment, lanes, Builder, candidate/publication, runtime, presence, attention, machine events, negative knowledge, and `next_continuation`.

### Assignment

Assignment resolution is:

1. explicit current user/session scope;
2. exact matching scoped thread/handoff/lane/session/candidate evidence;
3. unresolved.

Participant-wide unread directs are attention only and cannot independently assign the session.

Do not add a persistent `assignment_ref` unless a RED acceptance fixture proves existing locators insufficient.

### Continuation

Use:

```yaml
next_continuation:
  action: <action or null>
  authority_source: <source or null>
  authorized: true | false | unknown
  prerequisites: [...]
  evidence: [...]
```
`authorized=true` is legal only when the relevant authority and prerequisites are explicitly proven and linked. Otherwise return the missing refresh/authority; do not infer permission from conversational prose or apparent next-step order.

### Events versus conversation

Read existing `agent_workspace_events` as machine-event evidence where relevant. Machine events are not unread/direct assignments. Preserve typed trusted metadata separately from untrusted prose.

This packet does not change authoritative transition semantics or add event producers. GAR-AWARE-03 owns producer/envelope implementation and must enforce post-authority best-effort emission.

### Negative knowledge

Every active `DO NOT REDO` projection includes:

```text
evidence_locator
scope_key / candidate_ref
observed_at
validity_conditions
invalidation_conditions
superseded_by
```

Expired assumptions demote the item to historical/unknown/superseded evidence rather than permanent policy.

## Wave A prerequisites

Before production edits, freeze tests/fixtures for:

1. two concurrent sessions sharing one participant identity;
2. destruction/rebuild of all derived briefing artifacts;
3. successful authoritative transition followed by failed GAR event publication;
4. malicious imperative text in GAR, PR, handoff, and log evidence.

The production implementation must demonstrate a measured baseline or RED case for every acceptance behavior it changes.
## Acceptance

1. There is one shared orientation owner; no parallel GAR assembler exists.
2. Same-participant session B cannot silently adopt session A's assignment.
3. Participant-wide directs appear as attention only unless exact assignment correlation independently exists.
4. `next_continuation.authorized=true` is impossible without explicit authority/precondition evidence.
5. Source states distinguish `current`, `stale`, `unavailable`, and `unknown`; source failure never becomes empty success.
6. Deleting derived orientation artifacts cannot delete or alter KX, Builder, Git/GitHub, runtime, or GAR source truth.
7. Existing machine events are not treated as unread/direct assignments.
8. Untrusted prose is structurally separated from trusted typed metadata and cannot authorize mutation.
9. Negative knowledge carries validity/invalidation/supersession semantics.
10. Candidate-bound review/validation/publication evidence is exact-head bound and stale after candidate mutation.
11. Orientation construction makes no model/provider call.
12. Room Briefing is a view of the same domain result, not a separately computed truth model.

Final cross-client acceptance additionally requires KH-CONT-01 scoped retrieval to recover a relevant handoff after at least 150 unrelated messages; this is not permission to alter KH-CONT-01 before its R-1-safe rebase point.

## Verification

Exact commands are chosen after implementation paths are frozen, but the minimum verification set must include:

- focused `tests/test_context_receipt.py` coverage;
- focused shared-orientation/Room-Briefing contract tests;
- the four Wave A adversarial fixtures;
- exact-candidate lint/type checks for changed Python;
- `git diff --check`;
- a no-provider-call assertion/probe;
- an independent narrow delta review bound to the frozen candidate.

Do not substitute a broad full-suite run for the focused acceptance; follow current live test-safety authority before any full repository suite.
## Stop conditions

Stop and hand off instead of implementing if:

- the change requires copying authoritative Builder/KX/Git/GitHub/runtime state into a new mutable authority;
- assignment safety appears to require participant identity alone;
- a proposed event write can make an authoritative transition fail;
- the current R-1/R-2/R-3 owner overlaps intended production paths;
- KH-CONT-01 migration renumbering would be performed against its old base;
- the design requires another queue, scheduler, broker, ownership store, world-state file, or model-authored truth layer.

## Recovery / concurrency

Wave A contract/fixture work is independent of the return rollout when path ownership is non-overlapping. GAR-AWARE-01 production work must refresh live KX/#490, open PRs, Builder state, worktrees, and relevant processes immediately before mutation.

R-2 and R-3 do not wait for this packet unless an actual dependency/path collision exists. Preserve KH-CONT-01 at its current candidate until the applicable R-1 integration point; then rebase and renumber it rather than recreating it.

## Authorization boundary

This packet does not authorize merge/main push, destructive operations, credential/environment changes, paid provider/model calls, service restarts, or external messages beyond normal required coordination markers/handoffs.
