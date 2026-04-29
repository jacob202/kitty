# Spec: Builder Write-Time Security Enforcement

Date: 2026-04-28
Owner: Codex
Worker lane: Phase 6+ builder safety
Status: implemented

## Goal

Block unsafe generated content before `kitty_builder.write_file()` writes it to disk.

## Problem

`src/utils/security_scanner.py` can detect hardcoded secrets and dangerous code patterns, but `scripts/kitty_builder.py` still writes proposed file content before any security scan. This leaves the builder able to introduce obvious secrets or unsafe code snippets.

## Non-goals

- Do not scan the whole repository by default.
- Do not mutate generated content.
- Do not delete existing files.
- Do not change command execution safety rules.
- Do not run Bandit or add external dependencies.
- Do not change interactive model behavior.

## Files Allowed To Change

- `scripts/kitty_builder.py`
- `tests/test_kitty_builder.py`
- `specs/builder-security-enforcement.spec.md`
- `docs/DELEGATION_BOARD.md`
- `TASKS.md`
- `SESSION_SUMMARY.md`

## Files Forbidden To Change

- `src/utils/security_scanner.py`
- `web.py`
- `src/**`
- `data/**`
- UI files
- raw chat logs
- eval artifacts

## Existing Context To Read First

- `specs/security-scanner.spec.md`
- `src/utils/security_scanner.py`
- `tests/test_security_scanner.py`
- `scripts/kitty_builder.py`
- `tests/test_kitty_builder.py`

## Required Behaviour

- `write_file(path, content)` scans `content` before writing.
- Any scanner finding blocks the write.
- The error response includes rule, severity, path, and line number.
- No partial file is created when blocked.
- Safe content still writes normally and runs the existing quality judge.

## Acceptance Tests

- unsafe content containing a real-looking API key is blocked
- unsafe content containing `subprocess.run(..., shell=True)` is blocked
- blocked content is not written to disk
- safe content still writes

## Smoke Test

Command:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_kitty_builder.py tests/test_security_scanner.py -q --tb=short
```

Expected result:

- exits 0
- builder write safety and scanner tests pass

## Validation

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_kitty_builder.py tests/test_security_scanner.py -q --tb=short
bash scripts/run_gates.sh
```

## Rollback Plan

Remove only the `write_file()` security scan hook and the new tests in `tests/test_kitty_builder.py`, then rerun the smoke test.

## Completion Report Required

- files read
- files changed
- commands run
- tests passed/failed
- gates passed/failed
- known false-positive risk
- next smallest action
