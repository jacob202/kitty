# PR Janitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Builder automatically clear recurring publication gates before a PR is opened, then feed any remaining gate failure back into its existing bounded repair agent loop.

**Architecture:** Builder remains the only execution owner. A small `builder_pr_janitor` module applies only safe deterministic Ruff fixes, while `builder_loop` adds the repository pre-push hook as a universal publication validation gate and reuses the existing repair loop. No GitHub write-bot, daemon, queue, dependency, or new database is added.

**Tech Stack:** Python 3.12, existing KittyBuilder queue/attempt/loop modules, git subprocesses, Ruff, pytest.

## Global Constraints
- Maximum 3 janitor passes per `run_packet` publication loop.
- Never force-push during publication.
- Never edit secrets/auth/env, dependencies, `.claude/STATE.md`, `.claude/HANDOFF.md`, `data/`, or `logs/`.
- The fixer never approves itself; existing independent review remains required.
- Fail loud with structured evidence when safe repair cannot clear the gate.

---

### Task 1: Preserve gate failure evidence for repair workers

**Files:**
- Modify: `gateway/builder_attempt.py`
- Test: `tests/test_builder_attempt.py`

**Interfaces:**
- Extend `run_validation(..., extra_commands: list[str] | None = None)` to append orchestrator-owned validation commands.
- Extend `_prior_attempt_summary()` with a bounded `validation` digest containing failed command, exit code, and output tail.

- [ ] Write tests proving an extra command is recorded and a failed validation appears in the next attempt bundle.
- [ ] Run the two focused tests and verify they fail before implementation.
- [ ] Implement:
```python
def run_validation(..., extra_commands: list[str] | None = None) -> dict[str, Any]:
    commands = declared_commands + list(extra_commands or [])
```
and add bounded failed-command evidence in `_prior_attempt_summary`.
- [ ] Re-run focused tests and commit `feat(builder): carry publication gate evidence`.

### Task 2: Add safe deterministic PR repairs

**Files:**
- Create: `gateway/builder_pr_janitor.py`
- Create: `tests/test_builder_pr_janitor.py`

**Interfaces:**
- Produce `JANITOR_MAX_PASSES = 3`.
- Produce `PUBLICATION_GATE_COMMAND = "./scripts/hooks/pre-push"`.
- Produce `apply_safe_repairs(worktree: Path, *, run_cmd: RunCmd | None = None) -> dict[str, Any]`.

- [ ] Write tests for no-change, Ruff-fix-and-commit, dirty-worktree refusal, and forbidden-path refusal.
- [ ] Run the focused janitor tests and verify failure.
- [ ] Implement a clean-worktree-only fixer that runs the same Ruff surface as CI with `--fix`, verifies changed paths are limited to `gateway/`, `tests/`, `mcp/`, `workers/`, and `scripts/runpod_worker_smoke_test.py`, then commits only its own changes:
```python
RUFF_TARGETS = ["gateway/", "tests/", "mcp/", "workers/", "scripts/runpod_worker_smoke_test.py"]
# git status must be clean before mutation
# python -m ruff check --fix <targets>
# reject any changed path outside the safe roots
# git add -- <changed paths>; git commit -m "fix: apply PR janitor repairs"
```
- [ ] Re-run focused tests and commit `feat(builder): add deterministic PR janitor`.

### Task 3: Put publication gates inside the existing repair loop

**Files:**
- Modify: `gateway/builder_loop.py`
- Test: `tests/test_builder_loop.py`

**Interfaces:**
- Extend `run_packet(..., publication_preflight: bool = False)`.
- When enabled, call `apply_safe_repairs()` before validation and pass `[PUBLICATION_GATE_COMMAND]` as `extra_commands` to `run_validation()`.
- Record `pr_janitor_pass` events with pass number, attempt id, head before/after, repairs, and gate outcome.

- [ ] Write tests that a fixable publication failure retries and succeeds, non-fixable failure is repairable evidence, and pass 4 is never started.
- [ ] Run those tests and verify failure.
- [ ] Implement the bounded integration. A publication-gate failure uses the existing `repairable=True` validation failure path; it must not create a second worker system.
- [ ] Re-run focused loop tests and commit `feat(builder): repair publication gates before PR`.

### Task 4: Enable the janitor only when Builder will publish

**Files:**
- Modify: `gateway/builder_run.py`
- Test: `tests/test_builder_run.py`
- Modify: `docs/KITTYBUILDER_QUICKSTART.md`

**Interfaces:**
- `run_initiative(... publish=True ...)` passes `publication_preflight=True` to `run_packet`.
- Shadow/manual non-publishing runs keep the default `False`.

- [ ] Write a test proving publish mode enables the flag and shadow mode does not.
- [ ] Run focused test and verify failure.
- [ ] Wire the flag and add a short operator note explaining `pr_janitor_pass` evidence and the 3-pass cap.
- [ ] Run focused tests and commit `docs(builder): document PR janitor publication gate`.

### Task 5: Verify the bounded feature

**Files:** no new implementation files.

- [ ] Run `python3.12 -m pytest tests/test_builder_attempt.py tests/test_builder_pr_janitor.py tests/test_builder_loop.py tests/test_builder_run.py tests/test_builder_publish.py -q --tb=short`.
- [ ] Run Ruff only on touched Python files.
- [ ] Inspect `git diff origin/main...HEAD` for forbidden/surprise paths.
- [ ] Confirm no force-push was added to the publication path and no second queue/state store exists.
