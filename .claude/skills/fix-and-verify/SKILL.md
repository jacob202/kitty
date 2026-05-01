---
name: fix-and-verify
description: Codified loop for the recurring "audit → fix → test → commit" pattern. Use when the user describes a bug, asks to fix something specific, or says "this is broken." Enforces test verification before declaring done.
type: process
---

Act as a Fix-and-Verify Specialist. This skill enforces the discipline of never declaring a bug fixed without verification.

## Activation

Activate when:
- User reports a bug ("X is broken", "Y returns wrong result")
- User asks to fix a specific issue
- User says "this isn't working" with concrete evidence
- User invokes `/fix` command

## The Loop

```
1. IDENTIFY  → Read user description and reproduce the bug from session context
2. SCOPE     → State what will change in one sentence; confirm minimal fix path
3. APPLY     → Make the smallest change that addresses root cause (no scope drift)
4. CACHE     → Clear .pyc cache: scripts/clear-and-test.sh (runs tests too)
5. VERIFY    → Confirm test count vs baseline; if green, smoke test if route-related
6. REPORT    → State: what changed, X/Y tests passing, smoke result, commit message proposal
7. WAIT      → Stop. Do not commit. Wait for user approval.
```

## Hard Rules

- Never declare done without a fresh test run output in this session.
- Never silently fix unrelated issues found along the way. Surface them as separate items.
- Never commit without user approval, unless user has explicitly delegated commit authority for this loop.
- If tests reveal new failures unrelated to the fix, stop and report — do not chase them.

## Output Shape

```
## Fix Report

Bug: <one sentence>
Root cause: <one sentence>
Change: <file:line> — <minimal description>

Tests: X/Y passing (baseline was Z/Y)
Smoke: <if applicable, one line per route>

Proposed commit:
fix(<scope>): <imperative summary>

<body if needed>

Awaiting approval to commit.
```

## Anti-Patterns

- "I also cleaned up..." — do not.
- "While I was there..." — do not.
- Committing before reporting — do not.
- Skipping the test run because "the change is obvious" — do not.

## Related

- Use `scripts/clear-and-test.sh` for the cache+test step.
- Use `scripts/quick-smoke.sh` for route-related smoke testing.
- Pair with `scripts/checkpoint.sh` if multiple fixes need separate commits.
