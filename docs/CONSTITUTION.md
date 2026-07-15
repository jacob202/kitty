# Kitty Constitution — Engineering Principles

**Status:** Repository-wide doctrine. Takes precedence over roadmap items,
skills, and one-off proposals when they conflict on *principle*.

This file holds the small number of rules that govern how Kitty is built.
It is short on purpose. Every line must earn its keep by changing real
decisions.

---

## Article I — Fail Loud, Never Mask

(Established; mirrored in `AGENTS.md`. Promoted here so it has a permanent
home alongside the rest of the constitution.)

Raise errors with clear causes. Do not swallow exceptions, return fake
defaults, or add silent fallbacks. External calls may retry with a
visible warning, then must raise the real error with useful context.

A system that hides failure is more dangerous than the failure itself.

---

## Article II — Life-First Ordering

(Established in `NORTH_STAR.md` §2, ADR 0016.)

Life projects (job search, benefits, education, health, money) outrank
code projects — including Kitty itself. Kitty must never become a hobby
that eats the time it was built to free.

---

## Article III — Leverage Before Reinvention

Kitty differentiates on architecture, reasoning, and product design — not
on rebuilding mature infrastructure.

### The rule

Before introducing a new subsystem, determine whether the problem has
already been solved by a mature, well-maintained project. Study existing
implementations, prototype promising approaches, and adopt or reference
them when they provide equal or better outcomes at lower long-term
maintenance cost.

We build our own infrastructure only when at least one of the following
is true:

- Existing solutions cannot satisfy Kitty's requirements.
- Kitty's design provides a meaningful architectural advantage.
- Owning the implementation is strategically important.

Every custom subsystem becomes a long-term maintenance obligation. The
burden of proof is on **building**, not adopting.

### The leverage audit

Kitty periodically performs engineering leverage audits to identify:

- infrastructure that should be adopted instead of maintained,
- custom systems that no longer justify their existence,
- underutilized capabilities already present,
- obsolete documentation, skills, prompts, and tooling,
- opportunities to simplify the repository without reducing capability.

Success is measured not only by what Kitty gains, but by what it no
longer needs to maintain.

### The pre-build checklist

Every major proposal or ADR answers these before implementation:

1. **Scout** — What mature solutions already exist?
2. **Compare** — What tradeoffs did they discover?
3. **Prototype** — Can we validate the idea quickly?
4. **Decide** — Build, adopt, reference, or reject.
5. **Re-evaluate** — If we started today, would we still build this
   ourselves?

### The load-bearing question

> *"If we started Kitty today, would we build this subsystem again?"*

If the answer is **no**, it becomes a candidate for replacement,
simplification, or removal during the next leverage audit.

This keeps the project from drifting into exactly the cycle that
motivated this article: accumulating bespoke infrastructure simply
because it already exists.

---

## How this document evolves

Amendments require an ADR and an explicit `last-amended` date. Principles
can be tightened, but not softened without a recorded reason. If a
principle stops biting real decisions, it gets cut — a constitution that
grows is a constitution that no longer governs.
