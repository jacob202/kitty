# KTF-001 reliability reconciliation

**Prepared:** 2026-07-29 (the filename is fixed by the approved R1 manifest)
**Scope:** evidence reconciliation only. No Builder state, manifest, task, Git
branch, remote, or GitHub state was mutated.

## Decision

Do **not** replay any original KTF task. The Outcome 6 source change is on
current `main`, but the original task records are terminal and no supported
evidence proves the required daylight run or life-project resume loop. The
remaining reliability delta is an evidence/recovery delta, not a justified
source-code change.

R2 must therefore author fresh manifests with new initiative IDs. They must
exercise the current code from a controlled current-main checkout, capture the
required supported evidence, and stop if the runtime behavior differs from the
source contract below. A fresh code-remediation packet is justified only if
that controlled proof produces a failing repro.

## Authorities and collection boundary

| Question | Authority inspected | Evidence |
| --- | --- | --- |
| Current delivery commit | `origin/main` remote ref | `git ls-remote origin refs/heads/main` returned `23d0af1bb52407fe1dc1ffdb972d7d9279c18dde`. |
| Source behavior at that commit | Git object at the inspected SHA | `git show 23d0af1:gateway/builder_loop.py`, `gateway/builder_run.py`, and `tests/test_builder_run.py`. |
| Merge/publication history | GitHub | `env -u GITHUB_TOKEN gh pr list --state all ...`; PRs #261, #262, #263, #279, #280, and #295 are merged. |
| Task, attempt, lease, and derived packet state | Canonical checkout Builder database | `./kitty builder initiative doctor --json`, then `./kitty builder initiative status <id> --json` and `attempts <id> --json` from `~/Projects/kitty`. |
| Manifest mutability | Source at the inspected SHA | `gateway/builder_initiative.py:689-735`: changed contents under an existing initiative ID raise `InitiativeConflictError` without mutation. |

The canonical Builder database is
`~/Projects/kitty/data/kittybuilder/builder_queue.db`. The commands above were
run from that canonical checkout, not from this isolated documentation
worktree.

## Current-main source contract

`f9dfb6a8134c9926943f750b2541fffd84bc3400`
(`feat(builder): KTF-003 Outcome 6 — continue after exhaustion +
provider-exit-75`) is an ancestor of the inspected `main` SHA (the
`git merge-base --is-ancestor` exit status was `0`).

The current source establishes these implementation claims:

- `gateway/builder_loop.py:67-68` names `LOOP_PROVIDER_EXHAUSTED` and exit
  code `75`.
- `gateway/builder_loop.py:135-181` records provider exhaustion as a crashed
  attempt, records an infrastructure failure that does not consume budget, and
  releases a blocked task with the durable reason
  `provider_exhausted_resumable_pause`.
- `gateway/builder_run.py:500-531` records the provider-exhausted decision,
  pauses the initiative with a resumable reason, and returns a paused result.
- `gateway/builder_run.py:568-591` records
  `continued_after_packet_failure` and continues to unrelated eligible work;
  dependencies remain ineligible.
- `tests/test_builder_run.py:446` contains
  `test_exhausted_packet_does_not_stop_unrelated_packet`.

This is source and test-coverage evidence, **not** a claim that a current
daylight run was performed. No test, provider call, or Builder run was started
for this reconciliation because none was authorized by `/qg` or the
operator-gated R3 packet.

## Builder state reconciliation

`initiative doctor` lists the original KTF rows as stored `active` initiatives.
That is not a green execution result. The implementation intentionally
distinguishes operator-stored initiative state from `initiative status`'s
read-only derived state (`gateway/builder_initiative.py:939+`). The supported
derived projections below are the controlling packet outcomes.

