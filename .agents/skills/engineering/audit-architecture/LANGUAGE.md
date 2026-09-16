# Language

Shared vocabulary for every finding this skill makes. Use these terms exactly —
don't substitute "tech debt," "spaghetti," "coupling," or "architecture is
messy." Consistent language is the whole point.

## Terms

**Claim**
A statement of system shape that can be checked against code: a component
boundary, an owner, an import direction, a path, a port, a package layout, or a
decision. Claims come from `docs/ARCHITECTURE.md`, active ADRs, and
`docs/AUTHORITY_MAP.md` — nowhere else. The claim is the unit of conformance; the
system is audited claim by claim, not as a whole.

**Boundary**
A documented line the design says code should not cross — a module's owner, a
read path (`memory_graph`), a storage seam (`paths.py`, `StorageRouter`), a
service contract, an isolation boundary (ADR 0027/0033), or the canonical UI
surface (ADR 0039).

**The boundary test**
For each documented boundary: (1) what claim defines it? (2) what enforcement
makes crossing impossible, or failing, or loud — a type, a router, a path
constant, a test? (3) find the cheapest crossing and see if it is caught. No
enforcement in (2) makes the boundary **aspirational**; a crossing in (3) that
is not caught is a **boundary violation**.
_Avoid_: "reviewing the architecture" (too vague to produce findings).

**Boundary violation** _(the defect)_
Code that crosses a documented boundary — a direct store import where the
design requires the owning module, a route reading a table another subsystem
owns, a client reconstructing truth the server owns, or a route module carrying
domain logic where the design says "routes should remain thin." The finding
names the import/write path or the violating module and the claim it
contradicts.
_Avoid_: coupling (vague), bad practice (not evidence).

**Aspirational boundary** _(the defect)_
A documented boundary with no enforcement anywhere: the doc says "reads go
through X," and nothing — no type, no router, no test — makes a direct read
fail or even visible. The boundary is a hope; it is honored only while everyone
remembers. The fix is enforcement or an honest doc, not both-by-default.
_Avoid_: convention (a convention with an accepted decision behind it is a
ratified boundary — check for the ADR first).

**Orphan component**
A module, route, store, or service that runs but appears in no architecture
claim. Nobody owns its design; it grows unmanaged and surprises the next
reader. Distinct from dead code — orphans are live.
_Avoid_: undocumented feature (an orphan may be documented elsewhere, just not
in the design record).

**Ghost component**
A component, seam, or flow the design documents with no live implementation.
The doc side of the finding belongs to `audit-docs`; here the finding is that
the *design record* no longer describes the system.
_Avoid_: legacy (ghosts may be recent — check the dates).

**Ownership ambiguity** _(the defect — rank high)_
The highest-cost class: one store or path with two writers, one subsystem with
two claimed owners, or a documented owner that no longer writes what it owns.
Ambiguity is how silent corruption and double-maintenance enter a system; a
quiet failure in the data layer is worse than a loud boundary crossing.
_Avoid_: overlap (that's file-level; this is truth-level).

**ADR divergence**
An accepted decision the code contradicts, or a load-bearing practice the code
follows that no decision records. The first is a violation or an unratified
reversal; the second is an **unrecorded decision** waiting to become drift.
Route it: enforce, amend, supersede — or ratify by ADR.

**Layout drift**
Documented paths, ports, or package layout that has moved in code. The path
constants in `gateway/paths.py` are the truth for storage layout; docs claiming
locations they do not define are drift.

**Drift direction**
Whether the code moved past the docs or the docs moved past the code, and when.
Direction changes the fix: code-ahead usually wants a doc correction or a
re-ratification; docs-ahead usually wants enforcement built or the claim
withdrawn. Date it with `git log` when it decides the disposition.

**Enforcement**
The mechanism that turns a boundary from a claim into a fact — a type, a
router, a path constant, a failing test. Enforcement is to boundaries what
evidence is to failure paths: without it, the boundary is aspirational.

**Conformance**
The state of matching claim to code for one claim: **conformant**,
**violated**, or **unenforceable-and-aspirational**. Report one per finding —
"mostly conformant" is not a state.

## Principles

- **The boundary test.** Name the enforcement before judging the crossing. A
  boundary with no enforcement cannot be violated — it can only be ignored,
  which is its own finding.
- **Claims from docs, findings from code.** The doc supplies the claim; only
  the tree supplies a finding. Neither side alone is evidence.
- **Orphans and ghosts are both defects.** Live-but-unclaimed means nobody owns
  its design; claimed-but-dead means the record lies.
- **Ownership ambiguity outranks style.** Two writers of one store is a data
  integrity problem wearing an architecture costume — rank it above any
  structural preference.
- **An ADR is a promise about the system.** Promises are checked, not assumed;
  a divergence is a decision event (enforce it, amend it, supersede it), never
  a thing to note and ignore.
- **Conformance is not improvement.** This skill compares; it does not
  restructure. Deepening candidates go to `improve-codebase-architecture` with
  the finding as evidence.

## Relationships

- A **Boundary** is real (enforced), **aspirational** (claimed, unenforced), or
  **violated** (crossed and uncaught) — the **boundary test** decides which.
- An **Aspirational boundary** usually decays into a **Boundary violation**;
  the violation is the symptom, the missing enforcement is the cause.
- An **Orphan component** often lacks an owner; **Ownership ambiguity** is the
  same absence where something important depends on it.
- A **Ghost component** is a design-record defect (`audit-docs` territory) that
  this skill detects from the code side.
- **ADR divergence** and **Layout drift** are **Conformance** failures with a
  decision-shaped fix (ratify, amend, supersede, or enforce).

## Rejected framings

- **"Architecture is messy"**: unfalsifiable and unusable. State the claim and
  the contradiction.
- **Scoring the architecture** (grades, tiers, health percentages): a score
  hides which claim failed. Conformance is per-claim and three-valued.
- **Style review as conformance**: file sizes, naming, and folder taste are
  `improve-codebase-architecture`'s material at best, never findings here.
- **"The docs are old, so ignore them"**: a stale claim is a finding for
  `audit-docs`; the boundary may still be load-bearing while its description
  lags. Check the code before discarding the claim.
- **Reconstructing the design from code**: that produces a personal model, not
  conformance. The claim set comes from the ratified record.
