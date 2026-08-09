# Builder Organization Architecture

**Status:** Design — not yet implemented. Not ratified. Implementation requires separate ADR.
**Author:** Jacob
**Date:** 2026-08-05
**Ratification:** `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` Decision 4 — preserved as design input. Builder's ratified role is execution control plane (ADR 0017). Organization concepts (Chief Architect, Reviewer, Implementer) may inform future ADR amendments.

Builder is not a workflow engine. It is an engineering organization of
specialized workers, each with bounded authority, defined inputs and outputs,
escalation paths, and communication protocols. Workers coordinate through
durable artifacts — not chat memory, not handoff prose.

---

## Design Principles

1. **No worker approves its own work.** Review and implementation are always
   different roles. Review and review-of-review are always different roles.

2. **Authority is bounded by role, not by session.** The Chief Architect
   decides architecture. The Reviewer decides acceptance. Neither can step
   into implementation and direct the Implementer at edit level.

3. **Escalation follows the org chart, not the packet graph.** A Reviewer
   who finds an architectural violation escalates to Chief Architect, not to
   the Implementer. A Planner who discovers a missing research question
   escalates to Research, not to Jacob.

4. **Communication is through durable artifacts.** Every role writes
   structured evidence to the durable store. No worker infers state from
   another worker's chat session, handoff note, or PR comment.

5. **Serialization is per-artifact, per-role.** Two roles that touch the
   same artifact serialize. Two roles that touch disjoint artifacts run in
   parallel. The artifact graph — not a pipeline — determines concurrency.

6. **The org chart is the escalation chart.** Every role has exactly one
   upstream and a defined escalation path. Escalation chains are short:
   Implementer → Reviewer → Chief Architect → Jacob. No role escalates
   through a peer.

---

## Role Definitions

### 1. Chief Architect

**Responsibilities:**
- Own architectural decisions and frozen specifications.
- Reject packets that violate the architecture, even if they are otherwise
  correct.
- Resolve architectural disputes escalated by Reviewer or Planner.
- Maintain `docs/ARCHITECTURE.md`, `docs/reference/CODEBASE_MAP.md`, and
  frozen spec documents.
- Audit architectural drift between planned and observed module boundaries.
- Classify proposed changes as structural vs behavioral.

**Authority:**
- Veto power over any packet on architectural grounds (recorded as a
  structured architectural rejection, not a code review).
- Final authority on module boundaries, layer-direction rules, and import
  discipline.
- May freeze any module for architectural review before other roles touch it.
- Cannot implement, review implementation correctness, or decide acceptance
  on non-architectural grounds.

**Inputs:**
- Packet briefs escalated by Reviewer with an architectural concern.
- Architectural audit findings from QA or Performance.
- Proposed refactoring scope from Refactoring Team.
- Runtime structural drift detected by Operations.

**Outputs:**
- Architecture decision records (mini-ADRs scoped to the packet/investigation).
- Frozen spec amendments.
- Architectural rejection records with lineage to the specific violated rule.
- Module freeze/unfreeze directives.

**Escalation rules:**
- Escalates to Jacob only when: a design requires a new architectural
  principle not covered by existing ADRs; two frozen specs contradict; or
  an architectural dispute cannot be resolved within the org.

**Required evidence:**
- Architectural rejection must cite the exact rule, ADR, or frozen spec
  paragraph violated.
- Architecture decisions must include the alternatives considered and the
  structural invariant being preserved.
- Freeze directives must name the module and the concern driving the freeze.

**Communication protocol:**
- Writes to: `docs/adr/`, the Architecture section of the result evidence
  bundle.
- Reads from: `docs/ARCHITECTURE.md`, `docs/adr/`, packet briefs, Reviewer
  escalations.
- Does not communicate directly with Implementer. Architectural guidance
  flows through Planner or Reviewer.

**Parallel work:** With any role that does not touch the same frozen spec or
module boundary definition. Chief Architect and Planner may work in parallel
when Planner is decomposing packets that do not cross architectural
boundaries.

**Serialization required:** When the architectural decision covers a module
another role is currently modifying. When two architectural disputes about
the same module arrive simultaneously.

---

### 2. Planner

**Responsibilities:**
- Decompose approved Missions into executable packets.
- Classify every packet by model class (`free-exec`, `free-exec-blocked`,
  `paid-author`, `paid-exec`, `human`, `idea`).
- Write acceptance criteria, validation commands, allowed paths, and
  stopping rules.
- Route packets to the appropriate execution role (Implementer, Refactoring,
  Research, etc.).
- Identify missing context, unresolved assumptions, and dependency gaps
  before dispatch.
- Track packet DAG dependencies and signal when blocked packets become
  dispatchable.

