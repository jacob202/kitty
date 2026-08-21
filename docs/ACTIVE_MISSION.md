# Active Mission — Two-Week Builder Proof

**Mission ID:** KPROOF-001  
**Status:** Failed — verdict rendered 2026-08-21  
**Verdict:** [`docs/proof/KPROOF-001-VERDICT.md`](proof/KPROOF-001-VERDICT.md)  
**Approved by:** Jacob on 2026-08-04  
**Proof window:** 2026-08-04 through 2026-08-18  
**Budget ceiling:** $25 CAD (spend unverified — Builder's ledger is local-only)  
**Base SHA:** `b3f68aae84525f980d44db8d7b9e6d728457b0db`

<!-- kitty-mission
{
  "schema_version": 1,
  "mission_id": "KPROOF-001",
  "status": "failed",
  "approved_at": "2026-08-04T18:27:00-06:00",
  "approved_by": "Jacob",
  "base_sha": "b3f68aae84525f980d44db8d7b9e6d728457b0db",
  "authority": "docs/ACTIVE_MISSION.md",
  "deadline": "2026-08-18",
  "budget_cad": 25,
  "verdict": "failed",
  "verdict_at": "2026-08-21",
  "verdict_evidence": "docs/proof/KPROOF-001-VERDICT.md"
}
-->

## Verdict — 2026-08-21

KPROOF-001 **failed** its acceptance contract. The scored evidence is in
[`docs/proof/KPROOF-001-VERDICT.md`](proof/KPROOF-001-VERDICT.md).

In short: Builder did merge four real, tested, reviewed pull requests, so the
execution plane works. But the loop this mission specified was never run —
nothing went from a conversation, through an approved contract, into the
launched application, past an independent review, through a recovery test. The
one deliberate end-to-end attempt (2026-08-17) stopped five steps into twelve.
Of 53 pull requests merged during the proof window, 4 were Builder's; every one
of those was merged by hand.

The failure condition below prescribes a pause. Executing or overriding that
pause is Jacob's decision. Everything the mission requires preserved is
preserved; nothing is to be deleted on the strength of this verdict.

## Objective

Take one real software request from conversation to a working, verified feature,
with KittyBuilder carrying the execution and without Jacob manually coordinating
agents. Everything below bounds that single objective: the proof runs to
2026-08-18 under a $25 CAD ceiling, and Kitty continues only if it lands.

## Decision to prove

Can Kitty provide a genuinely better way to take a software request from conversation to a working, verified feature without Jacob manually coordinating the agents?

Kitty continues only as this bounded proof. The proof is not authorization to build the full vision.

## Phase 1 — Evidence-driven audit

Inspect the running application, Builder's actual execution path, working integrations, dead or unwired UI, GitHub history and issues, and repair-versus-replacement options. Separate direct evidence from inference and unknowns.

The audit must produce:

- what demonstrably works;
- what only appears to work;
- what should be preserved;
- what should be repaired or replaced;
- the smallest two-week implementation sequence;
- a tiny webpage prototype of the proposed conversation-and-progress experience.

No repository rebuild or broad implementation begins during the audit.

## Phase 2 — Experience test

The prototype must show:

- a polished Kitty conversation;
- decisive guidance about the next move;
- relevant personal and project context;
- visible Builder progress beside the conversation;
- the ability to question or redirect work while it runs;
- a plain statement of what is happening now and what comes next.

It passes only if Jacob genuinely prefers the experience to opening ChatGPT or Claude directly for the same project task.

## Phase 3 — One real Builder loop

Use one currently dead interaction in the Build Work area and complete this loop:

1. Jacob discusses the broken interaction with Kitty.
2. Kitty helps define the desired outcome.
3. Jacob approves the result contract.
4. Builder creates a durable job.
5. Builder chooses an available capable model.
6. Context survives model or provider changes.
7. Builder edits the code.
8. Builder launches the real application.
9. Builder exercises the feature end to end.
10. A second model reviews the implementation and result.
11. Builder repairs remaining defects.
12. Kitty reports completion only after the interaction works in the running product.

Jacob must be able to continue chatting with Kitty and ask what it is doing, why, and what comes next.

## Non-negotiable rules

- Runtime behavior outranks documentation, tests, commits, and agent claims.
- Existing working code comes first; Git history and evidence come second.
- Architecture may change only when evidence supports it.
- Models are replaceable workers. Provider or usage exhaustion must not erase the job or its context.
- Ask before exceeding the proof budget, deleting anything, sending messages, publishing, or changing account or security settings.
- Jacob may steer and answer meaningful questions, but manual agent coordination counts as proof failure.
- Do not add image generation, broad computer control, deep memory, elaborate routing, another agent framework, or a major redesign during this mission.

## Acceptance Contract

The pass and failure conditions below are the mission's contract: the pass
condition decides whether Kitty continues, and the failure condition decides what
happens to the work if it does not.

## Pass condition

By 2026-08-18:

- Builder completes one real feature loop;
- the result works in the launched application;
- the experience is pleasant, fast, clear, and understandable;
- Jacob would voluntarily choose Kitty over direct ChatGPT or Claude for the next project task.

## Failure condition

Pause Kitty for several months if Builder still requires constant supervision, the interface remains frustrating, or Jacob still prefers direct tools.

Preserve working integrations, repository history, the prototype, audit, and findings. Use existing AI tools separately until the technology or Jacob's capacity changes enough to justify another attempt.

## Product boundary

The central product is a personal AI operator that understands the project, recommends the next move, visibly carries the work through to a functioning result, and keeps going when individual models or sessions fail.

Everything else must earn its place by helping that loop work.
