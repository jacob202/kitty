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
| Local reviewer | `gateway/local_review.py:107`; model on disk at `~/Library/Application Support/Kitty/models/local-reviewer/` | Gated behind `KITTYBUILDER_LOCAL_REVIEW_SHADOW`, set in zero files. Timeouts already fixed by PR #869. |
| Builder's scheduler | `~/Library/LaunchAgents/com.kitty.builder.supervisor.plist` | `WorkingDirectory` and `ProgramArguments[1]` point at `~/Projects/kitty-autonomy-runtime`, which does not exist. Not loaded. Last ran 2026-09-01. |
| ~~Session cost analytics~~ **plugged 2026-09-14** | `scripts/kb_effectiveness.py` | `record` now reads the session's real token total from its own Claude Code transcript, and `summary --join-transcript-costs` answers the same question for history without rewriting the hash chain. Sessions with known total tokens went 0 → 2 for the last 30 days (354,094,076 tokens); every future receipt carries the number automatically. |
| Agent-room briefing | GAR-AWARE-02, on main | Built; the room is drowned by 797 status/claim messages against 213 handoffs in 14 days, and only 8 of 363 handoffs ever drew a reply from a different agent. |

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
- Builder may run unattended on its schedule. It may not push, open a PR, merge,
  provision paid infrastructure, or alter credentials without Jacob's explicit
  approval.
- User-facing copy carries no packet IDs, ports, env vars, raw HTTP status,
  stack traces, or internal service names.
- Pending, skipped, stale, or self-authored review evidence is unverified.
- Before committing, set `KITTY_AGENT_PARTICIPANT` and hold a coordination
  claim. The default participant is `chatgpt`, so an unset variable commits
  under the wrong identity.