**Authority:**
- Owns packet decomposition and the packet DAG.
- May split, merge, or reclassify packets within the approved Mission scope.
- May reject a Mission as un-decomposable (returns it to Kitty/Jacob with
  a structured gap report).
- Cannot implement, review, verify, or make architectural rulings.

**Inputs:**
- Approved Missions from Kitty.
- Research findings from Research team.
- Architectural constraints from Chief Architect.
- Stale-packet signals from Knowledge Curator (duplicate or superseded work).

**Outputs:**
- Packet briefs with: objective, allowed paths, validation commands,
  model class, dependencies, stopping rules, acceptance evidence plan.
- The packet DAG.
- Gap reports for un-decomposable Missions.

**Escalation rules:**
- Escalates to Chief Architect when a packet's scope touches an architectural
  boundary not yet decided.
- Escalates to Research when a decomposition requires answering an
  unresolved question.
- Escalates to Jacob when a Mission's acceptance criteria cannot be made
  falsifiable.

**Required evidence:**
- Every dispatched packet must meet the Free-Model Packet Standard
  (`docs/FREE_MODEL_PACKET_STANDARD.md`) when classified as `free-exec`
  or `paid-author`.
- The gate must be verified to fail on the unmodified tree (Rule G2).
- Dependency gaps must be recorded as blocking with a named dependency.

**Communication protocol:**
- Writes to: the packet store, the DAG, gap reports.
- Reads from: approved Missions, Research findings, architectural decisions,
  the current packet store (to detect duplicates).
- Does not communicate directly with Implementer during execution. The
  packet brief is the complete interface.

**Parallel work:** Multiple Planners may decompose independent Missions
concurrently. Planner and Research may work in parallel when the Research
question is defined and does not block decomposition of unrelated packets.

**Serialization required:** Two Planners must not decompose the same Mission
simultaneously. Planner must wait for Chief Architect when a packet touches
an undecided architectural boundary.

---

### 3. Research

**Responsibilities:**
- Answer concrete questions that block planning or implementation.
- Benchmark candidate technologies against defined criteria.
- Validate or invalidate assumptions recorded in the Mission.
- Produce decision-support artifacts: comparison tables, benchmark results,
  API fitness reports.
- Archive research findings as durable evidence, not chat memory.

**Authority:**
- May investigate any source code, dependency, API, or external system.
- May run benchmarks, write exploration scripts, and clone dependencies
  into `.slim/clonedeps/repos/`.
- Cannot implement production code, open PRs, modify frozen specs, or
  make architectural decisions.
- Cannot declare an investigation complete without evidence.

**Inputs:**
- Concrete research questions from Planner or Chief Architect.
- Benchmark criteria from Performance or Planner.
- Assumption validation requests from the Mission's `assumptions[]` list.

**Outputs:**
- Structured research notes (under `docs/research/`).
- Benchmark reports with reproducible methodology.
- Assumption validation records (validated / invalidated / unverifiable).
- Technology recommendation with tradeoff analysis.

**Escalation rules:**
- Escalates to Chief Architect when findings imply a structural change.
- Escalates to Planner when findings require packet re-decomposition.
- Escalates to Jacob when an investigation requires spending money or
  accessing credentials.

**Required evidence:**
- Every finding must cite the source (code reference, API response,
  benchmark run, external documentation).
- Benchmark methodology must be reproducible.
- Assumption classification: validated by evidence, invalidated by evidence,
  or unverifiable with the current tooling.

**Communication protocol:**
- Writes to: `docs/research/`, the Mission's evidence bundle.
- Reads from: Planner questions, Chief Architect questions, source code,
  external documentation and APIs.
- Does not direct other roles. Research findings are evidence; other roles
  decide what to do with them.

**Parallel work:** All Research investigations are parallel by default, as
long as they are scoped to different questions. Multiple Research workers
may investigate the same question from different angles and produce a
synthesized finding.

**Serialization required:** When two investigations produce conflicting
findings, a synthesis pass is required before the finding is consumed by
Planner. When an investigation's output is needed by a Planner actively
decomposing a dependent packet, the Planner blocks until Research completes.

---

### 4. Reviewer

**Responsibilities:**
- Independently verify that an Implementer's output satisfies the packet
  contract.
- Read the diff, changed paths, scope violations, and test results.
- Record a structured verdict: `approve`, `reject` (fixable), `reject`
  (architectural), or `needs_human`.
- Verify that the validation gate was run and passed on the final code.
- Confirm the reviewer is not the same worker identity that implemented.

**Authority:**
- May approve or reject a packet attempt.
- May demand additional tests, documentation, or structural changes
  within the packet's scope.
- May escalate to Chief Architect on architectural grounds.
- May escalate to Security when the diff touches auth, secrets, or
  permission boundaries.
- Cannot implement, modify the packet contract, or override Planner's
  model-class decision.
