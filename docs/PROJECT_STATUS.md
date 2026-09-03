# Project Status

**Historical repository evidence in this file:** through `main` `7badd7e1b08dfc49cf1c0dc3ae3a7f75eed42fa2`, plus product-surface branch `d8a8e8282e9650579561a7cadef4d861a6e396a7` and its 2026-08-19 restored-Mac live verification. **Planning state was re-reconciled on 2026-09-03 against `main` `610d86c7665bfdd9cb4c7dd84178493b9b1ec015`: `KITTY-RECOVERY-001` is the running broad Mission and `docs/ROADMAP.md` is the living personal release-quality guide.** Unmerged branch behavior is not described as shipped on `main`.

The full commit references above are standard 40-character SHA-1 object names. They were re-verified with `git rev-parse` on 2026-08-19 after an automated review incorrectly described them as 41 characters.

This file is a dated evidence summary, not a live runtime dashboard. Use Git/GitHub for repository state, supported probes for local services, and Builder's supported database/API/CLI for execution state.

## Architecture reference

Current system shape and component boundaries live in `docs/ARCHITECTURE.md`; this dated status file does not restate or override them. Product-surface supersession is preserved in ADR 0039 and the Constitution amendment history.

## Authority correction

`docs/ROADMAP.md` and this status file were reconciled on 2026-08-04 for the earlier trustworthy-daily-driver mission. Later, commit `89057bb23f4ed9195e6d198d883c80d5a8a14764` explicitly replaced that mission with **KPROOF-001 — Two-Week Builder Proof**. The active mission was therefore newer than the roadmap/status that still described the superseded execution order.

KPROOF-001 reached its 2026-08-18 deadline without a durable record satisfying the full pass condition. On 2026-08-19 its mission record is reconciled to `superseded`: it no longer gates individually approved work, but it is **not** retroactively marked passed and does not activate the blocked M1–M6 sequence.

## What's shipped

- `docs/ACTIVE_MISSION.md` records `KITTY-RECOVERY-001` as the running broad Mission. KPROOF-001 remains historical/superseded evidence and is not retroactively marked passed.
- `docs/proof/TWO_WEEK_PROOF_AUDIT.md` completed the source/history audit far enough to choose the first proving seam; it still requires live Mac runtime evidence before claiming the seam works.
- Builder has durable queue/runtime/recovery machinery and a bounded runtime projection; recent merged work also made `needs_decision` pause the initiative truthfully rather than continuing execution.
- #437 merged the Builder action trust repair: `useBuilderAction()` now converts an HTTP-success `{ok:false}` payload into a mutation error, refreshes the runtime-manifest query rather than `['runtime']`, and surfaces the action result. It merged without repository CI, and its recorded evidence is mocked/local UI behavior — so it must not yet be described as the completed KPROOF control seam.
- #442 removed Dependabot version updates, cancels superseded PR runs, and aligned `make ci` to the `Tests` workflow's exact commands and coverage gate.
- #444 recorded the out-of-band gate verification while Actions was unavailable.
- **The GitHub Actions outage ended on 2026-08-10 between 23:03Z and 23:20Z.** From 2026-08-06 until then, jobs were assigned no runner and failed within 3–13 seconds on every branch and event type — an account billing/spending state, not a code result, so red checks from that window carry no information. `Tests` runs now take 200–314 seconds and execute for real. Out-of-band verification is retired; CI is the gate again. Evidence: [`audit/MAIN_GATE_VERIFICATION_2026-08-10.md`](audit/MAIN_GATE_VERIFICATION_2026-08-10.md), which supersedes the 2026-08-09 receipt.
- **`main` at `d54fd896` was red on `lint` and `typecheck`** — both in `mcp/builder/context.py`, added by the KittyBuilder MCP bridge as a direct-to-`main` squash with no green check. Independently confirmed out of band, and fixed in #453 along with a third failure in `gateway/image_quality.py`. #453 also added `scripts/hooks/pre-push`, a local gate for exactly this class of failure.
- Historical status text below this line may name older `main` SHAs; current repository truth must always be read from Git rather than inferred from this evidence summary.

## Planning context captured 2026-09-03

`docs/ACTIVE_MISSION.md` now records **KITTY-RECOVERY-001 — Kitty Recovery** as the running broad Mission, approved 2026-08-29. Its objective is to turn the partially connected subsystems into a coherent product Jacob voluntarily uses, with actionable primary surfaces and independent running-product acceptance. KPROOF-001 remains historical/superseded evidence and is not retroactively marked passed.

On 2026-09-03 Jacob clarified the forward target: **public-release quality for his own Kitty, not preparation for public distribution**. `docs/ROADMAP.md` carries that living, reviewable sequence. It explicitly parks distribution-only work such as generic-user packaging/legal/multi-user/public-release infrastructure while keeping runtime trust, security, backup/restore, mobile access, reliability, complete features, accessibility and polish in scope.

Packet/spec existence does not activate execution. Current Builder/GAR/#490 ownership and fresh runtime/Git evidence still decide what can run next. `ROADMAP_V2.md` remains historical/superseded target detail; its Open WebUI-primary M1/M2 sequence is not executable current priority.

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
- GitHub ruleset `20193076` (`Main required checks — no bypass`) is active on the default branch and requires `policy-gate` plus `merge-gate`, with review-thread resolution. It does **not** require the branch to be up to date before merge (`strict_required_status_checks_policy=false`), so documentation and operators must not describe strict-up-to-date protection as platform-enforced. #453's pre-push hook remains an additional local guard.
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
