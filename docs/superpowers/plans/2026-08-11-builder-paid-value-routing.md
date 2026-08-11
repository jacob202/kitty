# Builder Paid Value Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an explicit governed paid OpenRouter lane with cheap/frontier tiers while preserving the free lane unchanged.

**Architecture:** A small config loader resolves paid route policy. CLI opt-in selects the paid OpenCode agents/models, while the existing compute governor remains the spend gate and Builder loop remains the execution authority. Attempt manifests gain the governor decision and projected cost as evidence.

**Tech Stack:** Python 3.12, argparse, JSON config, existing OpenCode adapters, pytest.

## Global Constraints

- No accidental paid fallback.
- Free agents and default free behavior remain unchanged.
- Credentials never enter checked-in config.
- Paid route must be governed before attempt creation.
- Existing leases, worktrees, retries, validation, review, and publication rails remain authoritative.

---
### Task 1: Paid route policy

**Files:**
- Create: `config/builder_paid_routes.json`
- Create: `gateway/builder_paid_routing.py`
- Test: `tests/test_builder_paid_routing.py`

- [ ] Write failing tests for valid cheap/frontier resolution, disabled config, unknown tier, and projected-cost ceiling.
- [ ] Implement a small validated config loader returning model/provider/governor route/projected cost.
- [ ] Run `pytest tests/test_builder_paid_routing.py -q` and Ruff/mypy.
- [ ] Commit the policy unit.

### Task 2: Paid agents and CLI selection

**Files:**
- Modify: `opencode.jsonc`
- Modify: `scripts/kittybuilder_opencode_worker.sh`
- Modify: `scripts/kittybuilder_opencode_reviewer.sh`
- Modify: `gateway/builder_cli.py`
- Test: `tests/test_builder_cli.py`

- [ ] Add failing tests proving paid is opt-in, mutually exclusive with free/explicit commands, and cheap is the default tier.
- [ ] Add separate `paid-builder` / `paid-reviewer` agents and parameterize adapter agent names with free defaults.
- [ ] Resolve paid models from config and pass model/provider metadata into Builder.
- [ ] Run focused CLI tests plus adapter syntax checks.
- [ ] Commit the CLI/agent unit.
### Task 3: Governor tier + attempt evidence

**Files:**
- Modify: `gateway/builder_loop.py`
- Modify: `gateway/builder_run.py`
- Test: `tests/test_builder_loop.py`
- Test: `tests/test_builder_run.py`

- [ ] Add failing tests that cheap maps to routine governor risk, frontier maps to risky, and the decision is present before worker execution.
- [ ] Thread the selected risk class through initiative and packet execution without changing the default routine path.
- [ ] Persist governor action/route/reasons/projected cost into `run-manifest.json` before the worker starts.
- [ ] Run Builder loop/run regressions and static checks.
- [ ] Commit the evidence unit.

### Task 4: Docs, CI, and proof

**Files:**
- Modify: `docs/FREE_WORKERS.md`
- Test: existing Builder/compute-governor/CLI suites

- [ ] Document explicit paid usage and rollback flag.
- [ ] Run focused tests, Ruff, mypy, and policy validation.
- [ ] Push and require clean GitHub CI before merge.
- [ ] From fresh merged `main`, run KPROOF-CLEAN-004 using `--paid --tier cheap` with the existing 20-minute/2-attempt proof limits.
- [ ] Record interventions, elapsed time, route/cost evidence, review outcome, and publish/merge result.