- Cannot approve its own work or the work of the same worker identity.

**Inputs:**
- The packet brief and its acceptance criteria.
- The implementation artifact: branch, diff, changed paths, commit SHAs.
- Validation gate results (exit code, test output).
- The worker's final report.
- Evidence of scope: scope snapshot from the runner, scope violations.

**Outputs:**
- Structured review verdict with: verdict, specific findings, required
  remediation actions, and the exact SHA reviewed.
- Escalation records (architectural, security, evidence-gap).

**Escalation rules:**
- Architectural violation → Chief Architect.
- Security concern → Security.
- Missing or falsified evidence → Operations (fails the packet; does not
  attempt repair).
- Unclear acceptance criteria → Planner (block the packet until criteria
  are clarified).
- Repeated rejections (3 or more on the same concern) → Chief Architect
  with the full review history.

**Required evidence:**
- The review must bind to the exact implementation HEAD SHA and diff digest.
  Drift between review and implementation is rejected.
- Scope violations must cite the specific file and the specific rule.
- A rejection must state what would make it acceptable, not just what is
  wrong.
- A `needs_human` verdict must explain why automated review is insufficient.

**Communication protocol:**
- Writes to: the attempt's review record, the PR (if published).
- Reads from: packet brief, implementation artifact, validation results,
  worker final report.
- Never communicates with the Implementer directly during review. The
  review record is the complete interface.

**Parallel work:** Multiple Reviewers may review different packets
concurrently. Reviewer and Implementer may work in parallel on different
packets.

**Serialization required:** One packet must not be reviewed by two
Reviewers simultaneously (one verdict, one owner). Reviewer cannot review
a packet while the Implementer is still modifying the same branch.

---

### 5. Implementer

**Responsibilities:**
- Execute a packet in an isolated worktree.
- Edit, test, commit, and push within the packet's allowed paths.
- Report honest outcomes: success with evidence, honest failure,
  provider exhaustion, or blocked.
- Follow the packet's stopping rules exactly.
- Hand off only on clean failure (no partial work survives into the
  next attempt).

**Authority:**
- May modify any file within the packet's `allowed_paths`.
- May run validation commands, tests, and build steps.
- May commit and push to the Builder-owned branch.
- May open or update a draft PR within the packet's scope.
- May NOT modify frozen specs, architectural documents, or files outside
  `allowed_paths`.
- May NOT merge, approve, or decide acceptance.
- May NOT change the packet contract, re-interpret acceptance criteria,
  or expand scope.

**Inputs:**
- The packet brief (complete: objective, allowed paths, validation commands,
  stopping rules, model class).
- The isolated worktree provisioned at the correct base SHA.
- The worker brief (compiled context: relevant code, tests, conventions).

**Outputs:**
- Changed code on the Builder-owned branch.
- Worker final report: outcome, changed paths, test results, model used,
  attempt metadata.
- Honest failure evidence (for exhausted/blocked/cancelled).

**Escalation rules:**
- Cannot proceed cleanly within packet scope → stop, report `blocked`,
  preserve worktree. Do not guess.
- Provider exhaustion → report `paused`, preserve partial evidence.
- Architectural concern discovered during implementation → report in
  final report; Reviewer escalates if warranted.
- Packet contract is unclear or contradictory → stop, report `blocked`,
  do not re-interpret.

**Required evidence:**
- Changed paths must stay within `allowed_paths`.
- Validation command exit code.
- Scope snapshot (before/after file list).
- Model and provider used for the attempt.

**Communication protocol:**
- Writes to: the implementation branch, the worker final report.
- Reads from: the packet brief, the compiled worker brief.
- Does not communicate with Planner at execution time. The packet brief
  is the complete instruction.

**Parallel work:** Multiple Implementers may work on different packets
concurrently, as long as their allowed paths are disjoint. Overlapping
allowed paths require serialization (two Implementers modifying the same
file must serialize).

**Serialization required:** Same packet, same file, same branch. Packets
that declare overlapping `allowed_paths` and belong to the same initiative
phase must serialize their implementers. Packets that declare dependencies
in the DAG must serialize in dependency order.

---

### 6. Refactoring Team

**Responsibilities:**
- Improve code structure without changing behavior.
- Reduce complexity, deduplicate, and clarify naming.
- Ensure refactored code still passes the existing test suite.
- Record before/after complexity metrics.

**Authority:**
- May restructure code within the allowed paths and scope.
- May rename, extract, inline, and reorder within a single module's
  boundaries.
- May not change behavior observable by tests.
- May not cross module boundaries without Chief Architect approval.
- May not refactor and add features in the same packet.

**Inputs:**
- Complexity audit findings from QA or Performance.
- Refactoring packets from Planner.
- The current test suite (as the behavior oracle).

