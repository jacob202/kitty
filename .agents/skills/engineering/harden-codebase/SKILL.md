---
name: harden-codebase
description: Find robustness and correctness gaps in a codebase — silent failures, swallowed exceptions, invented defaults, hidden unavailability, missing evidence, unhandled edge cases, weak invariants, and observability blind spots. Grounded in Kitty's fail-loud prime directive in AGENTS.md. Use when the user wants to harden code, make failures loud, audit error handling, find where the system fails quietly, improve reliability or observability, or check data integrity. The complement to improve-codebase-architecture: that skill shapes modules; this one makes them behave and fail correctly at runtime.
---

# Harden Codebase

Surface **robustness gaps** — places where the system fails quietly, guesses instead
of erroring, hides unavailable evidence, or breaks an invariant without saying so.
The aim is fail-loud behaviour and trustworthy evidence, per the AGENTS.md prime
directive. This is the sister to `improve-codebase-architecture`: that skill asks
*is the module shaped well?*; this one asks *does it behave and fail correctly?*

## Glossary

Use these terms exactly in every suggestion. Consistent language is the point —
don't drift into "error handling," "robustness," or "resilience." The canonical
definitions live in [LANGUAGE.md](LANGUAGE.md), injected below; the "Key
principles" summary follows.

!`cat "${COMMANDCODE_SKILL_DIR}/LANGUAGE.md"`

Key principles (see LANGUAGE.md for full definitions):

- **The fail-loud test**: trace every failure path. Does it raise a clear cause, or
  does it swallow, default, hide, or silently recover? Quiet failure is the defect.
- **The evidence test**: when this breaks at 2am, what does the operator see? If the
  answer is "nothing" or "a generic 500," the evidence is missing.
- **A default is a guess. A guess is a lie with extra steps.** Prefer an error that
  names the cause over a fallback that papers over it.
- **Invariants are checked at the seam, not hoped for.** If a condition must always
  hold, something must enforce it and fail when it doesn't.

This skill is _informed_ by the project's doctrine. Kitty's AGENTS.md prime
directive and its ADRs record what "correct failure" means here; don't re-litigate
accepted decisions.

## Kitty grounding (read first)

Before exploring, read:

| Doc | Purpose |
|-----|---------|
| `AGENTS.md` | The prime directive: "Fail loud. Raise errors with clear causes. Do not swallow exceptions, invent defaults, hide unavailable evidence, or add silent recovery." |
| `docs/ARCHITECTURE.md` | Live stack, ports, package layout — where the failure surfaces live |
| `gateway/doctor.py` | The existing health/preflight surface — what Kitty already checks |
| `docs/research/ktf-001-reliability-reconciliation-2026-07-30.md` | Recorded reliability findings and reconciliation doctrine |
| `docs/adr/` | Accepted decisions — treat as load-bearing unless Jacob changes them |

**Domain vocabulary:** use names from `gateway/` — e.g. `run_workspace` fail-closed
wrapping, `image_runner` health probes, the `lifespan` reconciliation passes,
`describe_chain_exhaustion` — not generic "the error handler."

**Recorded decisions:** `docs/DECISIONS.md` indexes accepted ADRs and
`docs/AUTHORITY_MAP.md` resolves conflicts. When a new rejection deserves
permanence, offer an ADR using [ADR-FORMAT.md](ADR-FORMAT.md) (shared with the
architecture skill at `../improve-codebase-architecture/ADR-FORMAT.md`).

## Failure modes to avoid

- **Parroting the directive.** Don't just quote "fail loud" — walk the code and find
  the specific `except: pass`, the invented default, the swallowed status.
- **Hardening the happy path.** The defect is in the failure path. If a function only
  ever succeeds, there's nothing to harden.
- **Adding defensive noise.** Don't wrap correct internal calls in try/except for
  scenarios that can't happen. Harden at boundaries (user input, external APIs,
  I/O, concurrency), not everywhere.
