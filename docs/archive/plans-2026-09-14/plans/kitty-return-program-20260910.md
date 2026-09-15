# Kitty return program

**Decision date:** 2026-09-10. **Execution owner:** interactive lead per outcome.
**Authority:** [ROADMAP](../ROADMAP.md) owns ordering; [Mission](../ACTIVE_MISSION.md) owns reviewed intent; Builder owns its admitted execution. This program details the current roadmap slice. Packet existence is not activation.
**Baseline:** GitHub main `505bdc09901084cc7730d6f7d0c442f04d805b4f`. Live evidence and existing owners take precedence over this dated snapshot.

## The decision

Finish one convincing return journey before expanding the companion. Recover the existing frontend/runtime candidates, connect a durable result to Work and Library, and prove that a conversation can become useful work that survives interruption. Then build Home, Image Lab and personal continuity on that working chain.

Jacob's external ChatGPT/Codex/Claude workflow remains the primary engineering environment. Improve its shared instructions and handoffs immediately. Builder is an optional execution lane inside Kitty; its broken scheduled launch remains off until current admission and dry selection are proven.

This replaces the former memory-first rollout and supersedes the September 10 visualization-folder drafts `kitty-companion-product-plan.md` and `kitty-feature-rollout-plan.md`. Their useful companion ideas remain candidates after the first value checkpoint. This is a delivery program, not a claim that Kitty is built or accepted.

## What the return should feel like

Jacob opens Kitty and sees one useful next action with an honest account of what was checked. He resumes a project without reconstructing its history, asks for a bounded result, approves it, and can leave. When he returns, the result opens directly, its current status agrees with the conversation, and he can reuse it in the next request. A failure preserves the request, progress and recovery action. An unavailable source is explained quietly and accurately.

The first proof uses a small repository change or generated text artifact, because that can exercise the whole chain without image-provider spending. The later image journey reuses the already selected character anchors and existing Image Lab plan. Visual polish, responsive layout, feedback and keyboard behavior are acceptance requirements within each slice, not a final coat of paint.

## Why keep Kitty

The working hypothesis is **personal continuity with less coordination**: durable project context, inspectable memory, safe follow-through and reusable results across tasks and devices. Generic chat, retrieval and coding are already available elsewhere. Kitty earns continued work only when connecting these capabilities reduces Jacob's effort enough to justify operating it.

The first implementation checkpoint compares three representative jobs against Jacob's current tools: resume a project after an interruption; request and recover a bounded result; find and reuse a past result. Record completion, manual handoffs/copying, elapsed time, recovery success, incremental spend and provenance errors. Use the same task inputs and constraints. Proposed continuation gate: all three complete without a truth/privacy failure, at least two need fewer manual handoffs, and added latency/maintenance is explained by a concrete benefit. Jacob's willingness to use it still matters; metrics cannot declare delight.

If it misses, allow one bounded repair of the observed failure. If it still misses, shrink Kitty to the valuable continuity/actions layer and use an external app for commodity features. A full replacement requires evidence of equivalent data ownership, recovery, integrations and lower total operating burden; no replacement or abandonment is justified by this planning review alone.

## Delivery order and owners

The lead selects one ready packet at a time for overlapping code. Different non-overlapping outcomes can have different visible leads. These are role assignments for dispatch, not claims that workers are currently running.

| Order | Packet / accountable role | Concrete result and dependency |
|---|---|---|
| Now, independent | **WF-1 — external workflow maintainer** | Mirror the concise execution contract into the tools Jacob uses; prove a handoff between two tools. No Kitty runtime dependency. |
| 1 | **R-1 — recovery integrator** | Reconcile #848/#846/#845 and preserved `f9a12bce`; obtain one reviewable candidate with truthful runtime/Work and project reentry. Preserve all source branches. |
| 2 | **R-2 — result/lifecycle integrator** | Persist the reviewed result before worktree cleanup; bind it to existing ArtifactStore identity, Work preview, Library reuse and Chat return. Depends on R-1's reconciled contracts. |
| 3 | **R-3 — product acceptance operator + independent reviewer** | Run Chat → reviewed Mission → Work → real result → Library → Chat on the exact candidate, then interrupt/recover/reload it. Includes current admission/launch proof if unattended Builder is exercised. |
| Checkpoint | **Lead, with Jacob's actual use** | Run the three-job comparison above. Continue, narrow, adopt a component or repair based on observed burden. Do not automatically activate more packets. |
| 4 | **R-4 — Home/Chat integrator** | Home/project reentry and shared actions reuse the accepted chain. Implement the reviewed Chat voice lifecycle and qualified quiet-state rules. |
| 5 | **R-5 — Image/Library integrator** | Activate IMAGE-001 within existing approval/spend rules; implement the reviewed fidelity plan and cross-surface reuse. Library availability never depends on indexing success. |
| 6 | **R-6 — companion/release integrator** | Add only continuity, memory, capture and automation behavior that wins the checkpoint; finish exposed primary journeys and accepted secondary jobs against the roadmap release gate. |

Full prompts, allowed scope, dependencies and stop rules are in [dispatch](kitty-return-program/dispatch.md). The [lane ledger](kitty-return-program/lane-ledger.md) is the preservation and salvage map. The [evidence record](kitty-return-program/evidence.md) distinguishes current observations from inherited results.

Useful side lanes: P2 paid-review dispatch repair; #849 development-loop repair with #850 test identity reconciliation; the bounded remainder of the backend audit. They may run independently only with non-overlapping ownership. P2 is a prerequisite for any path that could dispatch a paid Mission review. #849 is not a reason to block product work that can use the existing correct checks. The incomplete backend audit blocks resurrection of uncertain legacy capabilities, not the already understood result-artifact seam.

