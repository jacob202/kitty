# KF-GLANCE-01 — Home gets one bounded primary read model

**Initiative:** `kitty-opens-the-doors-20260831-v1`
**Owner:** builder
**Depends on:** none
**Free or paid:** free
**Base:** `origin/main` `546565246289e6730b518961de64b7f371013b3b`

## Outcome boundary
This packet implements and mechanically proves the backend half of the one-response Home outcome. It makes **no standalone visible-completion claim**: Jacob gets the visible result only after the dependent interactive packet `KF-GLANCE-02` lands. That packet owns the one-sentence user outcome, all four standing visible criteria in Packet Standard §7, Tier 2 browser proof, and Tier 3 independent product acceptance. Never report `KF-GLANCE-01` alone as a shipped Home experience.

## Publication ownership
This companion document was already owned by draft PR #728. Saul is updating that same lane and adding its manifest there; no second implementation or documentation lane is being created. Before publication or Builder apply, re-fetch PR #728 and PRs #722 and #725–#731. Stop if another live lane now touches any worker path or if this companion document is no longer owned by PR #728.

## Why this is the next thing
`gateway/kitty-chat/src/components/HomeState.tsx:753-761` makes What's Next wait on actions, needs-Jacob, projects, project next steps, todos, and session context; `984-986`, `1264-1266`, `1494-1499`, and `1735-1745` repeat project, deadline, action, inbox, and todo reads for neighboring cards. The primary Home grid at `1982-1989` therefore starts as a fan-out of independent requests.

The backend already has the right failure boundary. `gateway/state_composer.py:48-70` runs named sources independently and emits `{ok: true, ...}` or `{ok: false, error}` per section. Its current `SOURCES` at `178-185` already cover todos, inbox, journal, chats, calendar, and signals, but not proposed actions, needs-Jacob decisions, projects/next steps, or deadlines.

`_diff_sections` at `113-130` compares the union of section names and ignores list/dict display detail, so adding sections is compatible with old snapshots. One extra defect belongs in this packet: each future currently receives its own three-second `future.result(timeout=...)`; several hung sources can therefore stack into a response much longer than the stated source timeout.

## Plan
1. In `gateway/state_composer.py`, import the framework-free sources directly — never the FastAPI route modules. Build `actions` from `action_queue.list_actions(status="proposed", limit=50)`, `needs_jacob` from `triage.list_triaged(bucket="needs_jacob", limit=20)`, `projects` from `project_store.list_projects()`, `project_next_steps` from `next_step.select_steps(limit=3)` plus `next_step.get(project_id)` for the first four active projects Home can display, and `deadlines` from `deadline_store.list_open(status="open")`.
2. Keep each section bounded and diff-friendly: retain scalar counts (`proposed_count`, `count`, `total_count`/`active_count`, `selected_count`, `open_count`) beside only the rows Home renders (actions ≤50, decisions ≤20, active projects ≤4, curated next steps ≤3 plus stored steps for those four active projects, deadlines ≤4). Keep the existing `todos.open_count` and `todos.latest` keys intact and add only the first five open todo rows. Do not add a second store or cache.
3. Keep session context, weather, health/system diagnostics, experts, Builder status, and other disclosure-only data out of this primary read model. They may hydrate after the first useful paint in `KF-GLANCE-02`.
4. Preserve the section contract exactly: one source failure or timeout becomes only that section's `{ok: false, error}` and never raises the entire response.
5. Change the fan-out wait so the composed response has one overall wall-clock deadline rather than multiplying the timeout by the number of hung sources. Fast sections that finish before the deadline must still be returned.
6. Extend `tests/test_state_composer.py` first with RED coverage for the five new sections and their bounded/count contracts, both next-step projections, independent section failure, and two simultaneously hung sources completing within one bounded wall-clock budget.
7. Extend `tests/test_state_route.py` only as needed to prove `/state/now` and `/state/changes` continue returning the stable route contract after the new sections are present.

The risky part is the timeout change: do not replace a timed-out section with an empty healthy value, and do not wait for executor shutdown after the response deadline.

## Not in scope
Changing any frontend file. Adding a new HTTP route. Replacing `state_composer` with a second cache or registry. Pulling the full health surface, weather, experts, session context, Builder state, or other secondary Home disclosures into this response. Changing snapshot storage or the meaning of existing scalar diffs.

This packet creates no new production files.

## Verification
**Tier 1 — mechanical.** `python -m pytest -q tests/test_state_composer.py tests/test_state_route.py` and `python -m ruff check gateway/state_composer.py tests/test_state_composer.py tests/test_state_route.py`.

Fresh Saul baseline at this exact base: the existing pytest gate is green (`13 passed in 0.98s`) and Ruff reports `All checks passed!`, because the committed tests do not yet assert the new behavior. That green baseline is **not** acceptance proof.

The required RED gate was observed at this exact base by temporarily adding the following characterization to the already-allowed `tests/test_state_composer.py`, running the exact pytest validation command, recording the result, and then removing the temporary edit so this planning PR does not implement the worker's test:

```python
def test_default_sources_include_primary_home_sections():
    required = {"actions", "needs_jacob", "projects", "project_next_steps", "deadlines"}
    assert required <= set(state_composer.SOURCES)
```

Observed output: `FAILED tests/test_state_composer.py::test_default_sources_include_primary_home_sections` with the five required names reported as extra items on the left; summary `1 failed, 13 passed in 0.83s`. Before production edits, the worker must restore this characterization (or a stricter equivalent), add the bounded-shape and overall-wall-clock assertions from the plan, re-run the same command to preserve RED evidence, then make the implementation pass them.

**Tier 2 — running app.** Not applicable to this deliberately non-visible backend prerequisite. `KF-GLANCE-02` owns the browser spec, desktop and iPhone-class runs, independent degradation, control usability, plain-language errors, state truthfulness, and overflow proof.

**Tier 3 — product acceptance.** Not applicable to this deliberately non-visible backend prerequisite. `KF-GLANCE-02` owns the independent running-app reviewer and must not claim the combined Home outcome until both packets are integrated.

## Stop condition
If any requested primary section can only be obtained by creating a parallel store/cache or by importing a FastAPI route module in a way that creates an import cycle, stop and report the section and its existing source instead of duplicating state.

## Recovery
All changes are pure read composition plus tests. If the attempt fails, revert only this packet's dirty changes and restart from the source list; no data migration, schedule mutation, network side effect, push, PR, or merge is permitted.
