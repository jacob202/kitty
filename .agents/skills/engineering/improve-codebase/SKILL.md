---
name: improve-codebase
description: Triage a codebase-improvement request and route it to the right specialist skill. Use when the user says "improve the codebase", "make this better", "what should I fix", "review the quality", "harden this", "clean this up", or any broad code-improvement ask that doesn't name a specific layer. This is the entry point of the improvement family — it decides whether the highest-leverage problem is internal shape (improve-codebase-architecture), runtime failure behaviour (harden-codebase), user-facing experience (improve-daily-ux), or test trustworthiness (verify-by-mutation), then hands off. Use the specialist directly only when the user already named the layer.
when_to_use: improve the codebase, make this better, what should I fix, review the quality, harden this, clean this up
---

# Improve Codebase (Router)

You are the **entry point** of the code-improvement family. Your job is not to fix
anything yourself — it is to **triage** a broad improvement request, find the
highest-leverage problem, and **route** to the specialist that owns it. The four
specialists are siblings; this skill is the switchboard that stops the user having to
know which one to call.

> **Rule:** never do the specialist's work here. Triage, rank, route. If you find
> yourself proposing a concrete refactor / hardening / UX / test fix, you have routed
> too late — hand off to the specialist and let it run its own process.

## The family

| Skill | Layer | Core question | Heuristic |
|-------|-------|---------------|-----------|
| `improve-codebase-architecture` | internal **shape** | Is the module shaped well? | deletion test |
| `harden-codebase` | runtime **behaviour** | Does it fail loud and stay correct? | fail-loud test |
| `improve-daily-ux` | user **surface** | What does the user see and feel daily? | daily-touch test |
| `verify-by-mutation` | test **trustworthiness** | Does the test actually catch the defect? | mutation test |

Each specialist has its own `LANGUAGE.md` glossary, grounding docs, failure modes,
and explore→candidates→grilling process. **Do not duplicate their vocabulary here** —
route to them and let them speak in their own terms.

## When to use the router vs. a specialist

- **Router (this skill):** the request is broad or layer-ambiguous — "improve this,"
  "what's worth fixing," "review the quality," "make it better," "clean this up."
- **Specialist directly:** the user already named the layer — "harden the error
  handling," "the empty states are confusing," "is this test real," "this module is
  too shallow." Skip the router; activate the named specialist.

If the user named a layer but the triage shows the highest-leverage problem is
elsewhere, say so and offer to re-route — don't silently obey the wrong layer.

## Process

### 1. Scope the request

Restate what the user actually wants in one sentence. If the scope is the whole
codebase, narrow it: ask which subsystem, or pick the one with the most recent
churn / most open defects / most user-facing surface, and say which you chose and why.

<scope_check>
If the user already named ≤2 files or one subsystem, triage just that — don't boil
the ocean. If they named a layer, skip straight to the handoff (step 4).
</scope_check>

### 2. Triage across the four layers

Walk the in-scope code once, looking for the **highest-leverage problem in each
layer**. You are scanning to route, not to fix — spend minutes, not hours. For each
layer, note at most the top 1–2 candidates:

- **Shape** (`improve-codebase-architecture`): shallow modules, pass-throughs,
  scattered logic, tight coupling, poor locality, hard-to-test interfaces.
- **Behaviour** (`harden-codebase`): swallowed exceptions, invented defaults, hidden
  unavailability, unenforced invariants, missing evidence, unhandled edge cases,
  **dependency/supply-chain quiet failure** (unpinned deps, ghost packages, version
  drift — see the dependency note below).
- **Surface** (`improve-daily-ux`): state-coverage gaps, optimistic lies, dead-end
  copy, missing feedback, no recovery affordance, divergent state vocabulary.
- **Trustworthiness** (`verify-by-mutation`): smoke assertions that might pass
  vacuously, regression tests that wouldn't catch the regression, coverage without
  kills.

Use the Task tool (`subagent_type=explore`, or `general` for multi-step) for the scan
when scope is large. Read the Kitty grounding docs the specialists name — don't
re-derive them here.

### 3. Rank by leverage

Rank the triaged candidates with one consistent question per layer:

> **leverage = (how often is this hit?) × (what does it cost when it's wrong?) ÷
> (how big is the fix?)**

- A quiet failure on a hot path (`harden`) usually outranks a shallow module on a
  cold one (`architecture`).
- A daily-touch UX gap on the main screen (`daily-ux`) usually outranks a polish item
  on a rarely-visited one.
- A vacuous smoke test guarding a critical path (`verify-by-mutation`) can outrank
  everything — it means you have *no* evidence the others are safe.

Present the ranked list. Be honest about which layer each candidate is in and why it
ranks where it does. Surface evidence gaps as gaps.

### 4. Route and hand off

Recommend the **top-ranked candidate's specialist** as the next move. State plainly:
"This is a `<layer>` problem — activating `<specialist>`." Then activate that skill
and let it run its own explore→candidates→grilling process from step 1. Do not carry
your triage notes into the specialist as conclusions — they are leads, not verdicts;
the specialist verifies against the live code.

If the user picks a different candidate, route to *that* candidate's specialist
instead. The user chooses; you route.

### 5. Cross-pollinate

Findings cross layers. When a specialist's work implies another layer, name the
handoff explicitly:

- A **hardening** fix that changes what the user sees on failure → `improve-daily-ux`
  owns making the loud failure honest and actionable.
- A **daily-ux** fix that needs the backend to surface a cause it currently swallows
  → `harden-codebase` owns making the failure loud first.
- An **architecture** refactor that changes the test surface → `verify-by-mutation`
  proves the new interface's tests are real.
- A **verify-by-mutation** finding that a test can't be mutated cleanly because the
  code is untestable through its interface → `improve-codebase-architecture`.
- Any candidate whose rejection deserves permanence → the relevant specialist offers
  an ADR (shared `ADR-FORMAT.md`).

Record the handoff so the next session sees the thread. Don't let a cross-layer
finding die in chat prose.

## Dependency / supply-chain note

Dependency hygiene is **not a fifth sibling** — it is a facet of `harden-codebase`.
An unpinned dep is a silent-upgrade quiet failure; a ghost package (declared, never
imported) is hidden evidence; version drift across sub-requirements is an unenforced
invariant. When triage surfaces a dependency problem, route it to `harden-codebase`
and name the specific quiet-failure framing. See that skill's `LANGUAGE.md` →
"Dependency boundary" for the vocabulary.

## Failure modes to avoid

- **Doing the specialist's work here.** The router triages and routes. If you're
  proposing concrete fixes, you've routed too late.
- **Boiling the ocean.** Triage is a scan, not an audit. Cap candidates per layer;
  rank; route to the top one. The specialist goes deep on what you routed.
- **Silently obeying a mis-named layer.** If the user said "harden" but the leverage
  is in UX, say so and offer to re-route.
- **Re-deriving grounding.** The specialists already name the docs to read. Don't
  duplicate their reading list or their vocabulary here.
- **Vague routing.** "Maybe look at the architecture" is not a route. Name the
  specialist, name the candidate, activate it.
