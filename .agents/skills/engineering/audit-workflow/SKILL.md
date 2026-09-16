---
name: audit-workflow
description: Audit the repository's delivery and enforcement machinery — CI workflows, git hooks, pre-commit gates, required vs advisory checks, and the documented process — for drift between what is documented and what actually runs, gates that cannot fail, ghost mechanisms that were defined but never implemented, orphan checks nobody reads, duplicated or contradictory gates, stale enforcement claims, and delivery-pipeline friction worth removing. Grounded in PREVENTION_MECHANISMS.md status vocabulary and the live workflow set. Use when the user asks to audit CI, review the workflow or gates, check whether enforcement is real, find automation gaps or delivery friction, reconcile docs against pipelines, or analyze what a documented mechanism actually enforces. NOT FOR writing new pipelines from scratch, application code review, or performance profiling of application code.
when_to_use: workflow audit, CI audit, analyze workflows, are the gates real, enforcement audit, pipeline review, delivery pipeline analysis, CI/CD review, hooks review, automation gaps, workflow drift, does this actually run, gate analysis, audit the ci, audit the workflows, ci workflow audit
---

# Audit Workflow

Surface **process drift and gate defects** — the distance between the workflow the
repository *says* it runs and the machinery that actually runs. A mechanism
documented as ENFORCED with no implementation, a required-looking job that cannot
fail, an advisory check nobody reads, two gates doing one job differently, a
manual step everyone forgets, a pipeline stage that costs more than it catches.
This is the **process-truth sibling** of the other engineering skills: they audit
code, behavior, surfaces, and tests; this one audits the machinery that is
supposed to keep all of those honest.

## Glossary

Use these terms exactly. Consistent language is the point — don't drift into
"CI stuff," "the pipeline," or "DevOps." The canonical definitions live in
[LANGUAGE.md](LANGUAGE.md), injected below; the "Key principles" summary follows.

!`cat "${COMMANDCODE_SKILL_DIR}/LANGUAGE.md"`

Key principles (see LANGUAGE.md for full definitions):

- **The gate test**: can it fail? does its failure get read and acted on? does it
  map to a risk someone actually has? A check that cannot fail is a **paper gate**
  — false assurance, worse than no gate.
- **Documented is not enforced.** The only evidence of enforcement is a required
  check in the live ruleset or a recorded run that went red for the right reason.
  Everything else is a claim (PREVENTION_MECHANISMS models the honest vocabulary:
  ENFORCED / PARTIALLY ENFORCED / DEFINED).
- **Advisory is a contract word.** An advisory check is a deliberate choice, not a
  defect — until everyone treats it as required, or nobody reads it. Then it is an
  **orphan check**.
- **Measure friction, don't vibe it.** Delivery cost is measured
  (`scripts/ci_metrics.py`, `--durations`), not guessed. Slow is not the same as
  wasteful; duplicated and never-read are wasteful.
- **Gates are approval-gated to change.** Workflow files, hooks, and gate scripts
  are in the repo's sensitive/irreversible scope. This skill produces evidence and
  proposals; edits need Jacob's explicit authorization.

This skill is _informed_ by the project's enforcement doctrine. Kitty's
`docs/reference/PREVENTION_MECHANISMS.md` defines the mechanisms and their status
vocabulary; `merge-gate`/`policy-gate` define the required checks. Don't
re-litigate accepted decisions.

## Kitty grounding (read first)

| Doc / surface | Purpose |
|-----|---------|
| `docs/reference/PREVENTION_MECHANISMS.md` | The authority: 10 mechanisms with per-mechanism ENFORCED / PARTIALLY ENFORCED / DEFINED status and an implementation-priority list |
| `.github/workflows/` | The live machinery: `tests.yml` (scope classifier + `merge-gate` aggregation), `pr-agent-review.yml` (`policy-gate`), `nightly-health.yml` (Clock C: advisory hygiene + delivery metrics), `scan.yml`, plus the rest |
| `.githooks/pre-commit`, `.githooks/pre-push` | Local gates — `./kitty agent preflight --staged` and `scripts/hooks/pre-push`. Verify they are actually installed (`git config core.hooksPath`) and spot-check the pre-push claim of CI parity ("same commands, same thresholds") against `tests.yml` |
| `.pre-commit-config.yaml`, `Makefile` | Tool configuration and dev-command surface |
| `scripts/pr_scope.py`, `scripts/pr_policy.py` | The canonical scope classifier and policy gate — sensitive scope and `IRREVERSIBLE_PATTERNS` |
| `scripts/ci_metrics.py`, `scripts/scan.py` | Delivery-efficiency measurement and the daily stale-state report |
| `docs/audit/GITHUB_WORKFLOW_LEDGER_2026-08-04.md`, `docs/audit/DELIVERY_SYSTEM_REPAIR_CANDIDATES_2026-09-03.md`, `docs/audit/delivery-pipeline-baseline-2026-08-23.md` | Prior workflow evidence — start from these, don't re-derive them |
| `TESTING.md`, `docs/WORKFLOW.md`, `AGENTS.md` | What the process claims to be; AGENTS.md owns CI-interaction rules (one `--watch`, never poll) and the auto-merge prohibitions |