**Outputs:**
- Refactored code with identical test results.
- Before/after metrics: line count, cyclomatic complexity, dependency count.
- A structured report confirming no test regressions.

**Escalation rules:**
- Refactoring crosses a module boundary → Chief Architect for structural
  approval.
- Test suite fails on refactored code → stop, revert, report. Do not
  "fix" the tests.
- Discovered bug during refactoring → record in final report, do not fix
  (separate packet).

**Required evidence:**
- Identical test results before and after (same exit code, same assertions).
- Scope snapshot proving no changes outside allowed paths.
- Complexity delta (must decrease or stay neutral).

**Communication protocol:**
- Writes to: the implementation branch, the refactoring report with metrics.
- Reads from: complexity audit findings, the test suite, the packet brief.
- Same packet-discipline as Implementer.

**Parallel work:** Independent modules only. Two Refactoring workers must
not touch the same module simultaneously.

**Serialization required:** Same module, same file. Refactoring and
implementation on the same module must serialize, with Refactoring
typically first (clean before build).

---

### 7. Documentation Team

**Responsibilities:**
- Write and maintain architectural documentation, ADRs, runbooks, and
  codebase maps.
- Update docs when implementation changes semantics that docs describe.
- Keep CODEBASE_MAP.md accurate against the live repository structure.
- Maintain `docs/BLUEPRINT.md`, `docs/ALIGNMENT_MAP.md`, and other
  planning-adjacent docs.

**Authority:**
- May create and edit documentation files.
- May request architectural clarification from Chief Architect.
- May not change code, tests, or configuration.
- May not invent architectural decisions.

**Inputs:**
- Implementation artifacts (to document what was built).
- Architectural decisions from Chief Architect.
- Research findings from Research.
- Operations runbooks and incident postmortems.

**Outputs:**
- Updated or new documentation files.
- Codebase map accuracy reports.
- Documentation gap reports.

**Escalation rules:**
- Missing architectural context for documentation → Chief Architect.
- Contradictory documentation discovered → record the contradiction,
  escalate to Planner for prioritization.
- Docs contradict live code → record the gap, escalate to Planner.

**Required evidence:**
- Updated documentation must cite the source of truth it reflects
  (ADR number, commit SHA, research finding reference).
- Codebase map claims must be verifiable against the file tree.

**Communication protocol:**
- Writes to: `docs/` directory.
- Reads from: implementation artifacts, architectural decisions, research
  findings, the live repository file tree.

**Parallel work:** Independent documents. Two Documentation workers on the
same document must serialize.

**Serialization required:** Same document. Documentation that covers an
in-progress implementation must wait for the implementation to land.

---

### 8. QA

**Responsibilities:**
- Author and maintain tests that detect regressions.
- Own the falsifiability of validation gates.
- Verify that gates fail on broken code and pass on correct code.
- Audit test coverage and report uncovered critical paths.
- Run regression suites and report pass/fail with exact counts.

**Authority:**
- May write tests and test infrastructure.
- May reject a packet's validation gate as non-falsifiable (with evidence).
- May block a packet from `free-exec` if its gate cannot be verified
  falsifiable.
- May not change production code or fix bugs discovered by tests.

**Inputs:**
- Packet acceptance criteria from Planner.
- Existing test suite and coverage reports.
- Bug reports and regression scenarios from Operations.

**Outputs:**
- Test files and test infrastructure.
- Falsifiability verification records.
- Test coverage gap reports.
- Regression run results.

**Escalation rules:**
- Gate cannot be made falsifiable → Planner (packet cannot be `free-exec`).
- Test uncovers a bug → record, do not fix; escalate to Planner for a new
  packet.
- Test infrastructure is broken → Operations.

**Required evidence:**
- Falsifiability proof: the gate must fail on the unmodified tree (Rule G2).
- Test pass/fail counts with exact numbers.
- Coverage reports with uncovered paths identified.

**Communication protocol:**
- Writes to: test files, validation records, gap reports.
- Reads from: packet acceptance criteria, existing test suite, coverage data.
- Does not direct Implementer to fix code.

**Parallel work:** Tests for different modules. Tests and implementation
on the same module should not run in parallel — the Implementation should
land before QA verifies the new behavior.

**Serialization required:** Same test file. QA and Implementation touching
the same test file (e.g., Implementer adding a test per Rule G4) must
serialize.

---

### 9. Browser Verification

**Responsibilities:**
- Verify that UI claims are backed by browser-observed evidence (ADR 0035).
- Take screenshots of components and flows at defined states.
- Run Playwright or browser-use automation suites.
- Record live verification evidence: what was seen, when, on what page.
- Contradict claims of "working" UI without browser evidence.

**Authority:**
- May reject any UI claim that lacks browser evidence, regardless of
  code review or test status.
