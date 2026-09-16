# Language

Shared vocabulary for every finding this skill makes. Use these terms exactly —
don't substitute "outdated," "old," "messy," or "cleanup." Consistent language is
the whole point.

## Terms

**Claim**
A statement in a document that can be checked against live evidence — a path, a
command, a status label, a version, a count, a date, or an authority assertion.
The claim is the unit of docs freshness; a doc is audited claim by claim, not as a
vibe.
_Avoid_: statement, content (too vague to verify).

**Fresh**
A claim that matches live evidence (code, Git, CI, runtime, or the owning
authority). Freshness is per claim, not per file — a doc can be 95% fresh.

**Stale claim** _(the defect)_
A claim contradicted by live evidence. The doc asserts a reality that no longer
holds. The defect is the contradiction, not the age — an old doc with true claims
is fresh.
_Avoid_: outdated doc (that's a conclusion about the file, not evidence about a
claim).

**Ghost reference** _(the defect)_
A claim pointing at something that no longer exists — a deleted file, a removed
command or flag, a retired workflow, an archived doc cited as current instruction.
The reader follows it and finds nothing.

**Orphan authority** _(the defect)_
A document claiming ownership of a kind of truth that `docs/AUTHORITY_MAP.md` (or
a superseding ADR) assigns elsewhere. Competing authority is the most dangerous
class: an agent can follow it and act on the wrong truth.
_Avoid_: duplicated doc (overlap without an authority claim is milder — see
**Duplicate truth**).

**Duplicate truth** _(the defect)_
The same fact maintained in two current places. Guaranteed to drift: one copy
will move first. The fix is a pointer from the losing copy to the owner (the
`docs/CODEBASE_MAP.md` redirect pattern), never synchronization.
_Avoid_: repetition (restating context is fine; restating owned facts is not).

**Unverifiable claim**
A claim with no checkable evidence anchor — no path, command, date, count, or
source. Not automatically a defect, but permanently unmaintainable: it cannot be
audited, so it drifts silently. Its finding is "add an anchor," not "the claim is
false."

**Freshness clause**
A documented re-verification contract: "re-verify when X happens / when this date
is older than N days." `SKILL_REGISTRY.md` is the canonical example. A freshness
clause **expired** when its trigger has fired and re-verification has not
happened — stale by the doc's own contract, which makes it the highest-confidence
finding class.

**Last-verified date**
The dated evidence anchor a maintained snapshot must carry (`PROJECT_STATUS.md`
pattern: "verified at commit X on date Y"). A current-claiming doc with no anchor
is assumed drifting.

**Snapshot vs living doc**
A **snapshot** records a state at a date/commit and is historical by
construction — it must be dated and must not be updated to look current. A
**living doc** (authority, registry, guide) must be current. The defect
**snapshot sold as current** is a snapshot whose label, title, or surrounding
links present it as today's truth.
_Avoid_: stale doc (a labeled snapshot is never "stale" — it's dated).

**Disposition**
The single decision a finding asks for: **update** the claim, **archive** the
doc, **redirect** it to a compatibility pointer, **promote** the content to a
canonical/authority home, **re-walk** a registry/index, or **leave labeled**
(low-risk, ownerless). Every finding gets exactly one proposed disposition.

**Opportunity**
A verified gap where a document *should* exist — an undocumented invariant, a
decision living only in chat, a recurring question with no answer in the tree.
The constructive half of the audit. An opportunity feeds an existing authority
(ADR, ARCHITECTURE, CONTEXT); it never activates work by existing.

**Promotion**
Moving a proven truth from a transient surface (chat, a plan, a packet, a
comment) into its canonical home. The rescue path for knowledge that is about to
evaporate.

## Principles

- **The claim test.** State the claim; state what live evidence shows. A finding
  that cannot produce both is a lead, not a finding.
- **Evidence beats prose.** Live Git, code, CI, and runtime outrank any document.
  When they disagree, the document is the defect — unless it is a dated snapshot,
  in which case only its labeling can be wrong.
- **One truth, one home.** Duplicated truth is debt with a guaranteed interest
  payment (ADR 0020 and ADR 0029 are the repo's own applications of this).
- **Disposition, not deletion.** An audit produces the evidence for safe cleanup;
  moving or deleting files is a separate, approval-gated act. (The 2026-07
  documentation audit shipped the same rule: "does not move or delete any files.")
- **Existing enforcement is context, not finding.** lychee (links), `scan.py`
  (stale PR/issue state), and registry freshness clauses already run on a clock.
  Cite them; don't re-do them.
- **Findings are inert.** An audit result activates nothing
  (PREVENTION_MECHANISMS #7). It feeds the authority that owns a fix decision.

## Relationships

- A **Claim** is **Fresh** or a **Stale claim**; a **Ghost reference** is a
  claim whose referent is gone.
- **Orphan authority** and **Duplicate truth** are how truth splits; the fix is a
  pointer to the owner named in `docs/AUTHORITY_MAP.md`.
- An **Unverifiable claim** cannot go stale loudly — it drifts silently, which is
  why "add an anchor" outranks "argue about the wording."
- A **Freshness clause** that expires converts a doc into a **Stale claim** by its
  own contract — the cleanest evidence a finding can have.
- A **Snapshot** is healthy when labeled and defective when **sold as current**.
- An **Opportunity** ends in **Promotion** or an ADR offer — never in a new
  backlog.

## Rejected framings

- **"Docs are out of date"** as a verdict: not a claim, not auditable. Name the
  claim or drop it.
- **Auditing by age**: old and true beats new and wrong. Dates matter only where
  a freshness clause or snapshot label makes them matter.
- **Style review in truth's clothing**: wording, tone, and structure are out of
  scope. A poorly written doc with true claims is fresh.
- **Link-checking as a docs audit**: lychee already owns mechanical link
  validity nightly. This skill checks whether the *target still means what the
  text says*.
- **The audit as a work queue**: findings become evidence for existing
  authorities; a findings file that reads as an instruction list violates
  PREVENTION_MECHANISMS #7 (planning inputs are inert until explicitly
  activated).
