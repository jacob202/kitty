---
name: audit-docs
description: Audit documentation for staleness, drift, and opportunity — claims that no longer match live evidence, moved or competing authorities, ghost references, duplicated truth, snapshots sold as current, freshness clauses past their re-verification window, and the gaps where a document should exist. Grounded in Kitty's AUTHORITY_MAP, the SKILL_REGISTRY freshness contract, and the archive/supersession policy. Use when the user asks whether the docs are stale, wants a documentation audit or docs review, notices a doc contradicting the code, wants a registry or index re-walked, or asks what documentation is missing. NOT FOR link checking (nightly lychee owns that), prose style editing, or writing new feature documentation.
when_to_use: documentation audit, stale docs, docs freshness, docs drift, doc contradicts code, is this doc still accurate, registry re-walk, documentation gaps, what docs are missing, doc maintenance, documentation staleness, are the docs stale, docs out of date, is this doc accurate
---

# Audit Docs

Surface **documentation staleness and drift** — places where the written truth no
longer matches live evidence, or where the writing itself has become a defect:
a claim the code contradicts, an authority the AUTHORITY_MAP moved elsewhere, a
ghost reference to something deleted, the same fact maintained twice, a dated
snapshot presented as current, a freshness clause past its window. This is the
**written-truth sibling** of the other engineering skills: they ask *does it work
/shape well / fail loud / get seen?*; this one asks *is what we wrote down still
true, and is anything important unwritten?*

## Glossary

Use these terms exactly. Consistent language is the point — don't drift into
"outdated," "old," or "messy." The canonical definitions live in
[LANGUAGE.md](LANGUAGE.md), injected below; the "Key principles" summary follows.

!`cat "${COMMANDCODE_SKILL_DIR}/LANGUAGE.md"`

Key principles (see LANGUAGE.md for full definitions):

- **The claim test**: a doc is only as fresh as its checkable claims. Find the
  claim (a path, command, status, version, authority assertion), check it against
  live evidence, and report the verdict. No claim, no finding.
- **Evidence beats prose.** When a doc and live Git/code/runtime disagree, the
  evidence wins and the doc is the defect — unless the doc is a dated snapshot,
  in which case its *labeling* is the defect.
- **One truth, one home.** Duplicated truth is guaranteed drift (ADR 0020/0029
  doctrine). The fix is a pointer, not synchronization.
- **Disposition, not deletion.** Archive and redirect are the normal fixes.
  Deletion is approval-gated; an audit produces evidence for a safe cleanup, it
  does not perform one.
- **Opportunity is half the audit.** A verified gap where a doc *should* exist
  (an undocumented invariant, an unrecorded decision, a recurring question) is a
  finding too — and it feeds an authority, never a new backlog.

This skill is _informed_ by the project's documentation doctrine. Kitty's
`docs/AUTHORITY_MAP.md`, `SKILL_REGISTRY.md`, and archive policy define what
counts as truth and how it is retired; don't re-litigate accepted decisions.

## Kitty grounding (read first)

Before exploring, read:

| Doc | Purpose |
|-----|---------|
| `docs/AUTHORITY_MAP.md` | Who owns each kind of truth and the conflict rules — the arbiter for every authority finding |
| `SKILL_REGISTRY.md` | The canonical example of a freshness contract: "Last verified", the re-verify triggers, and the 90-day window |
| `docs/audit/README.md` | The dated-audit convention — where evidence lives and how it is consumed |
| `docs/archive/audits-2026-07/DOCUMENTATION_AUDIT.md` | Prior art: the classification key (Canonical / Active operational / Historical / Stale / Archive candidate / …) and the no-move-no-delete rule |
| `docs/archive/README.md` + `docs/archive/plans-2026-09-14/README.md` | Archive and supersession policy — archived docs are intentional, not defects |
| `docs/PROJECT_STATUS.md`, `docs/DISPOSITION_LEDGER.md`, `docs/KNOWLEDGE_GRAPH.md` | Examples of dated snapshots and compatibility pointers (the pattern a fix should copy) |

**Already enforced elsewhere — do not duplicate:** nightly `lychee` checks
broken links (`nightly-health.yml`), `scripts/scan.py` reports stale PR/issue
state, and `nightly-health.yml` profiles delivery health. Cite these as existing
enforcement; don't re-run them as your finding.

**Recorded decisions:** `docs/DECISIONS.md` / `docs/adr/` own accepted decisions.
When a doc conflict deserves permanence, offer an ADR using
[ADR-FORMAT.md](../improve-codebase-architecture/ADR-FORMAT.md) (shared).

## Failure modes to avoid

- **Vibes auditing.** "This doc looks old" is not a finding. Name the claim, the
  live evidence, and the contradiction.
- **Rewriting prose.** This is a truth audit, not an editing pass. Style and
  wording are out of scope; a doc that is ugly but accurate is fresh.
- **Treating every old doc as a defect.** Dated snapshots and archives are
  intentional (see archive policy). The defect is a snapshot sold as current, or
  an archive still being cited as instruction.
- **Re-running existing enforcement.** lychee, `scan.py`, and the registry's own
  freshness clause already run. Report what they cover as context, not as novel
  findings.
- **The audit as backlog.** Findings feed existing authorities (AUTHORITY_MAP
  owners, `docs/audit/` evidence, ADRs). A new list that activates work by
  existing violates PREVENTION_MECHANISMS #7 — planning inputs are inert until
  explicitly activated.
- **Deleting.** Never move, delete, or rewrite someone's working doc without the
  user's explicit disposition decision. Evidence first; cleanup after approval.

## Process

<scope_check>
If the user names ≤2 docs or one directory, skip the Task-tool exploration phase.
Read those docs, extract claims, verify each against live evidence, and move to
the candidates list.
</scope_check>

