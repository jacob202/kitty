# Active Mission — Kitty Recovery

**Mission ID:** KITTY-RECOVERY-001
**Status:** Running
**Approved by:** Jacob on 2026-08-29
**Base SHA:** `e2b7a061e87b159f535e37b021d9c6a2955647c4`
**Spend ceiling:** CAD 6.00 per week, enforced by `config/compute_governor.json`
**Last reconciled against live evidence:** 2026-09-14

<!-- kitty-mission
{
  "schema_version": 1,
  "mission_id": "KITTY-RECOVERY-001",
  "status": "running",
  "approved_at": "2026-08-29T23:00:00-06:00",
  "approved_by": "Jacob",
  "base_sha": "e2b7a061e87b159f535e37b021d9c6a2955647c4",
  "authority": "docs/ACTIVE_MISSION.md",
  "deadline": null,
  "budget_cad": 6
}
-->

Supersedes KPROOF-001, whose proof window ended 2026-08-18 without a durable
pass verdict. That file's history is preserved in git; nothing here retroactively
satisfies it.

**This file is the single control surface.** It carries the one sequence, the
real status of each step, and the evidence for that status. `docs/ROADMAP.md`
defines what "done" looks like in the long run; it is not a second queue.
Everything under `docs/plans/`, `docs/packets/`, `docs/initiatives/`,
`docs/phases/` and `docs/superpowers/` is candidate evidence and never activates
work by existing. Agents update *this* file rather than writing a new plan.

## Objective

Turn Kitty from an accumulation of partially connected subsystems into a
coherent product Jacob would voluntarily use. He must be able to ask for
meaningful work, approve a bounded outcome, watch progress, ask questions,
recover from failure, and get a real result.

## Acceptance Contract

The mission is complete when an independent reviewer completes the key journeys
at desktop and iPhone-class widths with no contradictory status, dead primary
controls, raw server errors, clipped dialogs, or horizontal overflow
(ACCEPT-001). Every preceding sequence item — REC-001 through HOME-001 — must be
verified in the running product, not in its implementation evidence.

## The rule that governs every surface

Every surface must be actionable in place. Information Jacob cannot act on right
there is a defect, not a feature. On Work he must be able to do work — retry,
unblock, resume, cancel, create, plan. The same holds for Image Lab, Library,
Automations, and Home. An item with genuinely no available action must say so in
plain language and say why. Recorded in `config/PREFERENCES.md` 2026-08-29.

## One sequence — naming reconciled 2026-09-14

The mission steps and the return program's R-chain were **two names for the same
work** and produced repeated re-derivation. They are merged here. The R-labels
are kept only because open PRs and GAR handoffs reference them.

| Step | Also known as | Status | Evidence |
|---|---|---|---|
| **REC-001** — one trustworthy baseline | — | **Partially done** | Build provenance is provable: `kitty status` reports `build source == HEAD`, `freshness checkout-current`, gateway-truth PASS (verified 2026-09-14). Every build path now records its own source revision — `npm run build` chains `gateway/kitty-chat/scripts/stamp-source-sha.mjs`, stamping the commit on a clean tree and `dirty:<sha>` otherwise, so no build can leave provenance `unknown` (2026-09-14). Self-healing on a *stale* build is still not implemented; it reports truthfully and waits for a human. |
| **WORK-001** — repair Work | R-1 | **Done on main** | PR #852 / `8ba172ad` — truthful resume and route state. |
| **RESULT-001** — durable results reach Work and Library | R-2 | **Done on main** | PR #855 / `12d49e39` — reuse durable Builder results. |
| **BUILDER-001** — chat → packet → result | **R-3** | **Blocked; never driven** | PR #870 open at `2417f82a`, all 12 checks green, blocked on **6 unresolved reviewer threads** (4×P1 + 1×P2 on `gateway/mission_runtime.py`, 1×P1 on `gateway/routes/missions.py`, 1×P1 on the acceptance test). The end-to-end journey has **never been run** — see `~/kb/handoffs/2026-09-13-kitty-r3-acceptance-record.md`: "the bounded product journey has NOT been run." |
| **VALUE-001** — is Kitty worth operating? | return-program checkpoint | **Not started; gates everything below** | Three representative jobs vs Jacob's current tools: resume a project after interruption, request and recover a bounded result, find and reuse a past result. Continue / narrow / shrink decision. |
| **HOME-001** — repair Home and Chat | R-4 | **Not started** | No commit on `origin/main` references it. |
| **IMAGE-001 + LIBRARY-001** | R-5 | **Not started** | Screens pre-date the mission. Image Lab planning is complete and parked at `~/kb/handoffs/2026-09-09-image-lab-character-fidelity-planning-closeout.md`. |
| **AUTO-001 + companion** | R-6 | **Not started** | — |
| **ACCEPT-001** — integrated acceptance | roadmap Phase 6 | **Not started** | Independent reviewer completes the key journeys at desktop and iPhone-class widths with no contradictory status, dead primary controls, raw server errors, clipped dialogs, or horizontal overflow. |

