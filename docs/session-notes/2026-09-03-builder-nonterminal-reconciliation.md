# Builder nonterminal reconciliation — 2026-09-03

Authority basis: live supported `./kitty builder initiative list/show` and `./kitty builder queue list/show` projections at `origin/main` `6aa79cf543bb1d4875041b1ac0f1e2da5e6a6799`, reconciled against `PC-BUILDER` and `DEFECTS-rc0.md`.

Classification vocabulary: `CURRENT`, `ABSORBED`, `SUPERSEDED`, `HISTORICAL`, `RECOVERY REQUIRED`. Classification does not itself authorize dispatch.

## Nonterminal initiatives

| Initiative | Builder state | Classification | Reason |
|---|---|---|---|
| `reasoning-backend-v1` | failed | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `cp08-campaign-a` | failed | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `kitty-endgame-init-1-builder-closeout-v1` | failed | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `kitty-endgame-init-1-builder-closeout-v2` | failed | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `kx-06-proactive-feed-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `kittybuilder-brain-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `ktf-003-outcome6-runtime-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `ktf-001-free-exec-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `ktf-002-acceptance-prose-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `ktf-003-daylight-exhaustion-proof` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `uifix-labels-2026-07-27-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `uifix-labels-2026-07-27-v2` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `ktf-004-daylight-proof-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `ktf-004-daylight-evidence-v2` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `ktf-004-daylight-lifecycle-v3` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `ktf-004-daylight-lifecycle-v4` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `phase1-smoke-recovery` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `phase1-1-recovery-proof-20260801-184814` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `ktl-002-measured-learning-boundary-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `trustworthy-kittybuilder-b2-b10-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `KPROOF-001` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `KPROOF-RETRY-001` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `KPROOF-FINAL-001` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `KPROOF-FINAL-002` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `KPROOF-CLEAN-001` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `KPROOF-CLEAN-002` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `KPROOF-CLEAN-003` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `KPROOF-PAID-004` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `KPROOF-PAID-005` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `KPROOF-PAID-006` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `KPROOF-VERSION-007` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `kitty-campaign-work-projection-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `kitty-campaign-codex-staging-scope-fix-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `kitty-campaign-codex-staging-reuse-fix-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `kitty-campaign-codex-staging-reuse-fix-v2` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `kitty-campaign-codex-staging-reuse-fix-v3` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `kitty-campaign-work-projection-v2` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `kitty-campaign-work-projection-v3` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `WORK-SPINE-001` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `WORK-SPINE-002` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `WORK-SPINE-003` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `WORK-SPINE-004` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `WORK-SPINE-004-LEAD-HARDEN` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `WORK-SPINE-005` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `CONSOLE-WORK-001` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `CONSOLE-WORK-002` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `autonomous-campaign-supervisor-v1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `autonomous-campaign-supervisor-v3` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `PUBLIC-GOLDEN-PATH-001` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `builder-cheap-hardening-20260816-v2` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `builder-cheap-hardening-20260816-v3` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `builder-cheap-hardening-20260816-v4` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `builder-cheap-hardening-20260816-v5` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001. |
| `KITTY-RECOVERY-001-BUILDER-001-V1` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001-BUILDER-001-V2. |
| `KITTY-RECOVERY-001-BUILDER-001-V2` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001-BUILDER-001-V3. |
| `KITTY-RECOVERY-001-BUILDER-001-V3` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001-BUILDER-001-V4. |
| `KITTY-RECOVERY-001-BUILDER-001-V4` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001-BUILDER-001-V5. |
| `KITTY-RECOVERY-001-BUILDER-001-V5` | paused | **SUPERSEDED** | Explicitly superseded by KITTY-RECOVERY-001-BUILDER-001-V6. |
| `KITTY-RECOVERY-001-BUILDER-001-V6` | paused | **ABSORBED** | Requirements folded into PC-BUILDER; initiative itself says preserve history and do not relaunch stale packets. |
| `KITTY-UNATTENDED-PROOF-20260831` | paused | **HISTORICAL** | Old unattended marker proof; not part of the current user journey. |
| `KITTY-UNATTENDED-PROOF-20260831-V2` | active | **HISTORICAL** | Retry of old unattended marker proof; not current product acceptance. |
| `kitty-finish-truth-20260831-v1` | active | **ABSORBED** | Restore/truth requirements retained under current recovery; this old campaign is not independent authority. |
| `kitty-finish-truth-20260831-v2` | active | **ABSORBED** | Restore/truth requirements retained under current recovery; this old campaign is not independent authority. |
| `KITTY-BUILDER-E2E-REVIEWFIX-20260831` | paused | **HISTORICAL** | Old reviewer canary, not current journey authority. |
| `kitty-opens-the-doors-20260831-v1` | active | **ABSORBED** | Home requirement deferred to later surface contract; no independent execution now. |
| `kitty-opens-the-doors-20260831-v2` | active | **ABSORBED** | Requirements preserved as later product inputs; no independent execution now. |
| `kitty-opens-the-doors-20260831-v3` | active | **ABSORBED** | Requirements preserved as later product inputs; no independent execution now. |
| `kitty-opens-the-doors-20260831-v4` | active | **ABSORBED** | Image Lab requirement deferred until PC-BUILDER passes once. |
| `kitty-opens-the-doors-20260831-v5` | active | **ABSORBED** | Builder event-copy requirement may contribute to PC-BUILDER; old campaign is not parent authority. |
| `kitty-opens-the-doors-20260831-v6` | active | **ABSORBED** | Undo/todo requirements deferred to later product work; no independent execution now. |
| `kitty-autonomy-runway-20260901-v2` | active | **RECOVERY REQUIRED** | Mixed backend tasks are not proven current; KT-RESTORE requirement is valid but latest packet warns its fence may be under-scoped. |
| `one-kitty-phase1-action-grammar-20260902` | active | **CURRENT** | OK-ACTION-02 may contribute to PC-BUILDER action/approval behavior but cannot close the contract. |

## Nonterminal tasks

| Task | Builder state | Parent | Classification | Reason |
|---|---|---|---|---|
| `kb_mtgwncgf_0f2e` / `UNATTENDED-PROOF-proto` | blocked | `KITTY-UNATTENDED-PROOF-20260831-V2` | **HISTORICAL** | Old unattended proof marker retry; no current product outcome. |
| `kb_mtiwmpcz_fe93` / `KF-HEALTH-PARSER-01` | blocked | `kitty-autonomy-runway-20260901-v2` | **RECOVERY REQUIRED** | Failed provider-health parser run; current need not established by PC-BUILDER evidence. |
| `kb_mtiwmpd0_2a6c` / `KF-AUTONOMY-STATE-01` | blocked | `kitty-autonomy-runway-20260901-v2` | **RECOVERY REQUIRED** | Exhausted autonomy-state test task; current need not established by PC-BUILDER evidence. |
| `kb_mth2nezq_9339` / `KT-RESTORE-01` | blocked | `kitty-finish-truth-20260831-v1` | **SUPERSEDED** | Older KT-RESTORE-01 attempt superseded by later v2/recovered packet evidence. |
| `kb_mth5wuo2_a5f0` / `KT-RESTORE-01` | blocked | `kitty-finish-truth-20260831-v2` | **SUPERSEDED** | Older KT-RESTORE-01 shadow-run attempt; later recovered packet carries the requirement forward. |
| `kb_mtgatvyi_340e` / `BUILDER-PREFLIGHT-proto` | blocked | `KITTY-RECOVERY-001-BUILDER-001-V6` | **ABSORBED** | Preflight/cost requirement belongs to PC-BUILDER, but V6 explicitly says do not relaunch stale packets. |
| `kb_mtgwkxjb_4315` / `UNATTENDED-PROOF-doc` | queued | `KITTY-UNATTENDED-PROOF-20260831` | **HISTORICAL** | Old unattended proof marker; no current product outcome. |
| `kb_mtiwmpd0_d968` / `KF-INGESTION-QUEUE-01` | queued | `kitty-autonomy-runway-20260901-v2` | **RECOVERY REQUIRED** | Backend reliability task may still be valid but is not bound to current PC-BUILDER evidence. |
| `kb_mtiwmpd0_9a31` / `KF-CALENDAR-INT-01` | queued | `kitty-autonomy-runway-20260901-v2` | **RECOVERY REQUIRED** | Calendar integration test task is not bound to the current Builder contract. |
| `kb_mtiwmpd0_cc12` / `KF-ASYNC-FEEDBACK-01` | queued | `kitty-autonomy-runway-20260901-v2` | **RECOVERY REQUIRED** | Async-feedback test task is not bound to the current Builder contract. |
| `kb_mtiwmpd0_792d` / `KT-RESTORE-01` | queued | `kitty-autonomy-runway-20260901-v2` | **RECOVERY REQUIRED** | KT-RESTORE-01 requirement remains valid for release trust, but the task itself warns its current fence may be under-scoped and requires current-main revalidation. |
| `kb_mthq0n1f_6a36` / `KF-GLANCE-01` | queued | `kitty-opens-the-doors-20260831-v1` | **ABSORBED** | Home read-model work is deferred until later surface contract; not current before PC-BUILDER acceptance. |
| `kb_mtjpgr9j_a5f5` / `OK-ACTION-02` | queued | `one-kitty-phase1-action-grammar-20260902` | **CURRENT** | OK-ACTION-02 may contribute to PC-BUILDER approval/action behavior; merge cannot close PC-BUILDER. |
| `kb_mthv7qa8_a9bd` / `KF-COPY-01` | queued | `kitty-opens-the-doors-20260831-v5` | **RECOVERY REQUIRED** | Builder event-copy requirement may contribute to PC-BUILDER, but the old shadow-run result was never integrated and must be revalidated on current main before salvage. |
| `kb_mtgatvym_6bd3` / `BUILDER-COCKPIT-001` | queued | `KITTY-RECOVERY-001-BUILDER-001-V6` | **ABSORBED** | Its missing Work request/proposal requirement is reproduced in DEFECTS-rc0 and now owned by PC-BUILDER; stale V6 task must not be relaunched. |
| `kb_mtgatvym_c782` / `BUILDER-AUTONOMY-001` | queued | `KITTY-RECOVERY-001-BUILDER-001-V6` | **ABSORBED** | Scheduler truth remains useful degraded-mode input, but unattended autonomy is not the first PC-BUILDER acceptance path and V6 says do not relaunch. |

## Binding results

- `PC-BUILDER` is the current parent outcome for Builder request/proposal/approval/progress/recovery/result behavior.
- `BUILDER-COCKPIT-001` requirement is absorbed into PC-BUILDER because rc0 reproduced the missing Work request/proposal path; the stale V6 queue task is not safe to relaunch.
- `OK-ACTION-02` remains CURRENT only as a contributor to shared approval/action behavior; its completion cannot close PC-BUILDER.
- `KT-RESTORE-01` remains a valid release-trust requirement, but the latest recovered queue task is RECOVERY REQUIRED until its scope fence is revalidated on current main.
- `KF-COPY-01` remains potentially useful to PC-BUILDER status copy, but its old shadow-run result requires current-main salvage review rather than automatic execution.
- No other queued/blocked task is authorized to dispatch merely because Builder still marks it eligible.
