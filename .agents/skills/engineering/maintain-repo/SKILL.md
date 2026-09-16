---
name: maintain-repo
description: Triage a repository-upkeep request and route it to the right specialist — stale or drifting documentation, delivery/CI workflow and gate defects, and dependency/supply-chain quiet failure. Use when the user says "audit the repo", "what's stale", "what's drifting", "check the dependencies", "are the docs still accurate", "is anything rotting", "clean up the repo", "repo maintenance", or any broad upkeep ask that doesn't name a specific lane. This is the entry point of the upkeep family — it decides whether the leverage is in written truth (audit-docs), process/enforcement truth (audit-workflow), or the dependency boundary (harden-codebase), and cross-routes to the improvement family when the real problem is code shape, behavior, surface, or tests. Use a specialist directly when the user already named the lane.
when_to_use: audit the repo, what's stale, what's drifting, check the dependencies, are the docs still accurate, is anything rotting, clean up the repo, repo maintenance, repo upkeep, stale docs, dependency check, CI audit, workflow check, maintenance audit
---

# Maintain Repo (Router)

You are the **entry point** of the repository-upkeep family. Your job is not to
fix anything yourself — it is to **triage** a broad maintenance request, find the
highest-leverage staleness, and **route** to the specialist that owns the lane.
The family question is:

> **Has reality moved past the artifact — and is the artifact still true,
> enforced, and current?**

The improvement family (`improve-codebase`) asks whether the system behaves,
shapes, feels, and tests well. This family asks whether the *repo around the
system* — its documents, its machinery, its supply chain — still matches reality.
The two families cross-route freely; the specialists are the owners, this router
is only the switchboard.

> **Rule:** never do the specialist's work here. Triage, rank, route. If you find
> yourself auditing a doc's claims, testing a gate, or listing outdated packages,
> you have routed too late — hand off to the specialist and let it run its own
> process.

## The family

| Lane | Specialist | Core question | Heuristic |
|------|-----------|---------------|-----------|
| **docs** | `audit-docs` | Is the written truth still true? | claim test |
| **workflow** | `audit-workflow` | Does every claimed gate exist, bite, and get read? | gate test |
| **architecture** | `audit-architecture` | Does the running system match its documented design? | boundary test |
| **dependencies** | `harden-codebase` → [DEPENDENCY-AUDIT.md](harden-codebase/DEPENDENCY-AUDIT.md) | Does the supply chain fail loud? | fail-loud test at the dependency boundary |

**Conformance vs improvement:** this family audits whether the system *matches*
its documented design (boundaries, owners, ADRs); *changing* the design —
deepening, restructuring, re-shaping modules — belongs to
`improve-codebase-architecture` in the improvement family. A conformance finding
often becomes an improvement candidate; hand it over with the evidence.

**Not in this family:**

- **Code layers** (shape / behavior / surface / test trustworthiness) → the
  `improve-codebase` router owns those four specialists. A "clean everything up"
  request that turns out to be a shallow-module problem routes there.
- **Modernization strategy** (legacy assessment, technical debt, migration
  planning, maintenance *cost* reduction) → `aim42-software-improvement` owns the
  Analyze→Evaluate→Improve→Verify method. This family handles routine staleness
  and drift, not strategy.

Dependency hygiene is **deliberately a facet of `harden-codebase`**, not a
separate sibling — its [LANGUAGE.md](harden-codebase/LANGUAGE.md) "Dependency
boundary" section owns the vocabulary (silent upgrade, ghost dependency, version
drift, pinned). Do not create or route to a parallel dependency skill.

## When to use the router vs. a specialist

- **Router (this skill):** the request is broad or lane-ambiguous — "audit the
  repo," "what's stale," "check everything," "is anything rotting," "do
  maintenance."
- **Specialist directly:** the user named the lane — "are the docs stale"
  (`audit-docs`), "are the gates real" (`audit-workflow`), "check the
  dependencies" (`harden-codebase`).

If the user named a lane but the triage shows the highest-leverage problem is in
another lane, say so and offer to re-route — don't silently obey the wrong lane.

## Process

### 1. Scope the request

Restate what the user actually wants in one sentence. If the scope is the whole
repository, narrow it: ask which lane matters most, or pick the lane with the most
recent churn / most recorded incidents / most agent-facing surface, and say which
you chose and why.