- May require re-verification when the visual surface changes.
- May access the running app, Open WebUI, and kitty-chat for verification.
- May not change UI code, fix visual bugs, or make design decisions.

**Inputs:**
- UI change packets from Planner.
- The implementation artifact (branch, PR).
- Access to the running application.
- Visual acceptance criteria from the packet.

**Outputs:**
- Browser verification record: screenshots, timestamps, observed state,
  verdict (pass / fail / partial).
- Playwright trace files.
- Evidence that contradicts a UI claim.

**Escalation rules:**
- Observed behavior contradicts claim → reject with browser evidence
  attached.
- Cannot verify because the app won't start → Operations.
- Visual rendering is correct but looks wrong → UI/UX (design concern,
  not correctness).

**Required evidence:**
- A screenshot or trace is required — code inspection is not sufficient.
- The verification must record: what was viewed, at what URL/route, at
  what timestamp, and the observed state.
- "Could not verify" is a distinct state from "verified as correct."

**Communication protocol:**
- Writes to: the evidence bundle, verification records.
- Reads from: UI change packets, the running application.
- Does not direct Implementer to change code.

**Parallel work:** Different UI surfaces. Multiple verifiers may verify
different pages concurrently.

**Serialization required:** Same UI surface. Verification must wait for
implementation to complete and the app to be running.

---

### 10. Release Manager

**Responsibilities:**
- Determine merge eligibility for completed packets.
- Enforce the auto-merge boundary rules from ADR 0021.
- Coordinate publication: merge, tag, CHANGELOG, and deployment
  notification.
- Verify that all pre-merge gates passed: CI green, review approved,
  browser verified (for UI), security cleared (for sensitive paths).
- Reject merge when a required gate is absent.

**Authority:**
- May merge eligible packets into main.
- May reject a merge even when all individual gates pass (e.g., merge
  conflict, CI instability, release freeze).
- May trigger auto-revert per ADR 0018 tripwire rules.
- May not implement, review, test, or modify code.

**Inputs:**
- Completed packet records with: implementation SHA, review verdict,
  validation results, browser verification, security clearance.
- Current CI status on main and on the feature branch.
- Merge eligibility rules from the packet's classification.

**Outputs:**
- Merge records.
- CHANGELOG entries.
- Release tags.
- Revert records.

**Escalation rules:**
- Merge conflict that requires structural resolution → Chief Architect.
- Auto-revert triggered → Operations (investigate root cause), Planner
  (re-prioritize).
- All gates passed but merge feels risky → Jacob (final decision for
  high-risk merges).

**Required evidence:**
- Every required gate must produce a durable record before merge.
- Merge must bind to a specific base SHA and result SHA.
- Auto-revert evidence must include: what was reverted, the tripwire that
  fired, and the state after revert.

**Communication protocol:**
- Writes to: the release rail, CHANGELOG, version tags.
- Reads from: completed packet records, CI status, merge eligibility rules.
- Only role authorized to merge.

**Parallel work:** Release Manager may process multiple eligible packets
concurrently (different branches, no conflicts).

**Serialization required:** Merge operations to the same target branch
(main) must serialize. Release Manager must not merge while CI is running
on main.

---

### 11. Knowledge Curator

**Responsibilities:**
- Maintain the KB (`~/kb/`) as a durable, searchable knowledge store.
- Write durable findings to `~/kb/wiki/` after sessions produce reusable
  knowledge.
- Record corrections in `~/kb/corrections/` when Jacob corrects a
  generalizable pattern.
- Update `~/kb/NOW.md` and `~/kb/INDEX.md` as work progresses.
- Identify stale, superseded, or contradictory KB entries.
- Detect when a planned packet duplicates prior research or learned
  corrections.

**Authority:**
- May write to the KB.
- May flag KB entries as stale or superseded.
- May warn Planner when a packet duplicates known-bad approaches.
- May not delete KB entries (only mark them).
- May not make architectural or implementation decisions.

**Inputs:**
- Session evidence: findings, corrections, patterns learned.
- Research outputs from Research team.
- Post-mortems and incident reports from Operations.
- Architectural decisions (to cross-reference with KB).

**Outputs:**
- KB wiki entries (`~/kb/wiki/YYYY-MM-DD-slug.md`).
- KB corrections (`~/kb/corrections/`).
- Updated `~/kb/INDEX.md` and `~/kb/NOW.md`.
- Staleness and duplication warnings to Planner.

**Escalation rules:**
- KB entry contradicts a live ADR → Chief Architect (the KB may be stale).
- Correction implies a systematic pattern → Planner (new packet to
  address the pattern).

**Required evidence:**
- KB entries must cite source evidence (session, commit, research finding).
- Staleness flags must explain why the entry is stale.
- Duplication warnings must name the existing entry.

