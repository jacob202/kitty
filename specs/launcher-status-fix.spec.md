# Spec: Launcher Status Fix

Date: 2026-04-29
Owner: Codex
Worker lane: Launcher
Status: draft

## Goal

Fix `./kitty status` so that it correctly reports when the Kitty server is running on port 5001, even if the `.kitty.pid` file is missing or stale.

## Current App Boundary

Current runnable app:

`/Users/jacobbrizinski/Projects/kitty`

## Background

Currently, `./kitty status` relies solely on the presence of `.kitty.pid` and `kill -0` to determine if the server is running. If the server is started via `scripts/start.sh` or directly via `python3.12 web.py`, the PID file is not created, causing `./kitty status` to falsely report the server as "stopped".

## Allowed Files

- `kitty`
- `specs/launcher-status-fix.spec.md`

## Forbidden Files

- `src/`
- `web.py`
- `scripts/start.sh`
- Any Python source or test files.

## Non-Goals

- Do not rewrite the entire bash launcher.
- Do not change how the server starts or stops, only how `status` checks it.

## Implementation Plan

1. Modify the `_status` function in `kitty`.
2. Check for the PID via `lsof -ti tcp:$PORT` if the PID file check fails.
3. If `lsof` returns a PID, report that the server is running and print its PID and URLs.
4. If neither check finds a running server, report "stopped".

## Acceptance Tests

- Test: Server is started via `python3.12 web.py` (no PID file). `./kitty status` reports it as running.
- Expected result: Output shows `running` and URLs.

## Smoke Test

Command:

```bash
./kitty status
```

Expected result:

Accurate status message (running or stopped) without errors.

## Validation Commands

```bash
# Start server in background
/opt/homebrew/bin/python3.12 web.py &
TEST_PID=$!
sleep 2

# Check status
./kitty status | grep "running"

# Cleanup
kill $TEST_PID
```

Expected:

- Exit code: 0
- Output shows "running".

## Rollback Plan

Revert `kitty` to its previous state using `git checkout kitty`.

## Completion Report

When done, report files changed, validation performed, and any edge cases discovered.
