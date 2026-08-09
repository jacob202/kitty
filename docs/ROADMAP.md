# Kitty Roadmap

**Current gate:** KPROOF-001 — Two-Week Builder Proof  
**Active mission:** [`ACTIVE_MISSION.md`](ACTIVE_MISSION.md)  
**Proof deadline:** 2026-08-18  
**Last reconciled:** 2026-08-08

This is the sole active delivery order. Issues, plans, packets, branches, and research do not become current work unless this roadmap or the active mission explicitly places them next.

## Current operating rule

KPROOF-001 temporarily gates every broader roadmap stage. Finish the smallest real proof, verify it in the running system, and make the continue-or-pause decision before widening scope.

The previous trustworthy-daily-driver sequence is preserved below as post-proof work. It is **not** parallel execution while KPROOF-001 is running, except where an item is directly required to prove the active mission.

Runtime behavior outranks documentation, tests, commits, and agent claims. Reliability, truthful status, bounded cost, recovery, and a completed user outcome outrank speculative architecture or more surfaces.

## Active gate — KPROOF-001

**Decision to prove:** Can Kitty take a software request from conversation to a working, verified feature without Jacob manually coordinating the agents?

Execute in this order:

1. **Establish live baseline**
   - inspect the canonical Mac checkout, current services, Builder state, provider availability, and test/build baseline;
   - treat unavailable evidence as unknown rather than reconstructing it from prose;
   - do not spend proof budget merely to inspect state.

2. **Confirm the experience direction**
   - compare the bounded conversation-plus-progress prototype with the current usable surfaces;
   - keep only the smallest experience Jacob would actually choose for the proof.

3. **Repair the truthful Builder control seam**
   - make failed Builder actions fail visibly rather than appearing successful;
   - refresh the authoritative runtime projection after successful actions;
   - expose only the minimum contextual recovery action needed for the proof;
   - verify the behavior in the running application, including a failure path.

4. **Prove conversation → approved durable job**
   - turn one bounded conversation outcome into an inspectable Mission/result contract;
   - require one meaningful approval;
   - persist the job without Jacob translating it into a worker prompt or CLI sequence.

5. **Complete one real feature loop**
   - let Builder select a capable worker;
   - edit in an isolated branch/worktree;
   - launch the real application and exercise the requested behavior;
   - capture validation evidence and a second-model review;
   - repair findings through the same durable job.

6. **Prove recovery**
   - demonstrate that a controlled interruption or worker/provider failure does not erase the job, context, evidence, or next action;
   - no manual reconstruction counts as success.

7. **Make the verdict**
   - score functioning result, Jacob intervention, clarity, recovery, total spend, and whether Jacob would voluntarily choose Kitty for the next project task;
   - continue or pause exactly as `docs/ACTIVE_MISSION.md` requires.

### KPROOF-001 exit gate

The proof passes only when one real Builder feature loop works in the launched application, survives the required review/recovery checks, stays within the authorized budget, and the resulting experience is preferable to manually coordinating direct AI tools.

If the proof fails by 2026-08-18, pause Kitty for several months and preserve the evidence rather than negotiating the standard downward.

## Post-proof sequence — not active during KPROOF-001

If KPROOF-001 passes, reconcile this roadmap from the proof evidence before starting the next stage. The retained order is:

### Trustworthy daily driver

- keep deterministic repository gates honest;
- keep authority documents consistent;
- prove Open WebUI clean start, real chat, persistence, restart, attribution, and understandable failure recovery on Jacob's Mac;
- complete one real #270 phone/PWA capture → return → response loop with restart/deduplication evidence;
- finish the workflow ledger/default-branch enforcement work only when it can be applied safely.

### Complete existing user workflows

Prioritize existing workflows over new surfaces:

1. documents/projects: native import, progress, search, source opening, and useful failures;
2. Tutor: grounded question/answer loop with inspectable sources;
3. normal-language work submission beyond the single KPROOF feature: acknowledgement, progress, result, and recovery without exposing Builder internals;
4. Image Lab: one real generation and one genuine reference-conditioned continuation with cost/provenance/cleanup evidence;
5. selected automations that remove repeated work and remain explicit, bounded, and reversible.

A capability is `proven`, `preview`, `developer-only`, `blocked`, or `hidden`. Unproven capability must not look shipped.

### Portability and leverage

Only after stable daily value:

- revalidate bounded PAA portability work rather than adopting a framework wholesale;
- salvage broad historical PRs by subsystem instead of merging them as unverified units;
- evaluate agent/model patterns through identical tasks, budgets, and evidence;
- reuse the proven browser evidence harness for later product-studio/audit work;
- improve routing through measured outcomes, not reputation or model-generated scores.

## Explicitly deferred

Until the active gate passes, do not start:

- another custom frontend foundation;
- broad PAA or agent-framework refactoring;
- a second queue, memory platform, scheduler, event bus, or Builder state machine;
- unlimited multi-agent swarms;
- new image architecture beyond the bounded existing slice;
- paid/GPU experiments without a hard budget and explicit authorization;
- image-history rewriting or purging.

## Evidence standard

Work is complete only when its claim can be reconstructed from supported evidence:

- exact commit/PR and changed paths;
- deterministic commands and exact results;
- live runtime steps for user-facing behavior;
- service-on and service-off behavior where relevant;
- explicit remaining limitations;
- no contradiction between success language and missing evidence.
