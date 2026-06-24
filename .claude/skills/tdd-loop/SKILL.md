---
name: tdd-loop
description: Run a failing test path through an autonomous fix-and-retry loop. Triggers on "make this test pass", "fix the failing test", "iterate until green", "fix until tests pass", "tests are red", "tests broke", "tests fail", "/tdd-loop <test-path>".
argument-hint: "<test-path-or-pattern>"
allowed-tools:
  - Read
  - Edit
  - Bash(python3* -m pytest*)
  - Bash(git diff *)
  - Bash(git add *)
  - Bash(git commit *)
---

# TDD Loop

Accepts a failing test path or pattern and iterates: read failure → patch → re-run,
up to 10 times. Escalates to user on repeated errors or large-scope changes.

## Protocol

1. **Baseline**: Run the target test(s) and record the initial failure message.
   ```bash
   python3.12 -m pytest $ARGUMENTS -q --tb=short 2>&1 | tail -30
   ```
   If tests are already green, report and stop.

2. **Loop** (max 10 iterations):
   a. Read the failure: identify the file, line, assertion, and root cause
   b. Propose the minimal patch — prefer fixing production code over changing tests
   c. Apply the patch
   d. Re-run the same test(s)
   e. If green → record iteration count, commit with message `fix: <what> (tdd-loop i=$N)`
   f. If still failing → go to next iteration

3. **Stop and escalate to user** if any of:
   - Same error message repeats 3× in a row (stuck, not making progress)
   - Fix would touch > 5 files
   - Phase 0 eval pass rate would drop below 80% (`python3.12 -m pytest tests/ -q 2>/dev/null | tail -1`)
   - Failure is an import/dependency error (environment problem, not logic)
   - 10 iterations reached without green

4. On escalation: report the last failure, what was tried, and your best hypothesis for the root cause.

## Rules

- Never change a test to make it pass unless the test is clearly wrong (and say so explicitly)
- Never add `# noqa`, `# type: ignore`, or `@pytest.mark.skip` to hide failures
- Each iteration must produce a meaningful diff — no no-op retries
- If a fix introduces a new test failure elsewhere, revert and try a different approach

## Flow

After escalation (stuck, >5 files touched, 10 iterations, or same-error-3x), suggest `/debug-fix` with the failing test path and the last 2 attempts in context. Don't re-try the loop — hand off.