- **Confusing recovery with hiding.** A visible retry-with-warning is legitimate
  recovery. A silent default that hides unavailability is the defect. Know the
  difference (AGENTS.md draws it explicitly).
- **Speculative invariants.** Assert only conditions that must actually hold for
  correctness, not every imaginable precondition.

## Process

<scope_check>
If the user names ≤2 specific files or asks about one function/class, skip the
Task-tool exploration phase. Read the named files directly and move to the grilling
loop.
</scope_check>

### 1. Explore

Read the Kitty grounding docs above, then walk the codebase. Use the Task tool
(`subagent_type=explore`, or `general` for multi-step work) for broad exploration
only when the scope is large. Hunt for quiet failure:

- Where does an `except` swallow, log-and-continue, or return a default instead of
  raising?
- Where is unavailable evidence hidden — a missing value rendered as empty/zero/None
  with no signal that it's unknown vs. genuinely absent?
- Where does the system invent a default instead of erroring (a guessed path, a
  fallback model, a synthetic success)?
- Where can an invariant be violated without anything noticing (a partial write, a
  stale lease, a race, a corrupt record)?
- Where would a 2am failure leave the operator with no evidence — no log, no status,
  a generic error with no cause?
- Where do edge cases (empty, partial, concurrent, timeout, malformed) fall through
  to behaviour nobody decided on?

Apply the **fail-loud test** to anything you suspect: trace the failure path end to
end. A path that ends in a swallow, a guess, or silence is the signal you want.

### 2. Present candidates

Present a numbered list of hardening opportunities. For each candidate:

- **Files** — which files/modules are involved
- **Failure path** — the exact condition that goes wrong, traced concretely
- **Current behaviour** — what happens today (swallow / default / hide / silent
  recovery / no evidence)
- **Loud behaviour** — what should happen instead (raise with cause, surface
  unavailability, emit evidence, enforce the invariant)
- **Blast radius** — who/what is affected when this fails quietly, and how often

**Use Kitty domain vocabulary** (from `docs/ARCHITECTURE.md` and `AGENTS.md`) **and
the glossary above.** Talk about "the `run_workspace` fail-closed wrapper" — not
"the error thing," and not "the try/catch."

**Doc conflicts**: if a candidate contradicts an existing ADR or the prime
directive's own carve-outs (visible retry-with-warning is allowed), only surface it
when the friction is real. Mark it clearly. Skip theoretical hardening that accepted
decisions already forbid.

Propose fixes only after the user picks a candidate. Until then, ask: "Which of
these would you like to explore?"

### 3. Grilling loop

Once the user picks a candidate, drop into a grilling conversation. Walk the failure
tree with them — what triggers it, how often, what the loud behaviour should say,
what evidence the operator needs, whether a retry is legitimate recovery or hiding,
what test proves the failure path now fails loudly. For dependency categories and
test strategy when hardening a chosen candidate, see
[DEEPENING.md](../improve-codebase-architecture/DEEPENING.md) (shared) — the seam
discipline applies: a hardening change should concentrate the failure logic at one
seam, not scatter try/except across callers.

Side effects happen inline as decisions crystallize:

- **Naming a new invariant or failure class?** Add a short definition to
  `docs/ARCHITECTURE.md` or a new `docs/CONTEXT.md` using
  [CONTEXT-FORMAT.md](../improve-codebase-architecture/CONTEXT-FORMAT.md) (shared).
- **Sharpening a fuzzy term during the conversation?** Update the relevant doc right
  there.
- **User rejects the candidate with a load-bearing reason?** Offer an ADR at
  `docs/adr/NNNN-title.md`, framed as: _"Want me to record this as an ADR so future
  hardening reviews don't re-suggest it?"_ Only offer when the reason would actually
  be needed by a future explorer. See
  [ADR-FORMAT.md](../improve-codebase-architecture/ADR-FORMAT.md) (shared).
- **The hardening changes a user-facing failure surface?** Hand off to
  `improve-daily-ux` — that skill owns what the user sees when this fails.
