# Language

Shared vocabulary for every suggestion this skill makes. Use these terms exactly —
don't substitute "error handling," "robustness," or "resilience." Consistent
language is the whole point.

## Terms

**Failure path**
Any branch of execution taken when something goes wrong — a raised exception, an
error return, a timeout, a missing value, a violated precondition. Deliberately
scale-agnostic: applies to a single `except` clause or a whole reconciliation pass.
_Avoid_: error case, unhappy path (too vague about where the path ends).

**Fail loud**
A failure path that surfaces its cause: raises with context, returns an explicit
error, or emits evidence an operator can act on. The opposite of quiet failure.
_Avoid_: crash (implies uncontrolled — loud failure is still controlled).

**Quiet failure** _(the defect)_
A failure path that swallows, defaults, hides, or silently recovers. The system
carries on as if nothing happened, or papers over the gap with a guess. This is what
the skill hunts.
_Avoid_: silent error, soft failure.

**Swallow**
Catching an exception and continuing without re-raising, recording, or surfacing it.
`except: pass` is the canonical form. A swallow with a log line is still a swallow
if nothing acts on the log.

**Default** _(as defect)_
A value the system invents when the real one is unavailable, instead of erroring. A
default is a guess; a guess presented as data is a lie with extra steps. Distinct
from a legitimate configured fallback the user chose.
_Avoid_: fallback (overloaded — a user-chosen fallback is fine; an invented default
is the defect).

**Hide**
Rendering unavailable evidence as if it were a normal value — empty, zero, `None`, a
blank list — with no signal that it's unknown versus genuinely absent. The operator
can't tell "no data" from "couldn't get data."

**Evidence**
What an operator can observe when something fails: the log line, the status field,
the error payload, the raised cause. Loud failure produces evidence; quiet failure
produces none.

**Recovery**
A legitimate, visible attempt to continue after failure — retry-with-warning, then
raise the real error with status/parameters/response context. AGENTS.md permits this.
Distinct from **hide**: recovery is visible and bounded; hiding is silent.
_Avoid_: resilience (overloaded, implies always-on rather than a specific visible
retry).

**Invariant**
A condition that must always hold for correctness — a lease is held before mutation,
a write is atomic, a record is well-formed. If nothing enforces it and fails when it
breaks, it's a hope, not an invariant.

**Edge case**
An input or state at a boundary — empty, partial, concurrent, timeout, malformed,
zero, negative, duplicate. Behaviour at an edge case must be decided, not accidental.

**Blast radius**
Who and what is affected when a failure path goes quiet, and how often that path is
hit. A quiet failure with a large blast radius outranks a loud one with a small one.

## Dependency boundary

The supply chain is a failure path too. A dependency you don't pin, declare-but-don't-
use, or let drift across sub-requirements is quiet failure at the boundary where
someone else's code enters yours. These are **harden** concerns, not a separate skill
— the `improve-codebase` router routes dependency problems here.

**Dependency boundary**
The seam where external packages enter the build — `requirements.txt`,
`package.json`, lockfiles, sub-requirements. Unknowns cross it on every install and
every upgrade, so it gets the same fail-loud treatment as any other boundary.

**Silent upgrade** _(defect)_
An unpinned or loosely-pinned dependency that can drift to a new minor/major on the
next install, changing behaviour with no diff in your code and no signal. The install
"works" and the behaviour changed underneath — a quiet failure with a large blast
radius.

**Ghost dependency** _(defect)_
A package declared in requirements but never imported. It looks like evidence of a
capability the system has; it's hidden evidence — the dependency isn't actually load-
bearing, and its declared presence misleads the next reader. Remove it or use it.

**Version drift** _(defect)_
The same package pinned to different versions across the root and a sub-requirements
file (e.g. root `fastapi==0.141.1`, worker `fastapi==0.140.0`). An unenforced
invariant: "the deployed tree shares one dependency version" is assumed but nothing
checks it, so the components silently run different code.

**Pinned**
A dependency with an exact version (and ideally a lockfile/integrity hash) so an
install is reproducible and an upgrade is a deliberate, reviewable diff rather than a
silent one. Pinning is the loud-failure fix for the dependency boundary.

## Principles

- **The fail-loud test.** Trace the failure path end to end. Does it raise a clear
  cause, or does it swallow / default / hide / silently recover? Quiet failure is the
  defect — find the specific line where it goes quiet.
- **The evidence test.** When this breaks at 2am, what does the operator see? If the
  answer is "nothing" or "a generic 500," the evidence is missing and the failure is
  effectively quiet even if it technically raised.
- **Harden at boundaries, not everywhere.** User input, external APIs, I/O,
  concurrency, and persistence are where unknowns enter. Defensive noise around
  correct internal calls is waste, not hardening.
- **Recovery is visible; hiding is silent.** A bounded retry that warns then raises
  the real error is legitimate recovery (AGENTS.md allows it). A silent default that
  hides unavailability is the defect. The difference is whether the operator can tell
  it happened.
- **Invariants are enforced at the seam, not hoped for.** If a condition must hold,
  something must check it and fail loudly when it doesn't. Concentrate the check at
  one seam rather than scattering assertions across callers.

## Relationships

- A **Failure path** either **fails loud** (produces **Evidence**) or **fails quiet**
  (a **Swallow**, an invented **Default**, a **Hide**, or silent **Recovery**).
- **Quiet failure** is the defect this skill surfaces; **fail loud** is the fix.
- An **Invariant** that isn't enforced becomes an **Edge case** that falls through to
  undecided behaviour.
- **Blast radius** ranks candidates: a quiet failure with a large blast radius is
  higher leverage than a loud one with a small radius.

## Rejected framings

- **"Robustness" as a score** (count the try/excepts): rewards defensive noise. We
  use fail-loud-per-failure-path instead — the question is whether each path surfaces
  its cause, not how many guards exist.
- **"Resilience" as always-on redundancy**: too broad. We mean the specific, visible,
  bounded **recovery** AGENTS.md permits — retry-with-warning, then raise the real
  error.
- **"Error handling" as a module concern**: too narrow and structural. This skill is
  about runtime behaviour across failure paths, not where the handler lives (that's
  `improve-codebase-architecture`).
- **Treating every default as a defect**: a user-configured fallback is legitimate.
  The defect is an *invented* default that hides unavailability — know the difference.