| Original initiative / packet | Supported task and attempt evidence | Disposition |
| --- | --- | --- |
| `ktf-001-free-exec-v1` / `KTF-FE-01-roadmap-authority-contract` | Task `kb_ms2h4hla_349e` is `done`; attempt 54 succeeded; review approved; PR #279 merged. | **Landed.** Do not duplicate. |
| `ktf-001-free-exec-v1` / `KTF-FE-02-daylight-proof-checkpoint` | Task `kb_ms2h4hlc_dd16` is `cancelled`; attempts 55 and 56 failed; no review or PR; derived initiative state is failed/exhausted with `needs_decision`. | **Superseded.** Its unsatisfied daylight checkpoint remains required, but this literal task cannot supply it. |
| `ktf-002-acceptance-prose-v1` / `KTF-FE-03-acceptance-prose-honesty` | Task `kb_ms2h4hy3_534a` is `done`; attempt 57 succeeded; review approved; PR #280 merged. | **Landed.** Do not duplicate. |
| `ktf-003-outcome6-runtime-v1` / `KTF-FE-04-continue-unrelated-after-failure` | Task `kb_ms2eqymk_3e6c` is `cancelled`; attempts 50 failed and 51 crashed; one infrastructure failure; no review or PR. Its intended source behavior is present via `f9dfb6a`. | **Superseded.** The code is on main, while this immutable task's delivery record is not proof of it. |
| `ktf-003-outcome6-runtime-v1` / `KTF-FE-05-provider-exhaustion-pause` | Task `kb_ms2eqyml_f104` is `cancelled`; it has no attempts, review, or PR. Its intended source behavior is present via `f9dfb6a`. | **Superseded.** A fresh provider-exhaustion proof is still required. |
| `ktf-003-daylight-exhaustion-proof` / `EXHAUSTION-PROOF-PACKET` | Task `kb_ms2i8s9o_4b27` is `cancelled`; attempt 58 crashed and attempt 59 succeeded; one infrastructure failure; no review or PR. | **Superseded.** It does not prove a reviewed, published, resumed daylight result. |

The old task IDs cannot be edited into a replacement: an identical manifest
may only be reapplied unchanged, while changed contents under the same
initiative ID fail loudly with `InitiativeConflictError`. The required recovery
mechanism is a new initiative ID, never task replay or direct database repair.

## GitHub reconciliation

- PR #261 merged at `deb04eeb3afdb82e8806532a4a047196bb6c1bc6`.
- PR #262 merged at `bc65c3eae534670ec934947536a9c166ecf598df`.
- PR #263 merged at `18a66f54430e482f6b2701af0ed2746465ecee3a`.
- The two completed original packets are represented by merged PR #279
  (`a45f16158c43eee5a658f76ede73fc9a2d822e5f`) and PR #280
  (`d071598f646b2e38efc90b991d5c4eab08dd29f6`).
- PR #295 merged at the inspected `main` SHA and its post-merge workflow was
  recorded as successful in the KTF checkpoint. That supports repository CI
  health; it does not replace a daylight Builder evidence run.

## Remaining reliability delta

1. **Current-source runtime proof:** no supported run record shows the current
   `main` implementation continuing unrelated eligible work after a failed
   packet and then safely pausing/resuming after an exit-75 provider exhaustion.
   A source inspection and a unit-test anchor are insufficient for the Mission
   acceptance contract.
2. **Fresh immutable packet contracts:** the records that attempted this work
   are terminal. R2 must use new initiative IDs and must not quote or rely on
   their stale literal-edit anchors.
3. **Independent validation/review/publication evidence:** the old Outcome 6
   and daylight tasks have no approved review or merged PR. A successful worker
   result alone is not completion evidence.
4. **Free-exec packet standard:** KTF-FE-01 landed but KTF-FE-02 did not.
   R2 must preserve the Mission requirement for at least two falsifiable
   free-exec packet contracts; it must not invent a code change merely to make
   a gate fail.
5. **Life-project resume loop:** no evidence in these original KTF records
   selects a real life project, delivers its next action, records its outcome,
   and exposes the next action.

## Required shape for R2 and R3

R2 should author only the minimum fresh contracts demonstrated by this delta:

1. A controlled current-main reliability-proof packet that proves both
   unrelated-work continuation and the exit-75 provider-exhaustion lifecycle
   against an isolated Builder database, with an explicit failure report if
   either observation differs from the source contract.
2. An operator-gated daylight packet that requires the applied fresh IDs,
   independent review, Builder run/task/attempt/lease/validation/review
   receipts, Git/GitHub reconciliation, and an explicit resumable-pause
   observation before it may claim success.
3. A separately scoped real-life-project resume-loop packet. It may not begin
   until the daylight evidence is complete. If no real code delta is found,
   its value is the durable outcome and next-action record, not manufactured
   implementation work.

If the controlled proof exposes a source defect, stop the proof, preserve its
receipts, and author a narrow remediation manifest with a falsifiable
pre-change gate. Do not repair the old initiative in place.

## Exact next action

Run **KTF-R2-fresh-proof-packet-authoring**: use this report to author the
fresh, narrowly scoped manifest(s), validate their structure only, and leave
Builder unapplied. R3 remains operator-gated until those manifests receive an
independent review and are applied from the canonical checkout.
