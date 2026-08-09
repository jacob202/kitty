# Project Status

**Repository evidence verified:** 2026-08-09 through `main` `ece1bad0341a7743681a0619e9266b186e8478d8`, plus current GitHub PR/check state.

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

## What's shipped

- `docs/ACTIVE_MISSION.md` defines KPROOF-001 as the one approved active mission: prove one conversation-to-working-feature Builder loop without Jacob manually coordinating workers.
- `docs/proof/TWO_WEEK_PROOF_AUDIT.md` completed the source/history audit far enough to choose the first proving seam; it still requires live Mac runtime evidence before claiming the seam works.
- Builder has durable queue/runtime/recovery machinery and a bounded runtime projection; recent merged work also made `needs_decision` pause the initiative truthfully rather than continuing execution.
- #437 merged the Builder action trust repair: `useBuilderAction()` now converts an HTTP-success `{ok:false}` payload into a mutation error, refreshes the runtime-manifest query rather than `['runtime']`, and surfaces the action result. It merged without repository CI, and its recorded evidence is mocked/local UI behavior — so it must not yet be described as the completed KPROOF control seam.
- #442 removed Dependabot version updates, cancels superseded PR runs, and aligned `make ci` to the `Tests` workflow's exact commands and coverage gate.
- #444 recorded the out-of-band gate verification while Actions is unavailable.
- **Repository CI has run no workflow step since 2026-08-06.** Jobs are assigned no runner and fail within two seconds on every branch and event type — an account billing/spending state, not a code result. Red checks currently carry no information. `main` was instead verified gate-by-gate in a CI-equivalent container; see [`audit/MAIN_GATE_VERIFICATION_2026-08-09.md`](audit/MAIN_GATE_VERIFICATION_2026-08-09.md).
- `main` currently ends at `ece1bad0341a7743681a0619e9266b186e8478d8`.

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
- **Builder investigation:** current local initiatives, packets, attempts, leases, runs, and budgets remain unverified through GitHub;
- that the merged #437 behavior works against the real `/builder/action` path in the running application;
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