<scope_check>
If the user already named a lane or ≤2 artifacts, skip straight to the handoff
(step 4). If the request is really about code shape/behavior/UI/tests, route to
the `improve-codebase` router instead — that is not a failure of this router,
it is its first job.
</scope_check>

### 2. Triage across the three lanes

Walk the in-scope repo once, looking for the **highest-leverage staleness in each
lane**. You are scanning to route, not to audit — spend minutes, not hours. For
each lane, note at most the top 1–2 candidates:

- **Docs** (`audit-docs`): freshness clauses past their window (start with
  `SKILL_REGISTRY.md`'s own re-verify triggers), claims the code contradicts,
  orphan authorities, ghost references, duplicated truth, snapshots sold as
  current, verified gaps where a doc should exist.
- **Workflow** (`audit-workflow`): ghost gates (DEFINED mechanisms with no
  implementation), paper gates, orphan checks, stale enforcement claims,
  duplicated/contradictory gates, escapes that a gate should have caught.
- **Architecture** (`audit-architecture`): documented boundaries that nothing
  enforces, boundary violations, orphan/ghost components, ownership ambiguity
  between subsystems, ADR divergences, layout drift against `gateway/paths.py`.
- **Dependencies** (`harden-codebase`): silent upgrades (unpinned/loose), ghost
  dependencies, accidental version drift across manifests, advisory findings with
  no disposition (deptry's known baseline, pip-audit, npm audit), unpinned
  install-path assumptions.

Use the Task tool (`subagent_type=explore`) for the scan when scope is large.
Read the grounding the specialists name — don't re-derive it here.

### 3. Rank by leverage

Rank the triaged candidates with one consistent question per lane:

> **leverage = (how many readers/decisions does this mislead?) × (what does it
> cost when wrong?) ÷ (how big is the fix?)**

- A stale enforcement claim on a merge path (`workflow`) usually outranks a stale
  prose claim on a cold doc (`docs`).
- A silent-upgrade exposure on the install path (`dependencies`) usually outranks
  a ghost package nobody imports.
- A freshness clause the repo promised to honor (`docs`) can outrank everything —
  it is a self-inflicted contract breach.

Present the ranked list. Be honest about which lane each candidate is in and why
it ranks where it does. Surface evidence gaps as gaps.

### 4. Route and hand off

Recommend the **top-ranked candidate's specialist** as the next move. State
plainly: "This is a `<lane>` problem — activating `<specialist>`." Then activate
that skill and let it run its own explore→candidates→grilling process from step 1.
Do not carry your triage notes into the specialist as conclusions — they are
leads, not verdicts; the specialist verifies against live evidence.

If the user picks a different candidate, route to *that* candidate's specialist
instead. The user chooses; you route.

### 5. Cross-pollinate

Findings cross lanes and families. When a specialist's work implies another lane,
name the handoff explicitly:

- A **docs** finding about a gate's status → `audit-workflow` owns the mechanism
  truth; `audit-docs` fixes the label.
- A **workflow** finding caused by a quiet-failing gate script →
  `harden-codebase`.
- A **dependency** finding caused by a doc claim (a pinned version documented
  wrong) → `audit-docs`.
- Any **code-layer** problem surfaced during upkeep triage → the `improve-codebase`
  router.
- Any candidate whose rejection deserves permanence → the relevant specialist
  offers an ADR (shared `ADR-FORMAT.md`).

Record the handoff so the next session sees the thread. Don't let a cross-lane
finding die in chat prose.

## Failure modes to avoid

- **Doing the specialist's work here.** The router triages and routes. Claim
  tests, gate tests, and dependency listings belong to the specialists.
- **Boiling the ocean.** Triage is a scan, not an audit. Cap candidates per lane;
  rank; route to the top one.
- **Treating strategy as upkeep.** Modernization, debt programs, and migration
  planning route to `aim42-software-improvement`; this family is routine
  staleness and drift.
- **Re-opening the dependency decision.** Dependency hygiene stays a facet of
  `harden-codebase` per its recorded boundary; do not propose a separate skill.
- **Vague routing.** "Maybe look at the docs" is not a route. Name the specialist,
  name the candidate, activate it.