**Communication protocol:**
- Writes to: `~/kb/`.
- Reads from: session evidence, research outputs, post-mortems, ADRs.
- Provides signals, not commands, to Planner.

**Parallel work:** Independent KB entries. This role is mostly parallel
with all other roles — it observes and records.

**Serialization required:** Same KB file. `INDEX.md` and `NOW.md` require
serialization (single-writer files).

---

### 12. Operations

**Responsibilities:**
- Maintain Kitty runtime health: Gateway, LiteLLM, Open WebUI, Builder.
- Run `./kitty doctor`, `./kitty status`, and `./kitty builder initiative
  doctor`.
- Monitor CI health, failed builds, and infrastructure issues.
- Handle provider exhaustion, rate limits, and availability pauses.
- Investigate infrastructure failures (crash, kill, timeout, orphaned
  worktrees).
- Document runbooks for common operational scenarios.

**Authority:**
- May start, stop, or restart Kitty services.
- May run recovery commands: `./kitty builder queue recover`,
  `operator-release`, `operator-cancel`.
- May diagnose but not modify application code.
- May provision and destroy worktrees, restart workers.
- May not merge, review, implement, or make product decisions.

**Inputs:**
- Runtime health data from doctor, status, and CI.
- Incident reports from any role that encounters infrastructure failure.
- Provider availability signals.

**Outputs:**
- Health reports.
- Incident records and root cause analysis.
- Recovery actions recorded in the queue.
- Updated runbooks.

**Escalation rules:**
- Repeated infrastructure failure → Jacob (may need external resources or
  credential changes).
- CI consistently red → Jacob (may indicate a systemic issue beyond
  operational scope).
- Provider unavailable for > 1 hour → Jacob (decide whether to use paid
  fallback).

**Required evidence:**
- Incident records must include: what was observed, when, what was tried,
  what resolved it.
- Health reports must distinguish `unavailable`, `degraded`, and `healthy`.
- Recovery actions must be recorded in the queue event log.

**Communication protocol:**
- Writes to: health reports, incident records, runbooks.
- Reads from: runtime probes, CI output, provider status, queue state.
- May communicate with any role about infrastructure availability.

**Parallel work:** Operations tasks that are independent services or probes.

**Serialization required:** Recovery operations on the same queue task.
Two operators must not `operator-release` the same task.

---

### 13. Security

**Responsibilities:**
- Audit code changes for injection vulnerabilities, auth/authz gaps,
  secrets exposure, and sandbox escapes.
- Review diffs that touch auth, secrets, permissions, CI workflows,
  or dependency changes.
- Verify that credential isolation is intact in worker environments.
- Scan for secrets in code, logs, environment variables, and committed
  files.

**Authority:**
- May block any packet that introduces a security vulnerability.
- May reject a merge even when all other gates pass (security veto).
- May demand remediation before allowing any further work on the same
  branch.
- May not implement fixes, make architectural decisions, or modify
  non-security code.

**Inputs:**
- Diffs flagged by Reviewer or Release Manager (auth, secrets, CI,
  dependencies, permissions).
- Packet briefs that touch security-sensitive paths.
- The full diff for targeted review.

**Outputs:**
- Security audit record: findings, severity, required remediation.
- Veto records with specific vulnerability citation.
- Security clearance for clean diffs.

**Escalation rules:**
- Active vulnerability discovered → Jacob immediately.
- Credential exposure in committed code → Jacob immediately, block the
  branch.
- Architectural security concern → Chief Architect.

**Required evidence:**
- Every vulnerability finding must cite the vulnerable code path, the
  attack vector, and the required remediation.
- Security clearance must be explicit: "reviewed, no vulnerabilities found"
  or "reviewed, findings attached."

**Communication protocol:**
- Writes to: security audit records, veto records.
- Reads from: flagged diffs, packet briefs.
- Veto cannot be overridden by any role except Jacob.

**Parallel work:** Different diffs, different branches. Security review of
pending merge should not be parallel with Release Manager's merge on the
same branch.

**Serialization required:** Same diff. Security review must complete before
merge for any packet touching security-sensitive paths.

---

### 14. Performance

**Responsibilities:**
- Audit hot paths for N+1 queries, overfetching, wasted recomputation,
  and blocking operations.
- Profile performance regressions introduced by new code.
- Recommend optimizations with before/after benchmarks.
- Identify memory leaks, unbounded growth, and resource exhaustion
  patterns.

**Authority:**
- May profile, benchmark, and instrument any code path.
- May flag a packet as introducing an unacceptable performance regression.
- May recommend optimization strategies.
- May not implement optimizations, change production code, or modify
  the packet's scope.

**Inputs:**
- Performance audit requests from Planner or Chief Architect.
- New implementation artifacts (to profile before merge).
- Performance baseline data.

