# Next Agent Prompt — Kitty Day-to-Day Leverage Sprint

You are taking over the Kitty repository remediation sprint.

Repository: `jacob202/kitty`
Branch: `perf/due-diligence-leverage-pack`
Base: `main` at `129c5468774aba0c4df1bff48763f1b19f2d9cc8`
Verification PR: #659

DO NOT restart the audit. Continue from this branch and read:

`docs/audit/2026-08-25/LEVERAGE_REMEDIATION_HANDOFF.md`

## Already implemented

1. Durable chat lifecycle recovery N+1 removed.
2. Artifact recovery N+1 removed.
3. Lifecycle regression coverage added.
4. Coverage configuration synchronized to 73%.
5. Trivial chat fast path now bypasses MemoryGraph retrieval and enrichments.
6. Health surface domain probes now run concurrently.
7. Regression tests added for both new performance changes.

## Immediate verification

Run:

```bash
python -m pytest tests/test_context_assembler_trivial_fast_path.py tests/test_context_assembler.py tests/test_chat_lifecycle.py tests/test_health_surface.py tests/test_health_surface_parallel.py -q
python -m pytest tests/ -q --tb=short --cov=gateway --cov-report=term-missing --cov-fail-under=73
ruff check gateway/ tests/ mcp/ workers/ scripts/runpod_worker_smoke_test.py
mypy gateway/ mcp/ workers/ scripts/runpod_worker_smoke_test.py
git diff --check
git status --short --branch
```

Frontend:

```bash
cd gateway/kitty-chat
npm ci
./node_modules/.bin/vitest run
node node_modules/next/dist/bin/next build
npx playwright test
```

Do not say anything passes unless it actually ran.

## Active user-visible work: review, don't duplicate

### PR #656
Builder conversation continuity / proposal trigger.

### PR #657
Web-monitor keyword notification transition fix.

### PR #658
Web-monitor disable/delete race fix.

### PR #649
ActionQueue stranded `executing` recovery after restart.

### PR #651
Native approval -> execute -> terminal result UX.

Review these PRs and determine whether they are safe/current. Do not recreate them on this branch unless a concrete defect requires a fix.

## Next implementation priorities

1. Verify the two newly implemented performance changes.
2. Review the five active PRs above and record merge/review status.
3. Run the security baseline:

```bash
pip-audit
deptry .
bandit -c pyproject.toml -r gateway/
cd gateway/kitty-chat && npm audit --audit-level=high
```

Classify findings before changing CI policy. Do not blindly upgrade dependencies or make every audit advisory blocking.

4. Improve chat latency instrumentation using existing timing/correlation infrastructure. Measure first; do not invent p95 thresholds.
5. Improve structured logging without adding a large observability framework.
6. Investigate `/health` polling semantics separately from `/health/surface`.

## Running tally

DONE:
- [x] lifecycle N+1
- [x] artifact N+1
- [x] lifecycle regression test
- [x] coverage drift
- [x] trivial context fast path
- [x] health surface concurrency
- [x] tests added for new optimizations

NEEDS VERIFICATION:
- [ ] focused Python tests
- [ ] full Python suite / 73% coverage
- [ ] Ruff
- [ ] mypy
- [ ] frontend Vitest/build/Playwright
- [ ] security audits

EXTERNAL / HUMAN DECISION:
- [ ] review/merge PR #656
- [ ] review/merge PR #657
- [ ] review/merge PR #658
- [ ] review/merge PR #649
- [ ] review/merge PR #651

BLOCKED:
If a task cannot be completed, record exactly:
- TASK
- WHY
- WHAT WAS ATTEMPTED
- EXACT ACCESS/CONTEXT NEEDED
- EXACT NEXT COMMAND/ACTION

## Current environment limitation already established

This agent environment cannot clone GitHub because outbound DNS/network access is unavailable. GitHub Actions for PR #659 produced a fully skipped `Tests` run rather than executable CI evidence. A real checkout/runtime with dependencies is therefore required for final verification.

## Goal

Make Kitty feel faster, more reliable, and less annoying in everyday use. Favor small changes with measurable user-facing effects over architectural cleanup for its own sake.
