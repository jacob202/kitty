# Work Surface Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Work the one normal user-facing Kitty execution surface while keeping durable Builder/Gateway truth and advanced diagnostics separate.

**Architecture:** Preserve Builder as source truth and `/work` as the canonical product projection. Converge navigation onto `WorkView`, then change Work presentation so user-relevant state leads and implementation IDs move behind deliberate disclosure. Do not change Image Lab or create another execution state store.

**Tech Stack:** Next.js/React/TypeScript, Vitest + Testing Library, FastAPI/Python only if the existing `/work` projection proves insufficient.

**Spec:** `docs/superpowers/specs/2026-08-20-work-surface-convergence-design.md`

## Global Constraints

- Kitty native UI remains the canonical product surface under ADR 0039.
- Work is backed by Gateway `/work`; the frontend must not invent execution truth.
- Home and ordinary navigation converge on Work.
- Existing deep Builder diagnostics may remain internal/advanced; do not delete them in this slice.
- `approval.state == "unavailable"` is not user action required.
- No Image Lab files are modified.
- Use TDD: watch each behavior test fail before production changes.

---

### Task 1: Converge ordinary navigation on Work

**Files:**
- Modify: `gateway/kitty-chat/src/components/HomeState.tsx`
- Modify: `gateway/kitty-chat/src/components/ViewRenderer.tsx`
- Modify: `gateway/kitty-chat/src/lib/views.tsx`
- Test: `gateway/kitty-chat/tests/HomeState.test.tsx`
- Test: create or extend a focused view-routing test under `gateway/kitty-chat/tests/`

**Interfaces:**
- Consumes: existing `onNavigate(view: string)` callbacks and `ViewRenderer({ view, ... })`.
- Produces: normal `builder` navigation resolves to `work`; Home Builder glance invokes `onNavigate('work')`.

- [ ] **Step 1: Write the failing Home navigation test**

Add a focused assertion around the existing Home Builder glance interaction so clicking its open action calls the supplied navigation callback with `work`, never `builder`.

```tsx
const onNavigate = vi.fn()
render(<HomeState {...baseProps} onNavigate={onNavigate} />)
await user.click(screen.getByRole('button', { name: /open builder/i }))
expect(onNavigate).toHaveBeenCalledWith('work')
expect(onNavigate).not.toHaveBeenCalledWith('builder')
```

- [ ] **Step 2: Run the Home test and verify RED**

Run from `gateway/kitty-chat`:
`npm test -- HomeState.test.tsx`

Expected: FAIL because Home currently navigates to `builder`.

- [ ] **Step 3: Write the failing ordinary builder-routing test**

Render `ViewRenderer` with `view="builder"`, mock `WorkView` and `BuilderView`, and assert the Work surface is rendered while the Builder cockpit is not.

```tsx
render(<ViewRenderer view="builder" compact={false} />)
expect(screen.getByTestId('work-view')).toBeInTheDocument()
expect(screen.queryByTestId('builder-view')).not.toBeInTheDocument()
```

Use local module mocks in the test only; production routing remains real.

- [ ] **Step 4: Run the routing test and verify RED**

Expected: FAIL because `ViewRenderer` currently renders `BuilderView` for `builder`.

- [ ] **Step 5: Implement the minimal navigation convergence**

Change Home's Builder glance callback to `onNavigate('work')`. Change the normal `builder` renderer case to the same `WorkView` path used by `work`/`tasks`. Update `REDIRECTS.builder = 'work'` or equivalent canonical redirect declaration while retaining the `builder` view identifier only where required for compatibility.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run the two focused test files. Expected: PASS with no console errors/warnings.

- [ ] **Step 7: Commit**

`git commit -am "feat(work): converge Builder navigation on Work"`

---

### Task 2: Present Work in user-centered groups

**Files:**
- Modify: `gateway/kitty-chat/src/components/WorkView.tsx`
- Modify: `gateway/kitty-chat/tests/WorkViewProjection.test.tsx`

**Interfaces:**
- Consumes: `GatewayWorkItem.state` from `src/lib/work.ts`.
- Produces: deterministic sections `Needs you`, `In progress`, `Completed` without changing durable state.

- [ ] **Step 1: Write failing grouping tests**

Create a snapshot containing representative items:

```ts
blocked -> Needs you
failed -> Needs you
paused -> Needs you
active -> In progress
ready -> In progress
waiting -> In progress
completed -> Completed
```

Assert section headings exist and each title appears beneath the correct section. Do not use `approval.state` for grouping.

- [ ] **Step 2: Run the WorkView test and verify RED**

Run: `npm test -- WorkViewProjection.test.tsx`

Expected: FAIL because Work currently renders one flat item list.

- [ ] **Step 3: Implement minimal grouping helpers**

Add a pure local grouping helper in `WorkView.tsx`:

```ts
type WorkGroup = 'needs-you' | 'in-progress' | 'completed'

function workGroup(state: GatewayWorkState): WorkGroup {
  if (state === 'blocked' || state === 'failed' || state === 'paused') return 'needs-you'
  if (state === 'completed') return 'completed'
  return 'in-progress'
}
```

