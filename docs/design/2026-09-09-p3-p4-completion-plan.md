# P3 + P4 completion plan — 2026-09-09

> **Non-authoritative working note. Not a roadmap and not a second backlog.**
> `docs/ROADMAP.md` remains the single active delivery backlog and the only
> authority on sequencing and status. This file is one session's snapshot of
> how the remaining P3/P4 work was approached. The per-checkpoint statuses
> below were true at the moment of writing and are **not** maintained — several
> were already changing as the work proceeded. Read delivery state from the
> roadmap, Git, and open PRs, never from here.

Base: `origin/main` at `505bdc09`. PRs #841–#844 merged.

Both backends landed. What remains is the half a person can actually see, plus
one backend repair that is currently telling the user something untrue.

Every checkpoint below states **what must be true** and **how it is proved**. A
checkpoint is not done because code was written; it is done when its proof runs.

---

## Where the acceptance gate binds

`scripts/pr_policy.py` requires a machine-readable acceptance block on any PR
touching `gateway/kitty-chat/src/` or `public/`. Six boxes, four evidence
fields. One box is:

> A reviewer who did not implement the change completed the task in the running app.

**I cannot tick that box for code I wrote.** Checkpoints marked **[JACOB]**
need five minutes of your clicking, or another reviewer. Everything else I can
finish and prove alone. I will get each UI branch fully green and hand you the
exact journey — you will not have to work out what to test.

---

## P3-A — stop reporting work as finished when it is not

**Status: not started. Backend only. No acceptance gate.**

`mcp/builder/context.py::work_result` reports:

```python
"complete": task_state == "done"
```

That is Builder's task being finished. It never reads the Mission, so it says
`complete: true` while the Mission's `acceptance.state` is still `unreviewed`
and nothing has been published. Chat then tells you the job is done. This is
the contradiction P3 acceptance 8 names, and `AGENTS.md` already forbids it:
implementation evidence is not user-outcome completion.

**What must be true**

1. `work_result` reports three separable facts: Builder task state, Mission
   acceptance state, publication state.
2. `complete` means the *outcome* is complete — Builder done **and** Mission
   accepted. Never Builder-done alone.
3. A Mission that cannot be found leaves acceptance `unknown`, never `accepted`.
4. Historical failures stay visible as history; current terminal truth wins.

**How it is proved**

- New `memory_mission.mission_for_initiative()` with tests.
- `tests/test_mcp_builder_context.py`: Builder done + Mission unreviewed →
  `complete` is false and the reason says which gate is open; Builder done +
  Mission accepted → true; missing Mission → `unknown`, not `accepted`.
- Narrow run reported with exact pass counts.

**Risk to check before writing:** who consumes `complete`. It is MCP-surface
only today (no gateway route), so the blast radius is `resume()` and MCP
clients — but that gets verified, not assumed.

---

## P3-B — separate "stop the mission" from "stop this run"

**Status: not started. Backend semantics, then UI labels. [JACOB] at the end.**

Today these are one blurred control. The plan requires three distinct things:

| Control | When it applies | What it does |
|---|---|---|
| Pause/Stop Mission follow-up | always | stops further follow-up, preserves prepared work |
| Cancel queued task | task queued, not started | existing Builder cancel |
| Stop current run | run active | `request_cancel`, signals the verified worker |

**What must be true**

1. The three controls are distinct in the API and in the UI.
2. `operator_cancel_task` still refuses in-flight/published tasks and is never
   used as a stand-in for run cancellation.
3. The UI reflects the runner's *durable* cancellation outcome, not success at
   button-click time.
4. Cancelling a run is never presented as undo, and never as proof that no
   external effect occurred.

**How it is proved**

- Backend tests for each control's refusal conditions.
- **[JACOB]** running-app pass: start a run, hit Stop current run, watch the UI
  wait for the durable outcome rather than claiming success immediately.

---

## P3-C — the browser stops being the only way home

**Status: backend landed (#843). Frontend not started. [JACOB].**

`GET /missions/by-origin` exists and works. `BuilderProposalCard.tsx` still
treats `localStorage` keyed by `chatId`+`messageIndex` as its recovery token.

**What must be true**

1. On mount, the card asks the server what this conversation delegated.
2. `localStorage` is a cache only — a hit is a speedup, a miss is not a loss.
3. Empty storage, a new browser, and a phone all recover the same work.
4. Message position is never used as identity.

**How it is proved**

- `gateway/kitty-chat/tests/BuilderProposalCard.test.tsx` extended: server
  recovery with storage empty; storage disagreeing with the server loses.
- **[JACOB]** running-app pass, desktop 1440px and phone 393px: approve a job,
  clear site data, reload, confirm the card comes back with the real state.

---

## P4-A — a project points at the action you chose

**Status: not started. Backend only. No acceptance gate.**

#844 made a todo's identity survive regeneration and gave it `project_id` and
`progress_note`. Nothing yet records *which* todo a project has selected, so
Home has nothing durable to prefer over generated suggestions.

**What must be true**

1. A project references its explicitly selected Todo by stable id.
2. Selecting a different Todo replaces the selection; deleting the selected
   Todo clears it rather than dangling.
3. Regenerating `project_next_steps` never changes the selection.
4. The selected personal project uses existing server-side preference storage —
   no new competing store.

**How it is proved**

- Store + route tests, including: regenerate suggestions, assert the selection
  and its progress note are untouched.

---

## P4-B — Home shows what you picked

**Status: not started. Frontend. [JACOB].**

Two defects Lane F found: generated suggestions outrank the chosen Todo, and
the UI mixes its own `active` with the backend's `in_progress`.

**What must be true**

1. The selected Todo appears above generated suggestions, always.
2. One status vocabulary end to end. No `active`-vs-`in_progress` mismatch.
3. `I did this` completes by id. `This is where I stopped` records progress
   without completing.
4. Completing does not force a new suggestion; `Choose the next step` is an
   honest fallback.
5. Home reads without a fresh model call.
6. System repair notices surface only when they block the chosen action.

**How it is proved**

- Component tests for ordering and the status vocabulary.
- **[JACOB]** running-app pass, desktop and phone.

---

## P4-C — it still works when things are down

**Status: not started. [JACOB] for the running-app half.**

**What must be true**

1. Model unavailable → stored and mechanical state still usable.
2. Calendar unavailable → no fabricated "free day" conclusion.
3. Builder unavailable → ordinary personal capture and continuation still work.
4. Every degraded surface says what failed and what you can do next. No raw
   server error as the primary message.

**How it is proved**

- Tests with each dependency forced unavailable.
- **[JACOB]** running-app pass with services actually stopped.

---

## Order

`P3-A → P4-A → P3-C → P4-B → P3-B → P4-C`

Backend-only work first (P3-A, P4-A) because it lands without waiting on
anyone. Then the two UI changes that need Jacob, batched so he reviews once
rather than four times. P3-B last because it is the largest and depends on the
control semantics being settled.

One mutating owner per seam; no two of these run in parallel.

## What "done" means for the whole thing

Not "the code is written". P3 and P4 are done when, on the running app:

- a request made in a chat comes back to that chat from a browser that has
  never seen it before, and
- an action you chose survives everything the system does around it.

Until both are true in the app, the backends are groundwork, not the outcome.