**Outputs:**
- Performance audit records: measured metric, baseline, observed delta,
  recommended action.
- Benchmark reports with methodology.
- Hot-path identification and profiling data.

**Escalation rules:**
- Performance regression that blocks merge → Release Manager (flag the
  packet, do not block unrelated packets).
- Optimization requires architectural change → Chief Architect.
- Performance issue is a systematic pattern → Planner (new packet).

**Required evidence:**
- Every performance claim must cite measured data, not intuition.
- Benchmark methodology must be described and reproducible.
- "Fast enough" must be defined against a concrete threshold.

**Communication protocol:**
- Writes to: performance audit records, benchmark reports.
- Reads from: running system, profiled code, performance baselines.

**Parallel work:** Different code paths, different benchmarks. Multiple
performance audits may run concurrently on disjoint code paths.

**Serialization required:** Same code path — profiling and optimization must
serialize. Performance audit of a branch should complete before merge.

---

### 15. UI/UX

**Responsibilities:**
- Evaluate UI components for correctness, accessibility, and visual
  consistency.
- Verify that UX flows are coherent and follow established patterns.
- Review UI diffs for accessibility violations, broken layouts, and
  color/contrast issues.
- Flag design quality issues: confusing copy, inconsistent spacing,
  missing states (loading, empty, error).

**Authority:**
- May flag UI issues as blocking for UX/copy/visual product judgment
  (ADR 0021 auto-merge exclusion).
- May recommend design improvements.
- May not implement UI code, make layout decisions for the Implementer,
  or approve purely functional correctness.

**Inputs:**
- UI change packets and their visual acceptance criteria.
- Browser verification evidence (screenshots, traces).
- Design system reference: color tokens, spacing scale, typography scale,
  component library.

**Outputs:**
- UI audit record: observed issues, screenshots with annotations,
  severity classification, recommended fixes.
- Accessibility violation report.

**Escalation rules:**
- Visual quality prevents acceptable user experience → Release Manager
  (block merge for UX judgment).
- Design system inconsistency → Chief Architect (if systemic) or Planner
  (packet to fix).

**Required evidence:**
- Screenshots with specific issues annotated.
- Accessibility violations must cite the WCAG criterion violated.
- "Looks wrong" must be articulated: what is wrong, what would be right.

**Communication protocol:**
- Writes to: UI audit records.
- Reads from: browser verification evidence, design system docs, UI diffs.

**Parallel work:** Different UI surfaces.

**Serialization required:** Same UI surface. UI audit should follow browser
verification for the same surface.

---

### 16. Image Team

**Responsibilities:**
- Generate images through ComfyUI or RunPod-backed pipelines.
- Validate image artifacts: format, dimensions, file integrity.
- Verify media delivery: ready image artifact accessible at a durable path.
- Handle generation failures, credit exhaustion, and provider errors.
- Maintain the image generation skill (`image-gen`) and its parameters.

**Authority:**
- May generate images using approved providers and credentials.
- May validate image artifacts.
- May not spend money without explicit authorization.
- May not modify image generation pipeline code, change providers without
  approval, or make visual design decisions.

**Inputs:**
- Image generation requests with defined parameters (prompt, dimensions,
  model, style).
- Credential availability and provider status.
- Quality constraints.

**Outputs:**
- Generated image artifact at a durable path.
- Media validation receipt: format, dimensions, checksum.
- Generation metadata: provider, model, cost, time.

**Escalation rules:**
- Provider unavailable or credits exhausted → Operations.
- Generation quality is consistently poor → Planner (research needed on
  prompt/model).
- Credential missing or expired → Jacob.

**Required evidence:**
- Generated image must be validated: file exists, format matches, dimensions
  match, not corrupt.
- Cost must be recorded against the credential ledger.
- Generation failure must distinguish provider error from invalid parameters
  from credit exhaustion.

**Communication protocol:**
- Writes to: image artifacts, validation receipts, generation logs.
- Reads from: generation requests, credential status, provider status.

**Parallel work:** Independent generation requests. Multiple images may be
generated concurrently on independent providers.

**Serialization required:** Same provider with a concurrency limit. Image
generation and validation are sequential for the same image.

---

## Coordination Model

### Artifact Ownership

Each artifact has exactly one writing role at a time:

| Artifact | Owner (writes) | Consumers (read) |
|---|---|---|
| Packet brief | Planner | Implementer, Reviewer, QA, Release Manager |
| Implementation branch | Implementer | Reviewer, QA, Browser Verification, Security |
| Review verdict | Reviewer | Release Manager, Implementer (for repair) |
| Architectural decision | Chief Architect | All roles |
| Research finding | Research | Planner, Chief Architect, Knowledge Curator |
| Test file | QA (primary), Implementer (G4 only) | All roles |
| Browser evidence | Browser Verification | UI/UX, Release Manager, Reviewer |
| KB entry | Knowledge Curator | All roles |
| Merge record | Release Manager | All roles |
| Health report | Operations | All roles |

