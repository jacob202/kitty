# Kitty Test Suite Hardening — 2026-08-23

## Outcome

This effort changed the test system, not just its documentation. The suite is now organized around regression-detection value per second:

- **FAST REQUIRED** — cheap hermetic behavior, API, persistence, policy, and error-contract tests.
- **INTEGRATION REQUIRED** — hermetic tests whose contract genuinely requires real subprocess, git/worktree, lifecycle, or orchestration behavior.
- **BROWSER REQUIRED** — critical user-visible journeys that lower-level tests cannot prove.
- **LIVE ACCEPTANCE** — real provider/GPU/GitHub/runtime evidence, explicitly authorized and never substituted with mocked unit tests.

FAST and INTEGRATION remain mandatory for code changes. GitHub Actions runs them as separate required jobs so the latency split cannot silently reduce required coverage.

## Baseline

Three consecutive Python baseline runs before hardening:

| Run | Result | Wall time |
| --- | --- | ---: |
| 1 | 4,716 passed, 4 skipped | 211.48s |
| 2 | 4,716 passed, 4 skipped | 204.94s |
| 3 | 4,716 passed, 4 skipped | 204.899s |

Baseline median wall time: **204.94s**.
Frontend baseline, three consecutive Vitest runs:

| Run | Result | Wall time |
| --- | --- | ---: |
| 1 | 427 passed | 12.817s |
| 2 | 427 passed | 11.058s |
| 3 | 427 passed | 12.41s |

Baseline Vitest median: **12.41s**.

A separate Python duration profile showed the slowest 20% of testcases accounted for **85.88%** of recorded testcase time. The cost was concentrated rather than evenly distributed.

## High-confidence defects fixed

1. `tests/test_resume_script.py` paid for a real `gh pr list` network-capable subprocess even though its assertions did not validate the GitHub result. A forced failing `gh` still let the old tests pass. The rewritten tests exercise deterministic observable orientation/PR formatting instead and removed the accidental external dependency.
2. Builder timeout/heartbeat tests retained real subprocess behavior but reduced unnecessarily large timing windows.
3. Real sleeps and scheduler-speed assertions were removed from observability, Magic Route, State Composer, and MemoryGraph tests in favor of explicit clocks, thread identity, events, and bounded synchronization.
4. OpenCode adapter tests now wait on subprocess completion directly instead of manual sleep polling.
5. Python child-process test guards survive sanitized environments, closing an escape route around test network/data protections.
6. Mocked HTTP/retry tests no longer spend wall time on real retry backoff.
## Test relevance / assertion quality

The static inventory was treated as a candidate list, not a deletion list. All 28 weak/no-obvious-assertion or mock-only candidates were manually reviewed.

Material changes included:

- Telegram command tests now assert the exact awaited outbound user-visible response.
- Tutor response tests assert exact structured output and useful error diagnostics.
- Builder event broadcaster coverage now actually enters the async generator, proves registration, closes it, and proves cleanup; the old test could pass without executing the production body.
- Model-digest, extraction, and PR-review-gate tests assert meaningful failure/output semantics instead of only exception type or truthiness.
- One redundant Image Lab import-only test was removed after mutation evidence showed other dedicated modules already fail collection if that import breaks.
- One proven-dead test helper was removed.

Representative mutation checks showed the old Telegram, Builder broadcaster, and Tutor tests could pass after relevant production behavior was intentionally broken; the rewritten tests failed as intended.

Positive no-raise tests were retained when acceptance itself is the public contract. Interaction assertions were retained where the interaction is genuinely the boundary being protected.

## Required Python split

The expensive boundary set was reviewed for meaning before marking. Real git/worktree/process orchestration remains required, but runs separately from the fast developer loop.

The integration tier currently covers the real boundary portions of Builder run/loop/runner behavior, OpenCode/Claude/Codex adapters, repository context receipts, and Discord command-center process/worktree behavior. Cheap pure Builder classification and pause/resume logic remains FAST.
## CI and developer workflow changes

