# Language

Shared vocabulary for every finding this skill makes. Use these terms exactly —
don't substitute "CI stuff," "the pipeline," "DevOps," or "automation." Consistent
language is the whole point.

## Terms

**Gate**
An automated check whose result blocks something or is read by someone. Two
honest kinds exist: **required** (its failure blocks merge/deploy) and
**advisory** (it reports and does not block). The label is a contract, not a
mood — mislabeling in either direction is drift.
_Avoid_: check (too vague about the blocking contract).

**The gate test**
Three questions asked of every gate: (1) what failure does it claim to catch?
(2) can it go red for that failure? (3) when it goes red, who acts? Failing (2)
makes it a paper gate; failing (3) makes it orphaned. The test is the unit of
work this skill performs.

**Paper gate** _(the defect)_
A gate that cannot fail — a vacuous assertion, a `continue-on-error` nobody reads,
a job whose failure feeds no aggregator, a check that reports success on its own
error. Worse than no gate: it converts absence of evidence into false assurance.
_Avoid_: flaky check (that fails wrongly; a paper gate fails never).

**Ghost gate** _(the defect)_
A mechanism documented as existing (or as "needs workflow") with no implementation
anywhere — not in `.github/workflows/`, not in `.githooks/`, not in `scripts/`.
The documentation promises enforcement the repository does not have.
This is the class `PREVENTION_MECHANISMS.md`'s "DEFINED — needs `X.yml`" entries
describe; re-check which remain unimplemented, don't re-derive the list.

**Stale enforcement claim** _(the defect)_
A document asserting ENFORCED (or a workflow name implying enforcement) where the
live truth is PARTIALLY ENFORCED, advisory-only, skipped by scope, or absent. The
repo's own status vocabulary (ENFORCED / PARTIALLY ENFORCED / DEFINED) is the
honest scale — discrepancies between it and the machinery are findings.

**Orphan check** _(the defect)_
A check that runs, produces output, and is consumed by no gate, issue, owner, or
decision. Its runs pile up unread. Evidence: the disposition of its last several
runs — no comment, no issue, no fix, no ADR, no waiver.

**Duplicated gate** _(the defect)_
The same concern enforced in two places with different versions, configs, or
thresholds. Each copy is a drift seed: one will be updated, the other will quietly
enforce yesterday's rule.
_Avoid_: defense in depth (layers catching *different* failures are healthy;
copies enforcing the *same* one are debt).

**Contradictory gate**
Two gates whose conditions cannot both hold, or whose failure messages tell the
operator opposite actions. The repository fights itself.

**Missing gate**
A documented risk or a recorded incident with no enforcement anywhere. The
strongest evidence is an escape (see below); the weakest is a hypothetical —
label which one you have.

**Escape**
An incident that reached `main`, the registry, or production despite the gates in
place. An escape is ground truth that some gate is missing, paper, or orphaned —
trace the path it took and name the gate that should have caught it.

**Manual step**
A step a human must remember for a documented policy to hold. Legitimate when the
policy is explicitly procedural (PREVENTION_MECHANISMS marks these); drift when a
doc implies automation the repository does not have.

**Friction**
Delivery cost that buys less than it should: duplicated work across jobs, a
required path re-running what the nightly already profiles, failures surfacing
late, gates serialized without dependency. Measured with `scripts/ci_metrics.py`
and pytest `--durations` — never asserted from vibes.
_Avoid_: slowness (long-but-load-bearing is not friction).

**Clock**
A scheduled cadence with a distinct purpose (the repo names these: PR-time CI,
nightly health as "Clock C", the daily stale scan). Findings must respect the
clock: a nightly advisory check is not a PR-gate defect, and a PR gate is not
slow merely because the nightly also profiles its subject.

**Status vocabulary**
The repo's honest three-value scale from `PREVENTION_MECHANISMS.md`: **ENFORCED**
(platform or CI provably blocks), **PARTIALLY ENFORCED** (some protections live,
specific gaps named), **DEFINED** (documented intent, no working enforcement yet).
Use these words in findings; they force the evidence question.

**Owner**
Who acts when a gate goes red or a mechanism changes status. A gate without an
owner is a future orphan; a mechanism without an owner is a future ghost.

## Principles

- **The gate test.** Can it fail? Does failure get read? Does it map to a real
  risk? A gate failing the first is a paper gate; failing the second, an orphan.
- **Documented is not enforced.** Only a required check in the live ruleset, or a
  recorded run that went red for the right reason, is enforcement evidence.
  Prose, filenames, and intentions are claims.
- **Advisory is a contract word.** Advisory-by-design (nightly-health says so
  explicitly) is healthy. Advisory-in-name-required-in-practice, or advisory
  nobody reads, are the defects.
- **Measure friction.** `ci_metrics.py`, run durations, and run dispositions are
  the evidence. "Feels slow" is not a finding.
- **Propose, don't edit.** Workflow files, hooks, and gate scripts are the
  irreversible subset (`scripts/pr_scope.py`). This skill's output is evidence
  plus a proposal with an exact shape; Jacob authorizes changes.
- **Respect existing evidence.** The workflow ledger, delivery baselines, and
  repair-candidate files already exist. Build on them; label findings inherited
  vs new.

## Relationships

- A **Gate** passes the **gate test** or is a **Paper gate** (fails to fail) or an
  **Orphan check** (fails to be read).
- A **Ghost gate** is a **Stale enforcement claim** whose mechanism is wholly
  absent; a **Stale enforcement claim** is the broader class — the doc outranks
  the machinery and is wrong.
- An **Escape** is evidence that converts "missing gate" from hypothesis to fact.
- A **Duplicated gate** or **Contradictory gate** is drift already underway;
  **Friction** is cost without catch.
- **Clocks** bound which findings are actionable: fix advisories by reading their
  delta, fix required gates by proving they can fail.

## Rejected framings

- **"Make everything required."** Advisory checks are a deliberate design
  (nightly-health: "advisory by design and never a merge gate"). The defect is
  dishonest labeling or unread output, not advisory existence.
- **"More gates = more safety."** Ungated additions create paper gates, noise,
  and maintenance drag. The gate test decides, not the count.
- **"The pipeline is slow, speed it up."** Long-but-load-bearing is not friction.
  Measure with `ci_metrics.py`; find duplication and dead weight before speed.
- **"Just fix the workflow file."** CI, hooks, and gate scripts are the
  sensitive/irreversible subset — proposals are this skill's output, approval is
  Jacob's, implementation follows the normal path.
- **Re-deriving the mechanism list.** `PREVENTION_MECHANISMS.md` already
  enumerates mechanisms with statuses and a priority order. The finding is the
  current gap between those statuses and live reality, not a fresh catalog.
