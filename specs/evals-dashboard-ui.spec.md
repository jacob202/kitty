# Spec: Eval Dashboard UI Panel

Date: 2026-04-28
Owner: Codex
Worker lane: Phase 6+ transparent evals
Status: draft

## Goal

Build a read-only UI panel in the Garage UI to display the current eval health, sourcing data from the existing `/api/eval/dashboard` backend route.

## Current App Boundary

Current runnable app:

`/Users/jacobbrizinski/Projects/kitty`

Physical repo move allowed:

No.

## Background

The backend for the evals dashboard has been implemented and tested (`specs/evals-dashboard.spec.md`). It exposes a `GET /api/eval/dashboard` endpoint that returns a summary of eval artifacts. We now need a dedicated UI panel to display this information to the user in a clear, transparent way.

## Allowed Files

- `kitty-chat/app/components/EvalDashboard.tsx` (new)
- `kitty-chat/app/page.tsx`
- `kitty-chat/app/components/Sidebar.tsx` (if adding a navigation link/view toggle)
- `kitty-chat/app/components/CommandPalette.tsx` (if adding a view toggle)
- `specs/evals-dashboard-ui.spec.md`

## Forbidden Files

- Backend Python files (`src/`, `web.py`, etc.)
- Eval artifacts (`evals/artifacts/`)
- Any files not strictly required for adding the UI panel

## Non-Goals

- Do not implement triggering of new evals from the UI (this is a read-only dashboard).
- Do not rewrite the backend route.
- Do not add complex historical charts; a simple summary of the latest state and trend is sufficient.

## Implementation Plan

1. Create a new `EvalDashboard` React component in `kitty-chat/app/components/EvalDashboard.tsx` that fetches from `http://${window.location.hostname}:5001/api/eval/dashboard`.
2. Design the component to display:
   - Total artifacts count.
   - Latest run summary (pass rate, failed checks).
   - Trend indicator.
3. Integrate the `EvalDashboard` component into the main layout in `kitty-chat/app/page.tsx`. This could be a new persistent view (like 'chat' and 'journal') or a panel in the Sidebar/Inspector. For visibility, creating a dedicated 'Evals' view toggled via the header or command palette is recommended.
4. Add a view toggle button for the Evals dashboard.

## Acceptance Tests

- Test: The UI successfully fetches and parses data from `/api/eval/dashboard`.
- Test: The dashboard displays the artifact count, latest pass rate, and trend.
- Test: The user can navigate to the Evals view and back to Chat/Journal.
- Expected result: The dashboard renders without errors and shows the current backend state.

## Smoke Test

Command or manual check:
1. Start the app backend and frontend.
2. Navigate to `http://localhost:3000`.
3. Toggle the view to the Evals Dashboard.
Expected result: The dashboard appears and shows valid eval metrics.

## Validation Commands

```bash
cd kitty-chat && npm run build
```

Expected:

- Exit code: 0
- Required output: successful Next.js build.

## Rollback Plan

Rollback steps:

1. Delete `kitty-chat/app/components/EvalDashboard.tsx`.
2. Revert modifications in `kitty-chat/app/page.tsx` and related navigation components.
3. Re-run `cd kitty-chat && npm run build`.

## Risk Notes

- UI might momentarily show stale data before the fetch completes; ensure a loading state is present.

## Completion Report

When done, report:

- Files changed.
- Files intentionally not touched.
- Validation performed.
- Acceptance test results.
- Smoke test result.
- Known gaps.
- Parked follow-ups.