**Merging PR #870 is not BUILDER-001.** Driving the journey is. Implementation
evidence is not user-outcome completion.

Driving it was also impossible until 2026-09-14: PR #870 built the trusted local
acceptance boundary (`record_running_product_acceptance`) but nothing could call
it — no command, no route, only tests. `kitty accept status | template | record`
now exists on `fix/r3-acceptance-operator-20260914`, stacked on #870. Jacob's
live database also has no `missions` table at all, which is the plainest
available proof that the Mission control plane has never run against real data.

## Built but switched off — 2026-09-14

Four things are complete, correct, and not running. This is the current
highest-leverage work because none of it is construction.

| Thing | Where | Why it is off |
|---|---|---|
| ~~Local reviewer~~ **on 2026-09-14** | `gateway/local_review.py:107`; model on disk at `~/Library/Application Support/Kitty/models/local-reviewer/` | `KITTYBUILDER_LOCAL_REVIEW_SHADOW=1` is now set in `.env` (gitignored, which is why greps for it still report zero files). It stays non-authoritative: `advisory_clear|escalate` only, fails closed. **It has produced no data yet** — shadow verdicts are written during Builder review, and Builder has not run since 2026-09-01. Measurement is blocked on the scheduler row below, not on the reviewer. |
| Builder's scheduler | `~/Library/LaunchAgents/com.kitty.builder.supervisor.plist` | **Plist repaired 2026-09-15** from the canonical renderer (`python -m gateway.builder_supervisor launchd-plist`); `contract_matches` is now true and a real tick ran through `scripts/start_builder_supervisor.sh`, launching nothing (`no_eligible_packet`). **Armed 2026-09-15 02:26** — `launchd` reports `loaded`, `healthy`, `LastExitStatus 0`; first unattended tick scanned 8 initiatives and launched 0. Note there were **two** independent causes, not one: besides the bad path, the service was also explicitly `disabled` in the launchd user domain, which the plist repair alone would not have fixed (`launchctl enable gui/501/...`). The drift is now caught by `kitty doctor` (`builder:scheduler`), which is why it hid for two weeks. |
| ~~Session cost analytics~~ **plugged 2026-09-14** | `scripts/kb_effectiveness.py` | `record` now reads the session's real token total from its own Claude Code transcript, and `summary --join-transcript-costs` answers the same question for history without rewriting the hash chain. Sessions with known total tokens went 0 → 2 for the last 30 days (354,094,076 tokens); every future receipt carries the number automatically. |
| Agent-room briefing | GAR-AWARE-02, on main | Built; the room is drowned by 797 status/claim messages against 213 handoffs in 14 days, and only 8 of 363 handoffs ever drew a reply from a different agent. **Narrowed 2026-09-15:** `list_inbox(attention_only=True)` keeps everything addressed to you plus broadcast prompts/handoffs/reviews and drops ambient status/result broadcast — measured 263 → 121 rows for `chatgpt`, 500 → 258 for `claude`. Projection only: no new store, nothing deleted, `room_recent` still sees everything. |

