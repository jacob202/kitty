# Agent Workflow Telemetry and Historical Backfill Implementation Plan

**Goal:** Make engineering waste measurable from authoritative evidence so later policy changes can be evaluated by launch count, retries, elapsed time, validation/review cycles, cleanup state, and token/provider provenance.

**Architecture:** Build a read-only derived reporting layer over existing Builder SQLite events/runs/attempts, KX state, Git/GitHub, CI metrics, session-end receipts, and local agent session logs. Do not introduce another execution authority or claim that token counts equal dollars.

**Initial baseline already established:** historical Builder attempt outcomes were dominated by failed/crashed attempts, infrastructure failures were common, many run rows lacked provider/model provenance, and current effectiveness policy cannot populate several of its own waste metrics.

## Task 1: Define a stable engineering-execution receipt schema

**Files:**
- Add: `docs/contracts/ENGINEERING_EXECUTION_RECEIPT.md`
- Add: `tests/test_engineering_efficiency_report.py`
- Add later in Task 2: `scripts/engineering_efficiency_report.py`

**Step 1:** Define normalized fields for outcome/task/PR identity, parent session, child agent/run, model/provider, start/end timestamps, base/candidate SHA, changed paths, validation commands/results, review result, CI timings, blocker fingerprint, retry reason, KX wait, worktree disposition, and source provenance.

**Step 2:** Define token fields by source semantics: input, output, cache-read, cache-write, cumulative/session-total, and unknown. Never sum cumulative snapshots as if they were deltas.

**Step 3:** Define `cost_cad` as nullable and source-bound. Populate it only from a provider/spend ledger receipt; estimates remain separately labeled estimates.

**Step 4:** Add schema-validation tests with synthetic receipts before implementing collectors.

## Task 2: Build the read-only report from existing sources

**Files:**
- Add: `scripts/engineering_efficiency_report.py`
- Add: `tests/test_engineering_efficiency_report.py`
- Reuse read-only: `data/kittybuilder/builder_queue.db`
- Reuse read-only: Git/GitHub CLI evidence

**Step 1:** Read Builder `runs`, `packet_attempts`, `events`, tasks, and initiative state without mutating the queue DB.

**Step 2:** Join Git worktree/branch state and GitHub PR/check timing by durable task/branch/SHA where a deterministic link exists. Leave ambiguous joins explicitly unmatched.

**Step 3:** Emit JSON plus a concise terminal summary: launches, implementation attempts, infra-blocked events, retries by fingerprint, median/percentile elapsed time, review cycles, PR lifetime, slowest check, and current workspace disposition counts.

**Step 4:** Add fixture tests proving repeated provider outages and stale-attempt reconciliation are classified as infrastructure, not implementation-quality failures.

**Step 5:** Add `--since`, `--until`, `--task`, `--pr`, and `--json` filters so the report is useful both for one incident and for trend analysis.

## Task 3: Backfill model/session topology without spending model calls

**Files:**
- Modify: `scripts/engineering_efficiency_report.py`
- Add fixtures under: `tests/fixtures/engineering_efficiency/`
- Modify: `tests/test_engineering_efficiency_report.py`

**Step 1:** Parse local Codex/Claude session records only where the format exposes deterministic session id, parent/child relationship, model, timestamps, and token counters.

**Step 2:** Preserve the raw source name and counter semantics on every normalized token field. Unsupported/malformed records become `unknown`, not zero.

**Step 3:** Reconstruct child fan-out and nested-agent depth so a task can show how many agents were launched to deliver one outcome.

**Step 4:** Add regression fixtures for cumulative counters so backfill cannot double-count the same session total across multiple snapshots.

**Step 5:** Do not invoke any external model/provider to perform the backfill.

## Task 4: Wire currently-null effectiveness metrics to real evidence

**Files:**
- Modify: `gateway/builder_run.py`
- Modify: `config/builder_effectiveness.json` only if threshold naming needs clarification
- Modify: `tests/test_builder_run.py`

**Step 1:** Populate `reset_recovery_events` from recorded recovery/reconciliation events and `repeated_systemic_blocker_count` from stable infrastructure blocker fingerprints.

**Step 2:** Populate worker/reviewer token fields only when the current run receipt provides compatible delta-style usage; otherwise leave them null and explain why.

**Step 3:** Keep missing telemetry visible. Do not convert unknown data to zero merely to make the effectiveness guard pass.

**Step 4:** Add tests proving the guard pauses when the same systemic blocker crosses its configured threshold and does not pause on distinct unrelated blockers.

## Task 5: Establish before/after engineering efficiency baselines

**Files:**
- Add: `docs/audit/ENGINEERING_EFFICIENCY_BASELINE_2026-09-09.md`
- Modify: `scripts/engineering_efficiency_report.py`

**Step 1:** Generate a historical baseline for the largest trustworthy window available from existing records and separately label periods known to predate current fixes.

**Step 2:** Capture current counts for registered worktrees, local branches, open PRs, Builder active/paused state, and recent PR/test latency.

**Step 3:** Define comparison metrics for subsequent plans: worker dispatches per accepted outcome, infrastructure dispatches per outcome, median retries, active worktree count, cleanup lag, PR lifetime, slowest-check time, and fast-suite time.

**Step 4:** Document uncertainty explicitly: historical failure rate is not presented as the current rate after admission/provider fixes.

## Acceptance evidence

- One command can explain a task/PR timeline from launch through cleanup using authoritative IDs and SHAs.
- The report distinguishes infrastructure failure, implementation failure, review change request, cancellation, and successful delivery.
- Parent/child fan-out is visible where local session evidence supports it.
- Repeated blocker counts feed Builder effectiveness policy from actual events.
- Unknown model/token/cost provenance stays unknown instead of being guessed.
- Historical baseline and current snapshot are clearly separated so improvements can be measured honestly.

## Non-goals

Do not build a new operational database in the first slice. Do not upload private session logs to an external service. Do not estimate dollar spend from token counts without authoritative prices/receipts. Do not make telemetry collection itself a reason to launch more agents. Do not treat missing historical provenance as evidence of zero usage.
