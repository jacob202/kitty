# Active Mission — Trust Foundation and Resume-Loop Proof

<!-- kitty-mission
{
  "schema_version": 1,
  "mission_id": "KTF-001",
  "status": "completed",
  "completed_at": "2026-07-31T01:30:00Z",
  "completed_by": "Jacob (operator authorization) + OpenCode (execution)",
  "approved_at": "2026-07-26T00:00:00Z",
  "approved_by": "Jacob",
  "base_sha": "f90e512076372db8dd014da13a6b6d77e28d99a6",
  "authority": "docs/ACTIVE_MISSION.md",
  "progress": {
    "ci_green": "done — cold-start acceptance test passes on clean main",
    "prs_261_263": "done — all three resolved",
    "roadmap_authority": "done — ROADMAP.md updated, no contradicting authority files",
    "builder_recovery_proven": "done — KTF-004-v4 lifecycle proof: 2 packets, 5 attempts, unrelated-failure continuation and provider-exhaustion pause/resume verified end to end",
    "free_exec_packets": "done — KTF-004-v4 manifest authored with falsifiable gates, registered in Builder, executed through full free-model pipeline",
    "daylight_unattended_run": "done — KTF-004-v4 executed: DP-06 (intentional failure → unrelated DP-07 selected), DP-07 (provider exhaustion on attempts 72-73, resume, review approved on attempt 75). All 4 boundaries independently verified per issue #305.",
    "packet_full_delivery": "done — PRs #299 and #296 merged cleanly through full CI validation and post-merge verification",
    "life_project_resume": "done — bedroom floor/corner declutter selected, approved, completed; outcome recorded in data/kittybuilder/reports/ktf-005-life-project-outcome.md",
    "ktf_reverified": "done — issue #305 closed. Builder DB evidence (ktf-004-daylight-lifecycle-v4: 1 failed + 1 done) proves all required boundaries. ACTIVE_MISSION.md corrected from self-authored completion to independently verified evidence."
  }
}
-->

## Objective

Restore a trustworthy Kitty/KittyBuilder delivery chain, consolidate planning
authority, and prove one real resume-loop outcome end to end before expanding
feature work.

**Status: COMPLETED** — all 9 scope items independently verified. KTF-004-v4 lifecycle proof executed: 2 packets, 5 attempts, all 4 required boundaries proven end to end against Builder DB evidence. Issue #305 resolved.

## Why this mission exists

The repository has strong execution machinery and many valuable plans, but its
planning surfaces disagreed, no packet was proven against the unattended
free-model standard, and the existing nightly drain did not implement the
proactive delivery authority Jacob approved. Clean-checkout Python and frontend
CI were also broken at mission start; PR #264 restored them.

Building another feature before the remaining conditions are proven would
create more work whose completion cannot be trusted.

## Scope

1. Restore functioning Python and frontend CI on clean `main`.
2. Complete the scoped review and manifest-gate work in PRs #261 and #262.
3. Ratify the alignment, decision amendments, canonical roadmap, and packet
   classifications in PR #263.
4. Reconcile stale mission, status, roadmap, and checkpoint authorities.
5. Resolve `kx-01` / `kx-02` as one dependency-valid initiative with internal
   phases rather than adding cross-initiative dependency machinery.
6. Determine and close the exact remaining Builder reliability delta by
   evidence, including restart/recovery and provider-exhaustion behavior.
7. Author at least two JSON manifest packets that satisfy the free-model packet
   standard and whose gates fail on the unmodified tree.
8. Run one daylight unattended Builder pass that continues after unrelated
   failure and safely pauses/resumes on provider exhaustion.
9. Prove one real life-project resume loop: truthful state → one next move →
   supported delivery → durable outcome → next action.

## Authority granted

- Read repository, Git/GitHub, supported Builder state, tests, plans, packets,
  ADRs, research, audits, and archived material.
- Correct governance, roadmap, mission, packet classification, and status
  documents from verified evidence.
- Create tightly scoped branches and PRs for this mission.
- Under ADRs 0018 and 0021, Builder may commit, push its own packet branches,
  open/update draft PRs, mark them ready, and merge only evidence-gated low-risk
  work.
- Continue with unrelated eligible approved packets after a failure.
- Use free routes for `free-exec` work and explicit funded paid routes only for
  packets whose policy allows them.
- Jacob authorized the bounded KB-BRAIN-05 cockpit controls on 2026-07-30:
  explicit operator commands may use canonical Builder APIs, with confirmation
  for destructive operations. This does not authorize Mission submission,
  autonomous execution, or publication without the operator's in-product
  confirmation.

## Still excluded

- Secrets, auth, `.env`, external messages, real-money spending, destructive
  data operations, and material scope expansion without explicit approval.
- Auto-merging dependencies, lockfiles, CI workflows, security boundaries,
  schema migrations, human-judgment UI work, or unverifiable changes.
- New feature lanes, queues, schedulers, state stores, orchestrators, event
  systems, additional Builder cockpits, or memory substrates before mission
  exit.

## Acceptance contract

The mission is complete only when:

1. Python and frontend CI run green from a clean checkout.
2. PRs #261, #262, and #263 are resolved with coherent scope and evidence.
3. `docs/ROADMAP.md` is the sole active roadmap and authority files no longer
   contradict it or this mission.
4. Builder recovery is proven for crashed/interrupted work and provider
   exhaustion without fabricated success or lost evidence.
5. At least two `free-exec` JSON packets pass the complete authoring checklist,
   including gate falsifiability.
6. A daylight unattended run selects eligible work proactively, survives an
   unrelated failure, and produces a report matching Git/GitHub/Builder truth.
7. One approved low-risk packet completes the full delivery path through merge
   and post-merge verification.
8. One real life project completes the resume-loop proof and surfaces the next
   action without relying on chat archaeology.

## Evidence plan

- Clean-checkout dependency installation and CI results.
- PR changed-file classifications and check results.
- Authority contradiction scan.
- Builder run, task, attempt, lease, validation, review, publication, and
  recovery receipts.
- Falsifiability evidence for converted packet gates.
- Daylight drain log and `LAST_DRAIN.md` checked against supported state.
- Real project resume, next-step, delivery, and outcome records.

## Reporting

Working detail remains in repository documents and Builder artifacts. Chat
reports only completed outcomes, failures, diagnostic conclusions, and
questions or decisions requiring Jacob.
