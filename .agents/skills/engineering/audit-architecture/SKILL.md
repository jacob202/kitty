---
name: audit-architecture
description: Audit whether the running system still matches its documented architecture — component boundaries and owners, import direction and layering, the paths/ports/package layout ARCHITECTURE.md describes, and accepted ADRs. Finds boundary violations, boundaries that are documented but unenforced, components that exist in code but in no architecture claim (and vice versa), ownership ambiguity between subsystems, and ADR divergence. Grounded in Kitty's ARCHITECTURE.md, ADR directory, and AUTHORITY_MAP. Use when the user asks to audit the architecture, check whether the code matches the architecture, whether documented boundaries are real, whether an ADR is still honored, find layer or ownership violations, or review architecture drift. NOT FOR deepening/refactoring candidates (use improve-codebase-architecture) or documentation truth generally (use audit-docs).
when_to_use: architecture audit, audit the architecture, does the code match the architecture, architecture drift, architecture conformance, boundary violation, are the boundaries real, layer violation, import direction, ownership ambiguity, ADR divergence, is this ADR still honored, architecture review
---

# Audit Architecture

Audit whether reality still matches the design. Kitty documents its shape
(`docs/ARCHITECTURE.md`), its owners (`docs/AUTHORITY_MAP.md`), and its accepted
decisions (`docs/adr/`, `docs/DECISIONS.md`) — this skill checks whether the
running system honors them, and where the two have drifted apart. It is the
**conformance sibling** of `improve-codebase-architecture`: that skill asks *is
this module shaped well?*; this one asks *does this system still match the shape
we said it has?* The improvement skill proposes changes; this one compares.

## Glossary

Use these terms exactly. Consistent language is the point — don't drift into
"architecture is messy" or "tech debt." The canonical definitions live in
[LANGUAGE.md](LANGUAGE.md), injected below; the "Key principles" summary follows.

!`cat "${COMMANDCODE_SKILL_DIR}/LANGUAGE.md"`

Key principles (see LANGUAGE.md for full definitions):

- **The boundary test**: for every documented boundary, name the enforcement
  evidence (a router, a type, a test, a path constant). No evidence means the
  boundary is **aspirational** — a claim, not a fact. Then find crossings.
- **Claims come from docs; findings come from code.** A conformance finding is
  a documented claim plus a live contradiction with a file and line, never a
  pattern-match on vibes.
- **Orphans and ghosts are both defects.** A component in code but in no
  architecture claim (orphan) means nobody owns its design; one in docs but not
  code (ghost) means the docs lie — hand ghost components to `audit-docs`.
- **Ownership ambiguity is the expensive class.** Two subsystems writing one
  store, or one store with no named owner, produces quiet corruption — rank it
  high.
- **An ADR divergence is a decision, not an accident.** Find the decision that
  was never ratified or never implemented, and route it: enforce it, amend it,
  or supersede it — never let it sit.
- **Conformance findings feed two owners.** Structural fixes go to
  `improve-codebase-architecture`; doc-side corrections go to `audit-docs`.

This skill is _informed_ by the repo's actual design record. `docs/ARCHITECTURE.md`
owns the current shape; ADRs own durable decisions; `docs/AUTHORITY_MAP.md`
resolves conflicts. Don't re-litigate accepted decisions.

## Kitty grounding (read first)

| Doc | Purpose |
|-----|---------|
| `docs/ARCHITECTURE.md` | The current runnable system shape — the primary claim set this skill tests |
| `docs/adr/` + `docs/DECISIONS.md` | Accepted decisions and their supersession chain |
| `docs/AUTHORITY_MAP.md` | Who owns each kind of truth; the arbiter for ownership findings |
| `CLAUDE.md` | The context-read rule in the consumer's own words: "Prompt/search context reads should go through `gateway/memory_graph.py`. Direct store imports remain acceptable for subsystem-owned writes and tests." |
| `docs/ALIGNMENT_MAP.md` | Kitty/Builder layering and boundary order |
| `gateway/paths.py` | The path-constant seam — where storage layout is actually defined |
| `gateway/storage_router.py`, `gateway/memory_graph.py` | The documented access rules (reads through `memory_graph`; direct store imports only for subsystem-owned writes and tests) |
| `docs/reference/CODEBASE_MAP.md` | The authoritative repository map to compare against the tree |
| ADR 0027/0033 (OpenWebUI isolation), ADR 0039 (kitty-chat is the canonical surface) | Live boundary decisions most likely to drift |
| `docs/ARCHITECTURE.md` → `KH-RUNTIME-01` note | Known defect: runtime probes can be stale — corroborate provenance, don't elevate it |

**Evidence sources for the code side:** import graphs (`grep` on imports, not
memory), route registrations in `gateway/routes/`, path constants, schema/store
ownership, and test seams that enforce a boundary. Use `git log` to date a
divergence when it matters.

## Failure modes to avoid

- **Vibes architecture review.** "Feels coupled" is not a finding. Name the
  documented claim, the contradicting file:line, and the direction of drift.
- **Re-deriving the design.** Read the authority, then check the code against
  it — do not rebuild an architecture model from scratch and grade the repo
  against your model.
