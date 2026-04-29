# Spec: Frontend Test Setup and Eval Dashboard Regression

Date: 2026-04-29
Owner: Codex
Worker lane: UI Worker
Status: draft

## Goal

Add a basic frontend testing harness (Vitest + React Testing Library) to the `garage-ui` Next.js application, and write a regression test for the Eval Dashboard component to ensure it correctly renders failed-check objects.

## Current App Boundary

Current runnable app:

`/Users/jacobbrizinski/Projects/kitty/garage-ui`

## Background

Currently, the `garage-ui` frontend lacks an automated testing framework. To safely iterate on components like the `EvalDashboard`, we need a baseline testing environment.

## Allowed Files

- `garage-ui/package.json`
- `garage-ui/vitest.config.ts`
- `garage-ui/tests/setup.ts`
- `garage-ui/app/components/__tests__/EvalDashboard.test.tsx`
- `garage-ui/app/components/EvalDashboard.tsx`
- `specs/frontend-test-setup.spec.md`

## Forbidden Files

- `src/`
- `web.py`
- Python tests

## Non-Goals

- Do not migrate the entire app to a new framework.
- Do not write tests for every existing component.

## Implementation Plan

1. Install `vitest`, `@testing-library/react`, `@testing-library/dom`, `@vitejs/plugin-react`, and `jsdom` as dev dependencies in `garage-ui`.
2. Configure `vitest.config.ts` for a React/jsdom environment.
3. Write a setup file `garage-ui/tests/setup.ts` with custom fetch mocking.
4. Write `EvalDashboard.test.tsx` to mount the component, mock the `/api/eval/dashboard` response (including a `failed_checks` array), and assert that the failed checks are rendered correctly.
5. Add a `test` script to `package.json`.

## Acceptance Tests

- Test: Run `npm run test` in `garage-ui`.
- Expected result: The `EvalDashboard` test passes, verifying that the component renders the "Failed Checks" section when `failed_checks` has items.

## Smoke Test

Command:

```bash
cd garage-ui && npm run test -- --run
```

Expected result:

All tests pass.

## Validation Commands

```bash
cd garage-ui
npm run build
npm run test -- --run
```

Expected:

- Exit code: 0
- Build succeeds and tests pass.

## Rollback Plan

Remove the installed testing dependencies, configuration files, and test files. Revert `package.json`.

## Completion Report

When done, report files changed, validation performed, and any edge cases discovered.
