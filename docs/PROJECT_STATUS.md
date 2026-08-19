# Project Status

**Repository evidence verified:** through `main` `7badd7e1b08dfc49cf1c0dc3ae3a7f75eed42fa2`, plus product-surface branch `d8a8e8282e9650579561a7cadef4d861a6e396a7` and its 2026-08-19 restored-Mac live verification. Unmerged branch behavior is not described as shipped on `main`.

This file is a dated evidence summary, not a live runtime dashboard. Use Git/GitHub for repository state, supported probes for local services, and Builder's supported database/API/CLI for execution state.

## Current architecture

- Kitty Gateway is the product authority for conversation behavior, memory/context, projects, tools, Tutor, provider policy, and user-facing workflows.
- **Shell authority is unresolved:** Constitution Article I.2 / ADR 0027 name Open WebUI as primary replaceable shell, while accepted ADR 0039 names the native Kitty frontend canonical. Constitution remains higher authority until explicitly amended; do not execute shell-role migrations from either assumption as if this conflict were settled.
- The native `kitty-chat` surface is live and testable on the product-convergence branch, but that runtime evidence does not itself amend the Constitution.
- KittyBuilder is the separate durable execution/control plane for accepted Missions, packets, workers, attempts, recovery, validation/review, budgets, and evidence.
- Models and coding harnesses are replaceable workers; their narration is not execution truth.

## Authority correction

`docs/ROADMAP.md` and this status file were reconciled on 2026-08-04 for the earlier trustworthy-daily-driver mission. Later, commit `89057bb23f4ed9195e6d198d883c80d5a8a14764` explicitly replaced that mission with **KPROOF-001 — Two-Week Builder Proof**. The active mission was therefore newer than the roadmap/status that still described the superseded execution order.

KPROOF-001 reached its 2026-08-18 deadline without a durable record satisfying the full pass condition. On 2026-08-19 its mission record is reconciled to `superseded`: it no longer gates individually approved work, but it is **not** retroactively marked passed and does not activate the blocked M1–M6 sequence.

## What's shipped

- `docs/ACTIVE_MISSION.md` preserves KPROOF-001 as a terminal/superseded mission record. It does not claim the full pass condition was met and no longer acts as the current scope gate.
- `docs/proof/TWO_WEEK_PROOF_AUDIT.md` completed the source/history audit far enough to choose the first proving seam; it still requires live Mac runtime evidence before claiming the seam works.
- Builder has durable queue/runtime/recovery machinery and a bounded runtime projection; recent merged work also made `needs_decision` pause the initiative truthfully rather than continuing execution.
- #437 merged the Builder action trust repair: `useBuilderAction()` now converts an HTTP-success `{ok:false}` payload into a mutation error, refreshes the runtime-manifest query rather than `['runtime']`, and surfaces the action result. It merged without repository CI, and its recorded evidence is mocked/local UI behavior — so it must not yet be described as the completed KPROOF control seam.
- #442 removed Dependabot version updates, cancels superseded PR runs, and aligned `make ci` to the `Tests` workflow's exact commands and coverage gate.
- #444 recorded the out-of-band gate verification while Actions was unavailable.
- **The GitHub Actions outage ended on 2026-08-10 between 23:03Z and 23:20Z.** From 2026-08-06 until then, jobs were assigned no runner and failed within 3–13 seconds on every branch and event type — an account billing/spending state, not a code result, so red checks from that window carry no information. `Tests` runs now take 200–314 seconds and execute for real. Out-of-band verification is retired; CI is the gate again. Evidence: [`audit/MAIN_GATE_VERIFICATION_2026-08-10.md`](audit/MAIN_GATE_VERIFICATION_2026-08-10.md), which supersedes the 2026-08-09 receipt.
- **`main` at `d54fd896` was red on `lint` and `typecheck`** — both in `mcp/builder/context.py`, added by the KittyBuilder MCP bridge as a direct-to-`main` squash with no green check. Independently confirmed out of band, and fixed in #453 along with a third failure in `gateway/image_quality.py`. #453 also added `scripts/hooks/pre-push`, a local gate for exactly this class of failure.
- `main` currently ends at `6de35bde4da298ca7e1c51401397eda201bf6dcc`, and `Tests` passes on it (run 275s, real execution).

## Active work

There is currently **no running broad Mission** in `docs/ACTIVE_MISSION.md`; KPROOF-001 is a terminal mission record. That absence is intentional and must not be filled by guessing a replacement mission.

Post-deadline work proceeds only where Jacob explicitly approved it and the durable decision/packet is named. The current product-surface convergence and ADR 0040 Image Lab packet chain meet that standard. Their execution does not activate ROADMAP_V2's Open WebUI M1/M2 sequence or any unrelated Builder initiative.

The next broad roadmap activation must first resolve the Constitution/ADR 0039 shell conflict and then be written into `docs/ROADMAP.md`.

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

- Red Actions results dated 2026-08-06 through 2026-08-10 23:03Z came from the runner outage and cannot serve as code-quality evidence. Results after 23:20Z on 2026-08-10 are real and must be read as such.
- Nothing server-side blocks an unchecked merge to `main`: the default-branch ruleset that would require passing checks (issue #399) is still disabled. #453's pre-push hook is a local guard only, so a merge made elsewhere can still land red.
- PR #437 remains historical KPROOF evidence; unresolved proof gaps are not silently promoted to success, but they no longer block separately approved post-deadline work.
- Local Builder/runtime facts remain unavailable from GitHub alone.

## Supported live checks

```bash
./kitty context --agent
./kitty status
./kitty doctor --json
./kitty builder initiative doctor --json
```

Use explicit charge authorization before any verification path that invokes paid providers or GPU compute.
