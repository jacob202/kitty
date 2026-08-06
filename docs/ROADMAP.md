# Kitty Roadmap

**Current stage:** 1 — Trustworthy Daily Driver  
**Active mission:** [`ACTIVE_MISSION.md`](ACTIVE_MISSION.md)  
**Last reconciled:** 2026-08-04

This is the sole active delivery order. It is intentionally short. Issues, plans, packets, branches, and research do not become current work unless this roadmap or the active mission explicitly places them next.

The pre-reconciliation roadmap remains available in Git history and is indexed by [`archive/ROADMAP_PRE_RECONCILIATION_2026-08-04.md`](archive/ROADMAP_PRE_RECONCILIATION_2026-08-04.md).

## Operating rule

Finish the smallest real user outcome, prove it in the running system, and only then widen scope. Reliability, security, truthful status, and completed daily workflows outrank speculative architecture or more surfaces.

## Stage 1 — Trustworthy daily driver

**Goal:** Jacob can start Kitty, use the approved Open WebUI shell, receive a real response, preserve continuity, recover from failures, and understand what is happening without terminal archaeology.

Execute in this order:

1. **Repository and security baseline**
   - keep deterministic CI green;
   - merge isolated security updates;
   - fix false or broken review gates rather than bypassing them;
   - keep custom clients loopback-only until real authentication exists.

2. **One authoritative operating picture**
   - keep README, Architecture, Decisions, Project Status, Active Mission, and this roadmap consistent;
   - preserve superseded material as history, not parallel authority;
   - keep image Git history unchanged by explicit owner decision.

3. **Prove Open WebUI locally**
   - clean start from supported commands;
   - real streamed chat;
   - actual model/provider attribution;
   - conversation persistence across restart;
   - bounded tools and memory behavior;
   - understandable failure and recovery when a dependency is unavailable;
   - no paid verification without explicit charge authorization.

4. **Finish one continuity loop**
   - complete #270 on the real phone/PWA;
   - capture one non-sensitive insight;
   - return it once at the intended time;
   - record Act, Snooze, or Archive;
   - prove restart and retry do not duplicate the return or action.

5. **Enforce repository trust**
   - complete #399's ledger for all active workflows;
   - retain the smallest justified CI/operations set;
   - retire only conclusively obsolete one-shot workflows;
   - map required checks to real stable contexts;
   - enable default-branch enforcement when the configuration can be applied safely.

### Stage 1 exit gate

Stage 1 is complete only when:

- main is green and the known security patch is merged;
- the authority documents agree;
- Open WebUI passes the clean-start/chat/persistence/restart proof on Jacob's Mac;
- #270 has real phone and deduplication evidence;
- the workflow ledger and enforceable protection configuration exist;
- no primary claim depends on chat history or unsupported inference.

## Stage 2 — Complete existing user workflows

Begin only after Stage 1 exits.

Prioritize existing workflows over new surfaces:

1. documents/projects: native import, progress, search, source opening, and useful failures;
2. Tutor: grounded question/answer loop with inspectable sources;
3. normal-language work submission: clear acknowledgement, progress, result, and recovery without exposing Builder internals;
4. Image Lab: one real generation and one genuine reference-conditioned continuation with cost/provenance/cleanup evidence;
5. selected automations that remove repeated work and remain explicit, bounded, and reversible.

A capability is `proven`, `preview`, `developer-only`, `blocked`, or `hidden`. Unproven capability must not look shipped.

## Stage 3 — Portability and leverage

Begin only after Stage 2 produces stable daily value.

Candidate work:

- rebase and revalidate #391 / #389 as a bounded PAA portability profile;
- split and salvage #396 by subsystem rather than merging it whole;
- evaluate task-level agent patterns from #390 through identical KittyBench tasks and budgets;
- build Product Studio/audit capabilities only by reusing the proven browser evidence harness;
- improve model routing through measured outcomes, not reputation or model-generated deciding scores.

## Explicitly deferred

Until prior gates pass, do not start:

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
- deterministic commands and exit results;
- live runtime steps for user-facing behavior;
- service-on and service-off behavior where relevant;
- explicit remaining limitations;
- no contradiction between success language and missing evidence.
