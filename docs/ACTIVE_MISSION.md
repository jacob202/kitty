# Active Mission — Kitty Recovery

**Mission ID:** KITTY-RECOVERY-001
**Status:** Running
**Approved by:** Jacob on 2026-08-29
**Base SHA:** `e2b7a061e87b159f535e37b021d9c6a2955647c4`
**Spend ceiling:** CAD 6.00 per week, enforced by `config/compute_governor.json`

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

## Objective

Turn Kitty from an accumulation of partially connected subsystems into a
coherent product Jacob would voluntarily use. He must be able to ask for
meaningful work, approve a bounded outcome, watch progress, ask questions,
recover from failure, and get a real result.

## Acceptance Contract

The mission is complete when an independent reviewer completes the key
journeys at desktop and iPhone-class widths with no contradictory status,
dead primary controls, raw server errors, clipped dialogs, or horizontal
overflow (ACCEPT-001). All preceding sequence items (REC-001 through
HOME-001) must be verified in the running product.

## The rule that governs every surface

Every surface must be actionable in place. Information Jacob cannot act on right
there is a defect, not a feature. On Work he must be able to do work — retry,
unblock, resume, cancel, create, plan. The same holds for Image Lab, Library,
Automations, and Home. An item with genuinely no available action must say so in
plain language and say why. Recorded in `config/PREFERENCES.md` 2026-08-29.

## Sequence

1. **REC-001 — one trustworthy baseline.** *Done.* Local `main` reconciled onto
   `origin/main`; the running UI's build source is provable and self-heals when
   it is not.
2. **WORK-001 — repair Work.** *Done.* Every row resolves to a real Builder
   command or a stated reason none exists. A banner reports whether Builder is
   running and what it can actually start.
3. **BUILDER-001 — chat → packet → result.** *Next.* Prove one bounded loop end
   to end in the running product — request, bounded proposal, explicit approval,
   durable packet, worker claim, progress, result — plus one interruption and
   recovery loop. `/builder/conversation/propose` and `/builder/conversation/approve`
   already exist.
4. **IMAGE-001 — make Image Lab honest.** Decision-relevant model, provider, and
   recipe truth without turning the normal workflow into provider jargon.
   Characters need a durable profile a person can understand.
5. **LIBRARY-001 — restore Library value.** Artifacts stay visible when indexing
   is down; saved, indexed, indexing-failed, and content-unavailable read as
   distinct states.
6. **AUTO-001 — repair Automations.** An enabled schedule must not look healthy
   when its heartbeat is stale. Retry must be explicit and safe against duplicate
   external effects.
7. **HOME-001 — repair Home.** Answer what matters now, what Kitty is doing, and
   what Jacob can do next. Remove decorative cards that support no decision.
8. **ACCEPT-001 — integrated acceptance.** An independent reviewer completes the
   key journeys at desktop and iPhone-class widths with no contradictory status,
   dead primary controls, raw server errors, clipped dialogs, or horizontal
   overflow.

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