Render only non-empty sections, preserving existing item order within each section.

- [ ] **Step 4: Run the grouping tests and verify GREEN**

Expected: PASS.

- [ ] **Step 5: Commit**

`git commit -am "feat(work): group execution state around user attention"`

---

### Task 3: Move implementation identifiers behind progressive disclosure

**Files:**
- Modify: `gateway/kitty-chat/src/components/WorkView.tsx`
- Modify: `gateway/kitty-chat/tests/WorkViewProjection.test.tsx`

**Interfaces:**
- Consumes: existing `GatewayWorkItem.source`, `current_packet`, `current_run`, `evidence`, `data_quality`.
- Produces: primary row shows title/state/blocker-next-action/result summary; a native details disclosure contains IDs and raw diagnostic metadata.

- [ ] **Step 1: Write failing default-visibility test**

Render an item with initiative, packet, task, and run IDs. Assert raw identifiers are not visible before expanding details.

```tsx
expect(screen.queryByText('WORK-SPINE-003')).not.toBeVisible()
expect(screen.queryByText(/run RUN-123/)).not.toBeVisible()
```

Then open the item's `details`/`summary` control and assert diagnostic identifiers become visible.

- [ ] **Step 2: Run the test and verify RED**

Expected: FAIL because raw IDs are currently rendered in the primary row.

- [ ] **Step 3: Write failing evidence-summary test**

For an item with bounded review/publication evidence, assert the row presents a concise truthful label derived only from present fields. For missing evidence, assert no invented success statement appears.

Prefer deterministic labels such as `Review passed`, `Published`, or `Evidence available` only when the corresponding projected evidence object proves it. If the current evidence shape is too inconsistent to support a safe concise label, keep evidence inside details and do not widen the backend contract in this task.

- [ ] **Step 4: Implement minimal progressive disclosure**

Use native `<details>`/`<summary>` so accessibility and state stay simple. Primary content remains title, state, blocker/next action, and any deterministic evidence summary. Put source initiative ID, packet/task/run IDs, data-quality issues, and structured evidence under `Details`.

- [ ] **Step 5: Run focused tests and verify GREEN**

Expected: PASS with no hidden duplicate accessible text that makes the default-visibility assertion meaningless.

- [ ] **Step 6: Commit**

`git commit -am "feat(work): hide execution internals behind details"`

---

### Task 4: Preserve stale, degraded, unavailable, and reload truth

**Files:**
- Modify only if required: `gateway/kitty-chat/src/components/WorkView.tsx`
- Modify: `gateway/kitty-chat/tests/WorkViewProjection.test.tsx`
- Modify or extend: `gateway/kitty-chat/tests/WorkGateway.test.ts`

**Interfaces:**
- Consumes: `fetchGatewayWorkSnapshot()` and existing React Query `useWorkSnapshot()`.
- Produces: no fallback to Builder cockpit; stale/degraded/unavailable states remain explicit; refetch still targets `/proxy/work`.

- [ ] **Step 1: Add regression tests**

Assert:
- expired `valid_until` renders `Builder stale`;
- `source.state='degraded'` renders degraded status;
- request failure exposes retry and does not render Builder cockpit fallback copy;
- gateway fetch remains `GET /proxy/work` and invalid payloads fail closed.

- [ ] **Step 2: Run tests**

If they already pass, record that as regression coverage and do not change production code solely to manufacture a red test. If a new desired behavior fails, make the smallest production fix after observing RED.

- [ ] **Step 3: Run the full focused Work/navigation slice**

From `gateway/kitty-chat` run the affected Vitest files together, including Home, WorkView, WorkGateway, and the new routing test.

Expected: all pass with pristine console output.

- [ ] **Step 4: Run frontend quality gates**

Run the repository's normal kitty-chat unit suite and production build commands from `package.json`. Do not substitute guessed commands if scripts differ; inspect `package.json` and execute the defined test/build scripts.

- [ ] **Step 5: Verify scope**

Run `git diff --name-only <base>...HEAD`. Confirm no Image Lab files changed and no backend projection files changed unless Task 3 proved them necessary.

- [ ] **Step 6: Commit any final test-only regression coverage**

`git commit -am "test(work): lock canonical execution surface truth"`

---

### Task 5: Final exact-head verification and PR

**Files:**
- No production changes expected.

**Interfaces:**
- Produces: pushed exact-head branch and a focused PR stacked on `feat/product-surface-convergence-20260817`.

- [ ] **Step 1: Run `git diff --check` and inspect status**

Expected: clean whitespace and only intended tracked changes.

- [ ] **Step 2: Re-run affected tests on exact head**

Expected: PASS.

- [ ] **Step 3: Push branch**

Push `feat/work-surface-convergence-20260820` without force unless the branch topology explicitly requires it.

- [ ] **Step 4: Open PR against `feat/product-surface-convergence-20260817`**

PR summary must state that Work becomes the canonical normal execution surface, Builder cockpit remains internal/advanced, `/work` remains truth, and Image Lab was untouched.

- [ ] **Step 5: Check exact-head CI/review status**

Do not claim success from earlier SHAs. If CI fails, inspect the failing job and fix only failures caused by this slice.
