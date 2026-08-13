# Gateway Work Spine v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose one read-only Gateway Work API that projects KittyBuilder durable task state for Discord and Console consumers.

**Architecture:** Add a pure `gateway/work_spine.py` projection layer over public `gateway.builder_queue` read APIs, then expose it through `gateway/routes/work.py`. Builder remains authoritative; v1 adds no Work database, no writes, and no new state machine.

**Tech Stack:** Python 3.12, FastAPI, existing KittyBuilder SQLite facade, pytest, Ruff.

## Global Constraints

- Read-only projection: never mutate Builder state or SQLite.
- Work IDs are `builder:<builder_task_id>`.
- Expose normalized `state` and exact `source_state`.
- Never infer completion from PR state; Builder task `done` is authoritative.
- Missing evidence stays missing; source failures fail visibly.
- No Discord, Console, image/chat/project adapter, SSE/WebSocket, approval, retry, cancel, or Builder execution changes.

---

## File structure

- Create `gateway/work_spine.py`: Builder-to-Work projection and read functions only.
- Create `gateway/routes/work.py`: HTTP validation/error translation only.
- Modify `gateway/routes/register.py`: register the new router.
- Create `tests/test_work_spine.py`: pure projection/state/evidence tests.
- Create `tests/test_work_routes.py`: focused FastAPI route tests.

### Task 1: Builder Work projection

**Files:**
- Create: `gateway/work_spine.py`
- Create: `tests/test_work_spine.py`

**Interfaces:**
- Consumes: `builder_queue.list_tasks()`, `get_task()`, `list_events()`, `list_runs()`, `get_pr_links()`.
- Produces: `list_work(*, state: str | None = None, source: str | None = None, limit: int = 50) -> list[dict]`, `get_work(work_id: str) -> dict | None`, `get_work_events(work_id: str) -> list[dict]`.

- [ ] Step 1: write failing state and identity tests for every known Builder state, `builder:<task_id>` identity, and unknown-state rejection.
- [ ] Step 2: run `python -m pytest -q tests/test_work_spine.py`; expect failure because `gateway.work_spine` does not exist.
- [ ] Step 3: implement `WorkProjectionError`, the explicit Builder-to-Work state mapping, namespaced identity parsing, and pure task projection.
- [ ] Step 4: run `python -m pytest -q tests/test_work_spine.py`; expect state and identity tests to pass.

The state mapping must be explicit:

```python
BUILDER_STATE_MAP = {
    "queued": "pending",
    "claimed": "pending",
    "running": "running",
    "blocked": "blocked",
    "awaiting_review": "review",
    "pr_opened": "review",
    "done": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
}
```

- [ ] Step 5: add tests for latest-run, latest-PR, blocker/error, final-report evidence, and missing optional evidence.
- [ ] Step 6: implement Builder read composition using only public facade functions. Latest run is the last item from `list_runs(task_id=...)`; latest PR is the last item from `get_pr_links(task_id)`.
- [ ] Step 7: add list filtering tests for normalized `state`, `source="builder"`, and bounded `limit`; reject unsupported sources and non-positive limits with `ValueError`.
- [ ] Step 8: add event tests proving source order, timestamps, source event type, payload, task/run identity, and no event reordering.
- [ ] Step 9: run `python -m pytest -q tests/test_work_spine.py`; expect all projection tests PASS.
- [ ] Step 10: commit the projection unit.

### Task 2: Read-only Work HTTP API

**Files:**
- Create: `gateway/routes/work.py`
- Modify: `gateway/routes/register.py`
- Create: `tests/test_work_routes.py`

**Interfaces:**
- Consumes: Task 1 `list_work`, `get_work`, `get_work_events`, `WorkProjectionError`.
- Produces: `GET /work`, `GET /work/{work_id}`, `GET /work/{work_id}/events`.

- [ ] Step 1: write route tests using a small `FastAPI()` + `app.include_router(work_route.router)` fixture.
- [ ] Step 2: assert `/work` returns projected items and forwards `state`, `source`, and `limit` query values.
- [ ] Step 3: assert `/work/builder:kb_123` returns one item; unknown work IDs return HTTP 404.
- [ ] Step 4: assert `/work/builder:kb_123/events` returns normalized chronological events.
- [ ] Step 5: assert unsupported filters return HTTP 400 and Builder read/projection failures return HTTP 503 rather than `200 []`.
- [ ] Step 6: run `python -m pytest -q tests/test_work_routes.py`; expect RED because the route does not exist.
- [ ] Step 7: implement an `APIRouter(tags=["work"])` and the three GET handlers. Translate `ValueError` to 400, unknown work to 404, and source/projection/storage failures to 503 without exposing raw secrets or environment values.
- [ ] Step 8: register `work` in `gateway/routes/register.py` using the existing module tuple pattern.
- [ ] Step 9: run `python -m pytest -q tests/test_work_routes.py`; expect PASS.
- [ ] Step 10: commit the HTTP unit.