**Already measured elsewhere — cite, don't duplicate:** nightly `lychee`
(links), `vulture` (dead code), `deptry` / `pip-audit` / `npm audit` / `bandit`
(advisory hygiene), `ci_metrics.py` (delivery efficiency). Your finding is what
those *mean*, not re-running them.

**Recorded decisions:** `docs/DECISIONS.md` / `docs/adr/` own accepted decisions;
PREVENTION_MECHANISMS owns mechanism status. When a disposition deserves
permanence, offer an ADR using
[ADR-FORMAT.md](../improve-codebase-architecture/ADR-FORMAT.md) (shared).

## Failure modes to avoid

- **Cataloguing instead of auditing.** A list of every workflow is not a finding.
  The finding is a mismatch: claimed vs enforced, gate vs risk, cost vs catch.
- **Demanding every gate be required.** Advisory checks are deliberate
  (nightly-health says so explicitly: "advisory by design and never a merge
  gate"). The defect is a *mislabeled* or *unread* check, not an honest advisory.
- **Proposing gates without owners.** A new gate needs a failure owner, a
  disposition path, and a cost justification — otherwise you are adding a paper
  gate with extra steps.
- **Confusing slow with wasteful.** Measure with `ci_metrics.py` and pytest
  `--durations` before calling anything inefficient. Long but load-bearing is not
  friction.
- **Editing CI to "fix" a finding.** Workflow files, hooks, and gate scripts are
  the irreversible subset (`scripts/pr_scope.py`). Propose; Jacob authorizes.
- **Re-deriving prior audits.** The workflow ledger and delivery-repair
  candidates already exist. Build on them; mark which findings are new versus
  inherited-but-unresolved.

## Process

<scope_check>
If the user names a specific workflow, hook, or mechanism, skip the Task-tool
exploration phase: read that file plus its PREVENTION_MECHANISMS entry, run the
gate test, and move to candidates.
</scope_check>

### 1. Explore — inventory claimed vs implemented

Read the grounding surfaces above, then build two inventories:

**Claimed** — every mechanism a current doc asserts, with its claimed status:
PREVENTION_MECHANISMS rows (the authoritative vocabulary), `TESTING.md` gates,
`AGENTS.md` rules, `START_HERE.md`/`docs/WORKFLOW.md` process steps, registry or
index claims about automation.

**Implemented** — what actually runs: workflows and their triggers/required
status, hooks and what they call, scripts the workflows invoke, ruleset-required
check names, and recorded run history (a recent red run is enforcement evidence; a
job that has never failed across its history is a *candidate* paper gate, not a
verdict — some gates are simply well-behaved).

Then match them. Use the Task tool (`subagent_type=explore`) only for broad
sweeps. Hunt for:

- **Ghost gate** — DEFINED in a doc, absent from `.github/workflows/` and the
  hooks. (PREVENTION_MECHANISMS' "Needs `X.yml`" list is the known backlog; check
  which remain unimplemented today and whether awareness of them is current.)
- **Paper gate** — runs and cannot fail: `continue-on-error` with no reader, an
  assertion that cannot be false, a job whose failure does not feed any gate.
- **Stale enforcement claim** — a doc says ENFORCED (or a workflow name implies
  it) where the live ruleset/aggregation shows skipped, advisory-only, or absent.
- **Orphan check** — runs on a clock, produces output, and nothing consumes it
  (no issue, no gate, no owner reading the delta). Include the disposition of its
  last several runs.
- **Duplicated / contradictory gates** — the same concern checked twice with
  different versions, configs, or thresholds (each copy is a drift seed).
- **Missing gate** — a documented risk with no enforcement anywhere (an incident
  that reached main is the strongest evidence; AGENTS.md and the audit files
  record several).
- **Manual step** — a human-memory step that a documented policy depends on
  (prevention mechanisms that are procedural by design are fine; ones that are
  *supposed* to be automated are drift).
- **Friction** — duplicated work between jobs, a required job re-running what the
  nightly already profiles, gates ordered so failures surface late.

Apply the **gate test** to anything you suspect: (1) construct the failure it
claims to catch; (2) can it go red for that failure? (3) when it goes red, who
acts? A gate that fails (2) is a paper gate; one that fails (3) is orphaned.

### 2. Present candidates

Present a numbered list. For each:

- **Mechanism / surface** — named in repo vocabulary (e.g., "PREVENTION_MECHANISMS
  #2 one-active-lane", "`merge-gate` aggregation", "nightly `hygiene` job") —
  not "the CI thing"
- **Class** — ghost / paper / stale claim / orphaned / duplicated / missing /
  manual / friction
- **Claimed behavior** — quote the doc or name the implied contract
- **Observed behavior** — what actually runs (file, job, trigger, run evidence)
- **Evidence** — the check you performed (a run id, a file read, a ruleset fact,
  a `ci_metrics` number); never a guess
- **Risk** — what escapes while this is wrong, and how often that path is taken
- **Smallest honest fix** — implement / demote-and-label / delete / document as
  procedural / ADR the deliberate gap

Rank by **leverage = escape risk × path frequency ÷ fix cost**. A ghost gate
guarding a high-traffic merge path (e.g., single-lane enforcement that also
carries the repo's collision history) outranks a cosmetic efficiency item.

**Use the status vocabulary from PREVENTION_MECHANISMS** (ENFORCED / PARTIALLY
ENFORCED / DEFINED) when discussing claims — it is the repo's own honest scale.

Propose fixes only after the user picks a candidate. Until then, ask: "Which of
these would you like to explore?"

### 3. Grilling loop

Once the user picks a candidate, drop into a grilling conversation. Walk the gate
tree with them — what failure it exists to catch, who owns a red, what the
failure message must say, whether required or advisory is the honest label, what
it costs per run, and how the fix proves itself (the gate must be shown failing
for the right reason, and passing when the condition is fixed — for the test-side
of that proof, hand to `verify-by-mutation`).

Side effects happen inline as decisions crystallize:

- **A status claim is wrong today?** Correct it in the owning doc right there
  (PREVENTION_MECHANISMS updates its own status lines when reality changes) —
  that edit is a truth fix, not a CI change.
- **A deliberate gap is being kept?** Offer an ADR at `docs/adr/NNNN-title.md` so
  future workflow audits don't re-open it: _"Want me to record this as an ADR so
  future audits don't re-suggest it?"_ See
  [ADR-FORMAT.md](../improve-codebase-architecture/ADR-FORMAT.md) (shared).
- **An audit produces durable evidence** (a whole-pipeline pass)? Offer a dated
  file under `docs/audit/` per `docs/audit/README.md` — evidence, never an
  execution order. The existing ledger/baseline files are the pattern.
- **A gate change is warranted?** Stop at a proposal with exact file, job name,
  trigger, required/advisory label, failure message, and owner. CI, hooks, and
  gate scripts are approval-gated (sensitive/irreversible scope) — Jacob
  authorizes implementation; hand to the normal implementation path after that.
- **A new gate script needs a test?** Hand to `verify-by-mutation` — a gate whose
  own test is vacuous is this skill's defect wearing a green badge.

### 4. Cross-layer handoffs

- **The mismatch is in the doc, not the machinery** (status label stale, ledger
  outdated)? That is `audit-docs`.
- **A gate's enforcement code fails quietly** (a check that swallows its
  exception and reports success)? That is `harden-codebase` — quiet failure is
  the defect class.
- **A gate's assertion is vacuous** (passes whether or not the condition holds)?
  That is `verify-by-mutation`.
- **The gate's failure surface misleads users/operators** (a red run with cryptic
  output)? That is `improve-daily-ux` for user-facing surfaces; for operators,
  keep it here — the failure message is part of the gate.
- **A dependency, version, or advisory gate is the subject** (pip-audit, deptry,
  npm audit, dependabot policy)? That is `harden-codebase`'s dependency boundary —
  see its [DEPENDENCY-AUDIT.md](../harden-codebase/DEPENDENCY-AUDIT.md) (shared).
- **The whole request is broader upkeep triage** (docs + workflow + deps)? Start
  at the `maintain-repo` router instead; this skill is the workflow lane.

Record the handoff so the next session sees the thread. Don't let a cross-layer
finding die in chat prose.
