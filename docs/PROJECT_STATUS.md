# Project Status

**Repository evidence verified:** 2026-08-08 through `main` `574899d64dbc5f27af4140d7c2d33222b1e3f248`, plus current GitHub PR/check state inspected during this reconciliation.

This file is a dated evidence summary, not a live runtime dashboard. Use Git/GitHub for repository state, supported probes for local services, and Builder's supported database/API/CLI for execution state.

## Current architecture

- Kitty Gateway is the product authority for conversation behavior, memory/context, projects, tools, Tutor, provider policy, and user-facing workflows.
- Open WebUI is the accepted replaceable local daily-driver shell under ADR 0027.
- The custom `kitty-chat` client remains a loopback-only fallback and development surface.
- KittyBuilder is the separate durable execution/control plane for accepted Missions, packets, workers, attempts, recovery, validation/review, budgets, and evidence.
- Models and coding harnesses are replaceable workers; their narration is not execution truth.

## Authority correction

`docs/ROADMAP.md` and this status file were reconciled on 2026-08-04 for the earlier trustworthy-daily-driver mission. Later, commit `89057bb23f4ed9195e6d198d883c80d5a8a14764` explicitly replaced that mission with **KPROOF-001 — Two-Week Builder Proof**. The active mission was therefore newer than the roadmap/status that still described the superseded execution order.

The current authority is now explicit: KPROOF-001 gates broader roadmap work until its 2026-08-18 verdict.

## What is verified in the repository

- `docs/ACTIVE_MISSION.md` defines KPROOF-001 as the one approved active mission: prove one conversation-to-working-feature Builder loop without Jacob manually coordinating workers.
- `docs/proof/TWO_WEEK_PROOF_AUDIT.md` completed the source/history audit far enough to choose the first proving seam; it still requires live Mac runtime evidence before claiming the seam works.
- Builder has durable queue/runtime/recovery machinery and a bounded runtime projection; recent merged work also made `needs_decision` pause the initiative truthfully rather than continuing execution.
- Current `main` still has the Builder action trust defect identified by the proof audit: `useBuilderAction()` does not reject an HTTP-success payload with `{ok:false}`, and it invalidates `['runtime']` instead of the runtime-manifest cache used by the Builder surface.
- PR #437 is a candidate repair for that defect. Its patch converts `{ok:false}` into a mutation error, refreshes the runtime-manifest query, and adds visible action result feedback.
- PR #437 has **not** passed repository CI. The GitHub Actions jobs did not reach a runner: GitHub recorded that they were not started because account payments failed or the Actions spending limit needs to be increased. That is an infrastructure/billing blocker, not a passing or failing code result.
- PR #437 also lacks independent running-app acceptance on its current head. Its recorded evidence is mocked/local UI behavior, so it must not be described as the completed KPROOF control seam.
- `main` currently ends at `574899d64dbc5f27af4140d7c2d33222b1e3f248`; recent maintenance includes the mypy cleanup and removal of the completed one-time RunPod diagnostic workflow.

## Active work

The one approved mission is [`ACTIVE_MISSION.md`](ACTIVE_MISSION.md): **KPROOF-001 — Two-Week Builder Proof**.

Current order:

1. establish the live Mac baseline through supported context/status/doctor/Builder projections;
2. verify the chosen Builder action failure/recovery seam against the running application;
3. repair or replace the #437 candidate only from current evidence, with a regression test for false-success handling;
4. prove conversation → approved durable job;
5. complete one real Builder feature loop with launched-app validation and independent review;
6. prove interruption/provider recovery;
7. make the continue-or-pause verdict by 2026-08-18.

No broader frontend, image, memory, agent-framework, or orchestration work is current execution unless it is strictly required by that proof.

## Known unknowns

Repository and GitHub evidence do not prove:

- Jacob's current local checkout/worktree state;
- current Gateway, LiteLLM, Open WebUI, `kitty-chat`, or launchd state on the Mac;
- current credentials, quotas, or provider availability;
- current local Builder initiatives, packets, attempts, leases, runs, or budgets;
- that PR #437 works against the real `/builder/action` path in the running application;
- that an approved conversation can currently create a durable Builder job without manual translation;
- that Builder context survives a real worker/provider interruption end to end.

Unknown is not success and must not be presented as failure without evidence.

## Current blockers and trust gaps

- GitHub Actions runners are blocked by the account billing/spending state, so red Actions results from affected runs cannot currently serve as code-quality evidence.
- PR #437 needs a current-base regression test and real running-app acceptance before it can satisfy the KPROOF seam.
- The committed `.claude/STATE.md` / `.claude/HANDOFF.md` still describe the already-merged Open WebUI session and therefore do not represent the current KPROOF execution checkpoint; this reconciliation invalidates that inherited handoff rather than treating it as current work.
- Local Builder/runtime facts remain unavailable from GitHub alone.

## Supported live checks

```bash
./kitty context --agent
./kitty status
./kitty doctor --json
./kitty builder initiative doctor --json
```

Use explicit charge authorization before any verification path that invokes paid providers or GPU compute.