- **Grading style.** Hyphens, file sizes, and pattern preferences are not
  conformance. This skill checks claims vs reality, not taste.
- **Duplicating the improvement skill.** Do not propose deepenings here. If a
  conformance finding implies restructuring, mark it and hand to
  `improve-codebase-architecture`.
- **Fixing docs here.** A wrong architecture claim is `audit-docs` work; this
  skill reports the contradiction and routes the doc side.
- **Treating every divergence as a violation.** Some divergences are accepted
  decisions or known defects (e.g., `KH-RUNTIME-01`). Cite the record and move
  on — reopening a ratified boundary needs new evidence.

## Process

<scope_check>
If the user names one subsystem, boundary, or ADR, skip the Task-tool
exploration phase: read the claim, check the code, and move to candidates.
</scope_check>

### 1. Explore — claim inventory, then verification

Build the **claim inventory** from the grounding docs — `ARCHITECTURE.md`'s
System boundary, Request flows (including "Routes should remain thin"), State
ownership, and Non-negotiable invariants tables; active ADRs; and ownership rows
— then verify each claim in code.
Use the Task tool (`subagent_type=explore`) for broad sweeps only.

For every claim, apply the **boundary test** and hunt these classes:

- **Boundary violation** — a path the design forbids (e.g., a route importing a
  store directly instead of going through its owner; UI code reaching around
  the gateway contract).
- **Route-layer bloat** — size the route modules against the documented
  thin-route claim: a route file carrying hundreds of lines of domain logic (or
  several unrelated domains) is the violation's signature, and the fix routes
  to `improve-codebase-architecture` as a split.
- **Aspirational boundary** — documented ("reads go through X") with no
  enforcement anywhere: no type, no router, no test that fails on a crossing.
- **Orphan component** — a module, route, or store that exists and runs but
  appears in no architecture claim: nobody owns its design.
- **Ghost component** — documented component or seam with no live
  implementation (hand the doc side to `audit-docs`).
- **Ownership ambiguity** — one store/path with two writers, one subsystem with
  two owners, or a documented owner that no longer writes.
- **ADR divergence** — an accepted ADR the code contradicts, or a practice
  everyone follows that no ADR records (offer the ADR).
- **Layout drift** — documented paths, ports, or package layout that has moved
  (`gateway/paths.py` is the truth for paths).

Date each divergence with `git log` when it changes the fix (a boundary that
predates its ADR is a different finding than one that postdates it).

### 2. Present candidates

Present a numbered list. For each:

- **Claim** — quote the architecture/ADR/authority statement, with its file
- **Code evidence** — the file:line that contradicts or lacks enforcement
  (for violations: the exact import or write path; for aspirational boundaries:
  the absence, stated as the checks you actually performed)
- **Class** — boundary violation / aspirational / orphan / ghost / ownership
  ambiguity / ADR divergence / layout drift
- **Drift direction** — did the code move past the docs, or the docs past the
  code, and when
- **Blast radius** — what quietly degrades while this stands (state corruption,
  two owners, an agent following a boundary that isn't real)
- **Proposed disposition** — enforce (code side, → improvement skill),
  document reality (doc side, → `audit-docs`), ratify (ADR), or deepen
  (→ `improve-codebase-architecture`)

**Use Kitty domain vocabulary** — `StorageRouter`, `memory_graph`, `paths.py`,
`gateway/routes/`, ADR numbers — not "the backend" or "the frontend."

Propose fixes only after the user picks a candidate. Until then, ask: "Which of
these would you like to explore?"

### 3. Grilling loop

Once the user picks a candidate, walk the boundary tree with them — what the
claim was, what the code does, which side is right, whether the boundary should
be enforced or re-drawn, and what would make a re-violation impossible or
loud. A boundary made real needs enforcement (a type, a router, a failing
test); a boundary abandoned needs its doc corrected and an ADR if the
abandonment is deliberate.

Side effects happen inline as decisions crystallize:

- **A ratified boundary should stay but nothing enforces it?** Hand to
  `improve-codebase-architecture` for the seam, and to `verify-by-mutation` for
  a test that fails on re-violation — a boundary test nobody can vacuously pass
  is the enforcement.
- **A decision is being made about a boundary?** Offer an ADR at
  `docs/adr/NNNN-title.md` using
  [ADR-FORMAT.md](../improve-codebase-architecture/ADR-FORMAT.md) (shared).
- **The architecture doc itself is wrong?** Hand to `audit-docs`; do not edit
  the claim here beyond a pointer-sized truth fix the user approves.
- **The audit produced durable evidence?** Offer a dated file under
  `docs/audit/` per `docs/audit/README.md` — evidence, never an execution order.

### 4. Cross-layer handoffs

- **Deepening or restructuring implied** → `improve-codebase-architecture`.
- **The claim (not the code) is stale** → `audit-docs`.
- **The boundary's enforcement fails quietly** (a check that can't fire, an
  owner that errors into a default) → `harden-codebase`.
- **The boundary is enforced by a gate/CI check** → `audit-workflow` for
  whether that check is real.
- **The user-facing consequence of the drift** (two sources of truth the UI
  shows inconsistently) → `improve-daily-ux`.

Record the handoff so the next session sees the thread. Don't let a cross-layer
finding die in chat prose.
