# Spec: Transparent Evals Dashboard Backend

Date: 2026-04-28
Owner: Codex
Worker lane: Phase 6+ transparent evals
Status: implemented backend

## Goal

Expose a read-only backend summary of eval artifacts so Kitty can show current eval health without running new evals or touching append-only artifacts.

## Current App Boundary

Current runnable app:

`/Users/jacobbrizinski/Projects/kitty`

Physical repo move allowed:

No.

## Background

The current eval route `POST /api/eval/run` runs the smoke suite and writes artifacts. A dashboard must not call that runner. It should read `evals/artifacts/*_smoke.json` and summarize recent results.

## Allowed Files

- `src/observability/evals_dashboard.py`
- `src/observability/__init__.py`
- `src/api/eval_routes.py`
- `tests/test_evals_dashboard.py`
- `specs/evals-dashboard.spec.md`
- `docs/DELEGATION_BOARD.md`
- `TASKS.md`
- `SESSION_SUMMARY.md`

## Forbidden Files

- `evals/artifacts/`
- `eval_snapshots/`
- UI files
- raw chat logs
- data deletion or artifact cleanup

## Non-Goals

- Do not build the frontend panel yet.
- Do not run evals from the dashboard endpoint.
- Do not overwrite or delete artifacts.
- Do not reuse `/api/eval/scorecard` as the source of truth.

## Implementation Plan

1. Add a read-only artifact parser.
2. Summarize latest run, pass rate, failures, trend, artifact count, and corrupt artifact count.
3. Add `GET /api/eval/dashboard` to `eval_bp`.
4. Add focused tests with temporary artifact directories.

## Acceptance Tests

- Test: missing artifact directory returns empty dashboard summary.
- Test: latest artifact is selected by timestamp/mtime.
- Test: failed checks are surfaced.
- Test: corrupt artifacts are counted, not raised.
- Test: route returns JSON and does not create artifacts.

## Smoke Test

Command:

```bash
curl http://localhost:5001/api/eval/dashboard
```

Expected result:

- HTTP 200
- JSON includes `artifact_count`, `latest`, and `trend`

## Validation Commands

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_evals_dashboard.py -q --tb=short
/opt/homebrew/bin/python3.12 -m pytest tests/test_reliability_platform.py tests/test_eval_loop_logging.py -q --tb=short
```

Expected:

- Exit code: 0

## Rollback Plan

Remove only the files and route added by this spec, then rerun the validation commands.

## Risk Notes

Artifacts are append-only evidence. This feature must remain read-only. Frontend work should be a later spec.

## Completion Report

When done, report files changed, validation performed, and known gaps.