### 1. Explore — build the claim inventory

Read the grounding docs above, then walk the in-scope docs. Use the Task tool
(`subagent_type=explore`) for broad sweeps only when scope is large. For each
document, extract its **checkable claims** and verify against the cheapest live
evidence:

- **Path claims** — does the referenced file/dir/command still exist? (`git ls-files`,
  direct reads)
- **Status claims** — does a stated authority, ratification, or "Active" label
  still match `docs/AUTHORITY_MAP.md` and the supersession chain?
- **Behavior claims** — does a described capability/flag/workflow match the code
  and CI? (cite the file and line that proves or disproves)
- **Number claims** — counts of skills, ADRs, workflows, tests — re-count them.
- **Freshness clauses** — has a documented re-verify trigger fired (a skill was
  added, the date is older than 90 days, an upstream it names changed)?
- **Duplication** — is the same fact maintained in two current docs? Name both,
  and which one the AUTHORITY_MAP assigns.
- **Opportunity pass** — walk recent activity (recent commits, ADR gaps, repeated
  questions in the room/docs) for truths that exist only in transient surfaces
  and deserve promotion to a canonical home. Include load-bearing capabilities
  the root contract never routes to: if `AGENTS.md` / `START_HERE.md` name no
  skill or procedure for a real family of work, a cold agent cannot find it —
  that gap is an opportunity, not a documentation absence.

Apply the **claim test** to anything you suspect: state the claim in one sentence,
then state what you observed. If you cannot state both, you have a lead, not a
finding.

### 2. Present candidates

Present a numbered list of findings, each classified with the prior audit's key
(`Stale claim`, `Ghost reference`, `Orphan authority`, `Duplicate truth`,
`Unverifiable claim`, `Freshness clause expired`, `Snapshot sold as current`,
`Opportunity`, `Needs owner review`). For each:

- **Doc** — the file, and the exact claim (quote or cite the line)
- **Class** — from the key above
- **Evidence** — what you checked and what it showed (path, command output, Git
  fact). Quote it; don't paraphrase.
- **Proposed disposition** — update / archive / redirect (compatibility pointer) /
  promote to ADR / re-walk registry / leave with a label. One per finding.
- **Blast radius** — who is misled while this stays stale (agents following the
  doc, operators, reviewers) and how badly.

**Use Kitty vocabulary**: the concern IDs from `docs/AUTHORITY_MAP.md` (e.g. "the
`roadmap` concern"), the registry's verdict vocabulary, the archive-policy terms —
not "the meta docs."

**Doc conflicts**: when a finding contradicts an accepted ADR or an explicit
authority, say so and default to the authority. Only surface it as a defect if
the authority itself moved; otherwise it is a rejected finding waiting for an ADR.

Propose edits only after the user picks a finding. Until then, ask: "Which of
these would you like to explore?"

### 3. Grilling loop

Once the user picks a finding, drop into a grilling conversation. Walk the truth
tree with them — what the doc claimed, when it stopped being true (Git archaeology
when useful), who owns the truth now, what the smallest honest fix is (a pointer →
a dated label → an update → an archive), and whether the fix needs permanence.
For dependency-category and test-strategy language, see
[DEEPENING.md](../improve-codebase-architecture/DEEPENING.md) (shared) only when
the fix touches code behavior.

Side effects happen inline as decisions crystallize:

- **A finding is accepted and the fix is small?** Make the edit right there —
  update the claim, add the dated label, or replace the duplicated truth with a
  compatibility pointer. Re-run the claim test on the fixed doc before moving on.
- **A rejection deserves permanence** (the doc's claim is deliberately allowed to
  differ, e.g. a known-divergence comment)? Offer an ADR at
  `docs/adr/NNNN-title.md`: _"Want me to record this as an ADR so future docs
  audits don't re-suggest it?"_ See
  [ADR-FORMAT.md](../improve-codebase-architecture/ADR-FORMAT.md) (shared).
- **The audit produced durable evidence** (a whole-repo pass, or findings other
  agents will consume)? Offer to persist it as a dated file under `docs/audit/`
  following `docs/audit/README.md`. Never persist a findings file that reads like
  an execution order — evidence only.
- **A skill was added/removed/merged/archived/rewired, or the registry's own
  freshness trigger fired?** A `SKILL_REGISTRY.md` re-walk is mandatory, not
  optional — perform it and update the "Last verified" line with what was walked.
- **A new term or verified invariant surfaced?** Add a short definition to
  `docs/ARCHITECTURE.md` or a new `docs/CONTEXT.md` using
  [CONTEXT-FORMAT.md](../improve-codebase-architecture/CONTEXT-FORMAT.md) (shared).

### 4. Cross-layer handoffs

- **The stale claim is about runtime behavior** (a doc says "raises" and it
  swallows)? That is `harden-codebase` — the doc and the code disagree, and the
  code side owns the fix.
- **The stale claim is about a gate, workflow, or enforcement status** (a doc says
  "ENFORCED" and nothing enforces it)? That is `audit-workflow`.
- **The stale claim is about module shape or a seam documented nowhere?** That is
  `improve-codebase-architecture`.
- **The stale claim is about the documented system shape** (a boundary, owner, or
  ADR the code no longer matches)? That is `audit-architecture`.
- **The stale claim is about what a user sees** (documented copy/state that the
  surface no longer shows)? That is `improve-daily-ux`.
- **The doc describes a dependency or supply-chain fact** (pinned version,
  advisory status)? That is `harden-codebase`'s dependency boundary — see its
  [DEPENDENCY-AUDIT.md](../harden-codebase/DEPENDENCY-AUDIT.md) (shared).

Record the handoff so the next session sees the thread. Don't let a cross-layer
finding die in chat prose.
