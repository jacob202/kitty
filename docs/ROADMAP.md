# Kitty Roadmap

**Current gate:** No broad roadmap stage is active
**Mission record:** [`ACTIVE_MISSION.md`](ACTIVE_MISSION.md) — KPROOF-001 is superseded
**KPROOF deadline:** 2026-08-18 (elapsed; no durable pass verdict recorded)
**Last reconciled:** 2026-08-19

This remains the sole roadmap authority. A terminal mission does not automatically activate the next historical sequence. Issues, plans, packets, branches, and research become current work only through this roadmap or explicit Jacob approval tied to an accepted decision/packet.

## Current operating rule

KPROOF-001's bounded proof window ended without a durable record satisfying its full pass contract. The mission is therefore superseded as a scope gate, **not passed**. Jacob explicitly chose to continue targeted Kitty work after the deadline; that approval does not retroactively satisfy KPROOF and does not activate M1–M6.

Individually approved post-deadline work may proceed when its authority is explicit. Current examples are the product-surface convergence work and ADR 0040's Image Lab packets. They are not a second roadmap.

The historical M1–M6 target below is **SUPERSEDED AS AN EXECUTION SEQUENCE**. ADR 0039 plus the 2026-08-23 Constitution amendment resolve the product-surface decision in favor of native Kitty; the old M1/M2 plan to make Open WebUI primary must not be executed. No broad replacement roadmap is activated implicitly by that correction.

Runtime behavior outranks documentation, tests, commits, and agent claims. Reliability, truthful status, bounded cost, recovery, and a completed user outcome outrank speculative architecture or more surfaces.

## Closed gate — KPROOF-001 (superseded; no pass verdict)

**Decision to prove:** Can Kitty take a software request from conversation to a working, verified feature without Jacob manually coordinating the agents?

Historical proof sequence (not current execution):

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

No durable evidence recorded the full pass condition by 2026-08-18. The mission is superseded rather than relabelled pass/fail after the fact; Jacob's later decision to continue targeted work is recorded separately from the proof verdict.

## Blocked post-proof target — Version 2, milestones M1 to M6

There is one roadmap: this file. [`ROADMAP_V2.md`](ROADMAP_V2.md) is its detail appendix
for the milestones below — objectives, packet catalog, and Builder initiative mapping.
It is not a second plan to choose between. KPROOF no longer runs, but this sequence still does **not** start automatically.

The M1–M6 table is retained only as target history. Its Open WebUI-primary M1/M2 premise is superseded by ADR 0039 and the amended Constitution, so it is not an executable dependency chain.

| # | Milestone | What is true when it is done |
|---|---|---|
| M1 | Historical shell target (superseded) | Open WebUI-primary premise superseded by ADR 0039; native Kitty is canonical |
| M2 | Console becomes the operator surface | The Next.js app stops competing as a chat shell and is re-roled as the operator console |
| M3 | Builder → Work integration | The shell and console show real Builder execution as product-level work, not internals |
| M4 | Failure, interruption, and receipts | A turn and a Builder run survive any provider, network, or crash failure, with honest receipts |
| M5 | Storage spine consolidation | The flagged simplification lands once everything relies on the Gateway authority and evidence spines |
| M6 | Ship the Console officially | The Console is the supported operator experience, with docs, onboarding, and backup/restore |

Each milestone is user-visible, independently releasable, leaves the tree green, and
reduces complexity. They are ordered by dependency, so M2 does not begin before M1 lands.

Carried into M1–M6 rather than tracked separately: keeping repository gates honest and
authority documents consistent; the real #270 phone/PWA capture → return → response loop;
documents/projects import and search; the Tutor question/answer loop; Image Lab's one real
generation with cost and provenance evidence; the default-branch enforcement work; and
selected bounded automations that remove repeated work and stay explicit and reversible.

### After M6 — portability and leverage

Not scheduled against a milestone, and not started before M6 lands. Kept here so it keeps
a place in the order rather than disappearing:

- revalidate bounded PAA portability work rather than adopting a framework wholesale;
- salvage broad historical PRs by subsystem instead of merging them as unverified units;
- evaluate agent and model patterns through identical tasks, budgets, and evidence;
- reuse the proven browser evidence harness for later product-studio and audit work;
- improve routing through measured outcomes, not reputation or model-generated scores.

A capability is `proven`, `preview`, `developer-only`, `blocked`, or `hidden`. Unproven
capability must not look shipped.

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
