# Spec: Builder Output Security Scanner

Date: 2026-04-28
Owner: Codex
Worker lane: Phase 6+ security scanning
Status: implemented

## Goal

Add a pure, testable scanner that can inspect proposed builder output for obvious secrets and dangerous code patterns before it is wired into write paths.

## Current App Boundary

Current runnable app:

`/Users/jacobbrizinski/Projects/kitty`

Physical repo move allowed:

No.

## Background

`scripts/kitty_builder.py` already has path containment and command sanitization, but `write_file()` does not scan generated content for secrets or dangerous snippets. This spec adds the scanner only. Builder write enforcement is a later spec.

## Allowed Files

- `src/utils/security_scanner.py`
- `tests/test_security_scanner.py`
- `specs/security-scanner.spec.md`
- `scripts/run_gates.sh`
- `docs/DELEGATION_BOARD.md`
- `TASKS.md`
- `SESSION_SUMMARY.md`

## Forbidden Files

- `scripts/kitty_builder.py`
- `web.py`
- `data/`
- UI files
- raw chat logs
- eval artifacts

## Non-Goals

- Do not block builder writes yet.
- Do not delete secrets or rewrite files.
- Do not run Bandit as an external dependency.
- Do not scan the full repository by default.

## Implementation Plan

1. Add `SecurityFinding` and `SecurityReport` dataclasses.
2. Add `scan_text(path, content)` and `scan_files(files)`.
3. Detect hardcoded secrets, private key blocks, `shell=True`, `os.system`, `eval`, `exec`, traversal strings, `rm -rf`, and `chmod 777`.
4. Add placeholder allowlist for examples such as `sk-or-...`.
5. Add focused tests.
6. Add scanner tests to `scripts/run_gates.sh`.

## Acceptance Tests

- Test: detects real-looking API keys and private keys.
- Test: ignores placeholder docs such as `sk-or-...`.
- Test: detects dangerous subprocess and dynamic execution patterns.
- Test: returns structured rule, severity, path, line, and message.

## Smoke Test

Command:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_security_scanner.py -q --tb=short
```

Expected result:

- exits 0
- all scanner tests pass

## Validation Commands

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_security_scanner.py -q --tb=short
bash scripts/run_gates.sh
```

Expected:

- Exit code: 0

## Rollback Plan

Remove only:

- `src/utils/security_scanner.py`
- `tests/test_security_scanner.py`
- `specs/security-scanner.spec.md`

Then remove the scanner test from `scripts/run_gates.sh` and rerun the gate.

## Risk Notes

The scanner is intentionally conservative. It can produce false positives and should report findings, not mutate files. Enforcement in builder write paths requires a separate spec.

## Completion Report

When done, report:

- Files changed.
- Validation performed.
- Known false-positive limits.
- Whether builder enforcement remains parked.