- `make test` is the FAST required Python loop.
- `make test-integration` runs the required process/git/lifecycle tier explicitly.
- `make test-all` recombines all required Python coverage locally, excluding only controlled-live probes.
- GitHub Actions has separate `pytest` and `pytest-integration` jobs for code scope, and `merge-gate` requires both.
- Workflow contract tests explicitly protect the integration dependency so it cannot be silently dropped later.
- Nightly profiling recombines FAST + INTEGRATION to keep a broad timing/canary view of main.
- `TESTING.md` documents executable commands and tier semantics.
- `make lint` now uses `python3.12 -m ruff`, so it works from isolated worktrees instead of depending on a canonical-checkout `./venv` path.

The FAST split is a latency optimization, not a reduction in required CI evidence.

## Reconciled parallel audit

Four independently produced lanes were reconciled before final integration: original baseline/profiling, determinism/external-dependency hardening, assertion/redundancy review, and tier/command documentation.

One lane originally concluded that a separate Python integration tier was not justified. That conclusion was superseded after reconciliation with the measured duration profile and Builder/process contract evidence: a durable set of real git/subprocess/lifecycle tests consumed roughly half the old Python wall time while protecting boundaries that should not be mocked away. The final architecture therefore keeps those tests required but moves them into a parallel CI lane.

The authoritative reconciliation package is preserved outside the repository under:

`/Users/jacobbrizinnski/Projects/kitty-command-center/test-suite-hardening-20260823/`
## Product-risk gaps that remain real

These are not closed by adding more mocked unit tests:

1. **Image Lab core browser journey** — deterministic product-surface proof of generate → select/anchor → follow-up edit is still weaker than Chat's send → stream → persist → reload trust slice. This should be added against the now-converged authority/spend model, without making paid renderer calls in ordinary CI.
2. **Image Lab real compute lifecycle** — real renderer/GPU execution, provenance, cost settlement, output cleanup, and recovery are LIVE ACCEPTANCE evidence.
3. **Builder real mission proof** — queue → execution → branch/commit → PR → checks/review → merge-ready or truthful failure remains a live/runtime acceptance concern beyond fake-worker integration tests.
4. **Builder restart/recovery proof** — a real running mission interrupted by process restart remains a live acceptance gap.
5. **Builder UI/CLI agreement** — the product surface should prove it reflects the same durable execution truth as the control-plane interfaces.

These gaps are higher ROI than proliferating low-level tests around already-covered internals.

## Deliberate non-goals

- No retries were added as a primary flake fix.
- No meaningful process-boundary tests were deleted for speed.
- No paid/live provider calls were added to normal CI.
- No third-party library/framework behavior was tested merely for its own sake.
- No production architecture was broadly refactored just to satisfy tests.

## Final verification

The reconciled integration branch was rebuilt from `origin/main` at `9b8c6649677143ff1d8759f8709ef36b1067433e` and contains the 15 substantive hardening commits only; stale merge commits from the source lanes were not carried forward.

Focused reconciliation checks:

- `tests/test_ci_gate_workflows.py` plus adjacent workflow/policy coverage: **106 passed**.
- focused determinism/assertion/tier regression set: **139 passed, 79 deselected**.
- Ruff across `gateway/ tests/ mcp/ workers/ scripts/runpod_worker_smoke_test.py`: **passed**.
- both modified workflow YAML files parse successfully.

Five consecutive FAST required runs all passed with the same result: **4,714 passed, 1 skipped, 312 integration tests deselected, 29 subtests passed**. Real wall times were **125.01s, 108.12s, 109.29s, 108.25s, and 108.80s**; median **108.80s**. Relative to the 204.94s pre-hardening median, the ordinary required Python loop is approximately **46.9% faster** while retaining the process-heavy tests in a separate required tier.

Five consecutive INTEGRATION required runs all passed with the same result: **312 passed, 4,715 deselected**. Real wall times were **112.82s, 113.88s, 113.09s, 112.48s, and 112.86s**; median **112.86s**.

The split therefore improves developer feedback latency without deleting the real git/subprocess/lifecycle contracts: FAST and INTEGRATION remain separately required by CI and are recombined by the merge gate.