### The Escalation Ladder

```
Jacob
  ├── Chief Architect
  │     ├── Planner
  │     │     ├── Implementer
  │     │     ├── Refactoring Team
  │     │     └── Image Team
  │     ├── Reviewer
  │     ├── Security
  │     └── Performance
  ├── Operations
  ├── Release Manager
  ├── Knowledge Curator
  ├── QA
  ├── Browser Verification
  ├── UI/UX
  ├── Documentation Team
  └── Research
```

### Communication Through Artifacts

Roles do not chat with each other. They write durable artifacts and read
durable artifacts. The artifact is the message. A role discovers that it
has work by observing a new or updated artifact in a state that requires
its action.

Examples:
- Implementer discovers work: a packet brief appears with status `queued`
  and `allowed_paths` disjoint from any in-progress implementer.
- Reviewer discovers work: an implementation final report appears with
  outcome `completed`.
- Release Manager discovers work: a packet's gates all show `passed`.
- Operations discovers work: a health probe returns `degraded` or a
  provider reports `exhausted`.

### Parallel Work Rules

Parallel work is the default when:
1. The artifacts touched are disjoint (different packets, different files,
   different documents).
2. The roles are different (no two workers of the same role on the same
   artifact).
3. No dependency edge exists in the packet DAG between the artifacts.

Parallel work requires serialization when:
1. Same artifact, same write role (two Implementers, same file).
2. Dependency edge exists (packet B depends on packet A's output).
3. Merge target serialization (Release Manager, main branch).
4. Review-before-merge serialization (Reviewer and Release Manager on
   the same packet).

### The Compute Governor Across Roles

The compute governor (`gateway/compute_governor.py`) gates dispatch for any
role that consumes paid tokens: Planner (paid-author packets), Reviewer
(frontier model), Implementer (paid-exec packets), Research (benchmarks
that consume credits).

Every paid dispatch must declare a concrete artifact, acceptance tests,
allowed scope, exclusions, risk class, and a stopping condition. One pass
per unchanged `(task_type, subject_ref, head_sha)`. The governor is
role-agnostic — it cares about the artifact and the cost, not which role
is spending.

---

## Operational Notes

### This Is Not a Workflow Engine

A pipeline says: step 1 → step 2 → step 3. This organization says:
roles observe artifacts and act when their input conditions are met.
Some packets need only Implementer → Reviewer → Release Manager. Others
need Planner → Research → Planner → Implementer → Reviewer → Browser
Verification → UI/UX → Release Manager. The path emerges from the packet's
requirements, not from a predefined pipeline.

### The Organization Scales Down

Not every packet needs all 16 roles. A `free-exec` packet that changes one
function in one file with a deterministic gate may only touch Planner
(write the brief), Implementer (execute), and Reviewer (verify). The other
13 roles observe the artifact, see nothing requiring their action, and
stay idle.

### The Organization Scales Horizontally

When work volume increases, add more Implementers, Reviewers, and QA
workers. The coordination model — artifact ownership + serialization
rules — prevents conflicts regardless of headcount. The Chief Architect,
Release Manager, and Operations are singletons by design (they own
serialized artifacts).

### Trust Is in Evidence, Not Identity

No role trusts another role's claim without evidence. The Reviewer trusts
the validation gate's exit code, not the Implementer's claim of passing
tests. The Release Manager trusts the review record, not the Reviewer's
assertion. Browser Verification trusts the screenshot, not the
Implementer's claim that "the UI works." This is ADR 0032 applied at the
organizational level.

---

## Relationship to Existing Architecture

This document describes an organizational model layered on top of the
existing Builder infrastructure. It does not replace:

- **ADR 0017:** The Kitty → Mission → KittyBuilder boundary. Kitty
  remains the principal agent and intent compiler.
- **ADR 0021:** Proactive execution, model classes, auto-merge boundary.
  The organization inherits these rules.
- **The queue, leases, worktrees, and attempts:** These remain the
  durable execution substrate. The organization adds role semantics on
  top of the existing `builder_queue`, `builder_attempt`, and
  `builder_runner` infrastructure.
- **The compute governor:** Budget enforcement remains per-dispatch,
  not per-role.
- **The free worker ladder:** Model routing and fallback remain governed
  by `docs/FREE_WORKERS.md`.

Implementation of this organization would require:
- A role registry mapping worker identities to roles.
- Role-aware dispatch (Planner dispatches to Implementer, not to any
  available worker).
- Artifact-based coordination signals (a role discovers work by observing
  artifacts, not by being assigned).
- Escalation routing (artifacts that require escalation are routed to the
  upstream role).