## Decisions that close the planning contradictions

- **Preserve before integrate.** Canonical `feat/builder-001-frontend-gaps@f9a12bce` is clean and pushed, but its bypassed verification does not make it accepted. Compare semantic behavior, salvage focused changes in a fresh-main worktree, and retain the original. Do not redo the already completed dirty-file archive or queue pausing.
- **Work completion is outcome evidence.** Worker exit, task completion, review, result registration and initiative rollup must agree. A saved patch is a reusable artifact; it is not evidence that the patch was merged or deployed.
- **One owner per object.** Mission owns reviewed intent; Builder owns execution; Chat presents continuity; Home orients; Work projects Builder evidence; ArtifactStore owns reusable artifact identity; Image Lab owns character/session/job semantics. No universal-object store or extra status machine.
- **Voice retention is deliberate.** Stage raw audio durably through the existing lifecycle; default cleanup follows successful transcription and durable turn persistence. Long-term raw retention needs an explicit retain choice. Implement visible staging/failure state, bounded expiry for failed staging, sensitivity rules and deletion behavior. Do not silently place every recording in Library or create another audio store.
- **Quiet is scoped to evidence.** The first Home slice says what checked sources show, and names an unavailable Calendar source when relevant. It must never infer global “nothing needs you” from an error collapsed to an empty list. A narrow owner-returned Calendar result (`ok/events/error`) is the follow-on when global quiet is needed.
- **Reuse the reviewed work.** Work/Library design gates are clear; Chat/Home corrections are deltas. Generic MCP exposure stays out of Chat v1. Add a narrow existing adapter only for an accepted user journey.
- **No automatic paid review.** A budget ceiling is not permission for a new paid call. Paid authorization must bind the exact reviewed content and be checked where the network dispatch occurs. A CLI launch failure before submission releases the reservation.

## Build, adopt or use another app

| Option | Decision now | Evidence needed to change it |
|---|---|---|
| Existing ChatGPT + desktop/GitHub tools | Default external engineering route for bounded work with local access. Use existing included capacity. | Actual inability to access files, run validation, recover context or finish within the selected session. |
| Existing Kitty owners plus small adapters | Chosen product route for the first vertical; it preserves existing state and reviewed work. | Compare task success, recovery, latency, maintenance and manual coordination at the checkpoint. |
| LibreChat | Candidate for a commodity chat/tool surface or external companion benchmark; do not wholesale transplant it now. Its repository provides agents, tools and artifacts under MIT. [Project](https://github.com/danny-avila/LibreChat), [license](https://github.com/danny-avila/LibreChat/blob/main/LICENSE). | A pinned-version trial proves import/export, owner-state boundaries, recovery and lower maintenance than the small integration. No trial has run. |
| AnythingLLM | Candidate benchmark for document ingestion/retrieval, not a replacement personal truth store. Repository is MIT. [Project](https://github.com/Mintplex-Labs/anything-llm), [license](https://github.com/Mintplex-Labs/anything-llm/blob/master/LICENSE). | Same documents and failures, measured retrieval usefulness, local-data controls and full exit/export path. No trial has run. |
| Open WebUI | Possible external app; not the current canonical Kitty frontend. Current licensing includes branding conditions and a small internal-use exception; personal use is not categorically prohibited. [Official license explanation](https://docs.openwebui.com/license/). | Review the pinned license and dependencies for the intended use, then demonstrate an owner-state migration and native-journey parity before proposing architectural replacement. |

Do not install every candidate. Run one small comparison only when the first vertical exposes a concrete expensive gap. Adoption must remove maintenance, not add another synchronization boundary. No new orchestration plugin or general Agent Launcher is justified by the evidence gathered here.

## Unattended operation

**Current state: not ready to restart.** The launch job points at a deleted runtime directory; core Kitty listeners were absent. The DB doctor passed mechanically, and five stale initiatives were already paused. Neither fact proves scheduled execution is safe.

Before scheduled launching: preserve the known DB backup; inspect the supported current admission/initiative projection; prove dry selection chooses only the specifically admitted current work (or nothing); reconcile the preserved scheduler candidate; bind launcher cwd/repo/data root to one validated candidate; check provider readiness before claiming a task; then exercise one bounded run plus interruption/recovery. Do not use a real scheduler tick as a “dry run.” If the candidate offers no side-effect-free selection entry point, add/test that seam before activation.

Once those gates and task-specific authorization are satisfied, unattended workers may inspect, edit in their own worktrees, run bounded checks, commit, and push their own approved task branches/open draft PRs. This records Jacob's existing task-branch publication authorization; it grants no main push, merge, history rewrite, data deletion, credential/environment change, new paid spend or external message authority. Creating or editing external deliverables still follows their specific authorization.

Stop the packet after two failed repair/review cycles, exhausted included capacity, an unresolved collision, ambiguous external-effect completion, or a required approval. Persist exact state and the recovery command; do not rotate endlessly through models or duplicate a possibly completed action. Review remains independent. Do not enable ready-state/paid PR review automation without the required spend authorization.

## Scope cuts and completion

Keep retired launchers/queues and unsafe auto-rearm paths retired. Defer council/expert/profile machinery unless it improves a measured task. Do not reactivate every historical packet or expose every backend module. Video/audio-generation/training expansion and public distribution are outside this first program slice.

The program is delivered when its lane dispositions, first dispatches, authority corrections and formal reader review are recorded against the exact repository candidate. Product completion is separate: the running journeys, recovery, responsive/degraded states and actual-use checkpoint must pass. See [outcome contract](kitty-return-program/outcome-contract.md).