**The scheduler alone will not drive R-3.** Measured 2026-09-15 against the
live supervisor projection: 8 initiatives are *stored* `active`, but **zero
derive to `active`** (derived: 63 paused, 12 failed, 10 completed), and no
initiative has an eligible packet. `KITTY-RECOVERY-001-BUILDER-001-V1` through
`V6` are all `paused` with `eligible_packets: []`. So a repaired, armed
scheduler ticks every 15 minutes and correctly launches nothing. Driving
BUILDER-001 needs an initiative that *derives* active with an eligible packet —
a deliberate decision, not a side effect of fixing the LaunchAgent.

**The empty runway is deliberate, not a defect** (checked 2026-09-15). All 12
queued tasks belong to initiatives that are *stored* `paused`, and
`derive_initiative_state` short-circuits on stored-paused before anything else
(`gateway/builder_initiative.py:1364`). Every one of those pauses carries an
explicit reason, and most forbid exactly the thing an armed scheduler would do:

| Initiative | Pause reason (abridged) |
|---|---|
| `KITTY-RECOVERY-001-BUILDER-001-V6` | implemented directly at `2dde1f66`; "preserve V6 history, **do not relaunch stale packets**" |
| `kitty-hardening-gar-scoped-continuity-20260903` | already merged (PR #865); "must stay paused so side-effects" don't replay |
| `kitty-hardening-runtime-truth-20260903-v1` | "equivalent outcome shipped externally in merged PR #827; stale Builder duplicate" |
| `kitty-opens-the-doors-20260831-v1` | "not authorized for unattended dispatch" |
| `kitty-opens-the-doors-20260831-v5` | "preserved shadow result must be revalidated before any new dispatch" |
| `one-kitty-phase1-action-grammar-20260902` | "hold pending explicit" authorization |
| `kitty-autonomy-runway-20260901-v2` | "hold from unattended dispatch until explicitly re-authorized" |
| `KITTY-UNATTENDED-PROOF-20260831` | "superseded before first run: validator warned the path could never pass" |

The stored-vs-derived gap (8 → 0) is benign bookkeeping, not a demotion bug:
3 of the 8 stored-active initiatives have every packet `done` and simply never
had their stored state written back to `completed`; 4 have genuinely failed
packets; 1 has no eligible work.

**So driving BUILDER-001 means authoring a fresh packet against current HEAD —
not unpausing anything.** Unpausing `V6` would not even produce work
(`eligible_packets()` returns `[]`), and unpausing the others would replay
already-merged work against a tree that has moved on.

Builder's queue is **not** a mess and does not need cleaning: 214 of its 264
cancelled tasks were cancelled on 2026-09-01 as a deliberate curation, and
`cancelled`/`paused` are the retirement states. The live queue is 12 queued /
6 blocked / 1 failed.

## Standing constraints

- Gateway is product truth; KittyBuilder is the execution control plane; native
  `gateway/kitty-chat` is the canonical product surface.
- Reuse the existing memory, work, artifact, action, session, and provider
  systems. Do not build a parallel model registry, queue, artifact store, or
  frontend state machine to make the UI easier.
- Builder may run unattended on its schedule. **Jacob authorized publication on
  2026-09-16**: each succeeded packet may push its own branch and open its own
  pull request, parked at `awaiting_review`. That authorization stops there.
  Builder may not merge, provision paid infrastructure, or alter credentials,
  and the ADR 0018 / ADR 0021 evidence-gated auto-merge capability remains
  unused by unattended dispatch. Opening a pull request is how the work becomes
  visible; merging it stays a human decision. As of 2026-09-17 the per-packet
  publish path is **not implemented end-to-end**: `initiative run-packet` does
  not accept `--publish`, the run path does not attach the task final report
  `publish_task` requires, and unattended dispatch therefore runs shadow-mode
  until that wiring lands.
- User-facing copy carries no packet IDs, ports, env vars, raw HTTP status,
  stack traces, or internal service names.
- Pending, skipped, stale, or self-authored review evidence is unverified.
- Before committing, set `KITTY_AGENT_PARTICIPANT` and hold a coordination
  claim. The default participant is `chatgpt`, so an unset variable commits
  under the wrong identity.
