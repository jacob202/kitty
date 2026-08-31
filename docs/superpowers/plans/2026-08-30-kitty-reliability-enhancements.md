# Kitty Reliability Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use TDD for every behavior change and verify exact-head evidence before publication.

**Goal:** Make Kitty degrade predictably under tool/context failures and require repeated failure-path success before release.

**Architecture:** Extend existing owners only: MCP bridge for invocation resilience, context assembler for request context truth, health surface for read-only operational projection, and one fixed developer reliability gate. No new persistence or orchestration system.

**Tech Stack:** Python 3.12, asyncio/subprocess, FastAPI health projection, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-08-30-kitty-reliability-enhancements-design.md`

## Global Constraints

- Do not touch PR #705 Chat/Library paths.
- Do not touch active Builder retry/supervisor files.
- Do not create a new DB, queue, policy engine, or dependency.
- Healthy context rendering must remain unchanged.
- Circuit state is ephemeral load-shedding state, never product truth storage.

### Task 1: MCP subprocess lifecycle + circuit breaker

**Files:** modify `gateway/mcp_tool_bridge.py`; create `tests/test_mcp_tool_bridge.py`.

- [ ] Write failing tests for timeout cleanup, cancellation cleanup, consecutive-failure cutoff, cooldown recovery, and timeout override validation.
- [ ] Run `python -m pytest tests/test_mcp_tool_bridge.py -q` and confirm RED.
- [ ] Implement bounded timeout resolution, child cleanup, and `(server, tool)` circuit state.
- [ ] Add `tool_health_snapshot()` with configuration + open-circuit evidence only.
- [ ] Run the focused test to GREEN and commit.

### Task 2: Existing health/context surfaces become degradation-aware

**Files:** modify `gateway/health_surface.py`, `gateway/context_assembler.py`; modify `tests/test_health_surface.py`, `tests/test_context_assembler.py`.

- [ ] Write failing health test showing an open MCP circuit degrades `mcp_tools` without claiming remote liveness.
- [ ] Write failing context tests proving healthy output is unchanged and failed sources produce a sanitized model marker + structured receipt.
- [ ] Run focused tests and confirm RED.
- [ ] Implement the MCP health source and `ContextBundle.context_health` derivation/marker.
- [ ] Run focused tests to GREEN and commit.

### Task 3: Fixed repeated reliability gate

**Files:** create `gateway/reliability_metrics.py`, `scripts/kitty_reliability_gate.py`, `tests/test_reliability_metrics.py`, `tests/test_kitty_reliability_gate.py`.

- [ ] Write failing tests for all-pass summary, one-failure summary, bounded repetitions, fixed node IDs, and atomic JSON receipt behavior.
- [ ] Run focused tests and confirm RED.
- [ ] Implement pure summary helpers and the fixed pytest runner; reject arbitrary scenario/command input by not providing such a CLI surface.
- [ ] Run unit tests and `python scripts/kitty_reliability_gate.py --repetitions 5 --json-out /tmp/kitty-reliability.json` to GREEN.
- [ ] Commit.

### Task 4: Verification + independent review + publication

- [ ] Run the affected suites: MCP, health, context, capability manifest, integrations/action grants.
- [ ] Run full repo Ruff, focused mypy, and `git diff --check`.
- [ ] Run the repeatability gate five times per scenario and preserve its JSON receipt outside the repo.
- [ ] Independently review the exact SHA; repair substantive findings test-first.
- [ ] Merge current `origin/main` normally if it advanced; rerun affected gates.
- [ ] Push branch, open PR, wait for required GitHub gates/review, and merge only if repo policy permits and exact-head gates are green.
- [ ] Record final handoff in #490; preserve the feature branch/worktree until publication is proven.
