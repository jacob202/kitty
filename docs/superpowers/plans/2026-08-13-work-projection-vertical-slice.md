# Work Projection Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one read-only Gateway `GET /work` projection over existing Builder truth, with truthful state/evidence/approval semantics and no new persistence.

**Architecture:** `gateway/work_projection.py` is a pure product-language mapper over `builder_status.build_status_snapshot()`. `gateway/routes/work.py` is a thin fail-loud route. `gateway/routes/register.py` registers it. No Work code imports Builder DB/queue modules or writes state.

**Tech Stack:** Python 3.12, FastAPI, pytest.

## Global Constraints
- Gateway owns product truth; Builder owns execution truth.
- No direct Builder SQLite access from Work.
- Missing approval binding is `unavailable`, never inferred.
- No external writes, paid calls, credentials/auth, publishing, or service restart.
- TDD: every production behavior begins with a failing test.
- Repair cap: two verifier-driven cycles.

---

### Task 1: Pure Work projection
**Files:** Create `gateway/work_projection.py`; Create `tests/test_work_projection.py`.
**Consumes:** `BuilderStatusSnapshot`-shaped dict from `build_status_snapshot()`.
**Produces:** `build_work_projection(snapshot, observed_at=None) -> dict[str, Any]`.
- [ ] **Step 1: write RED state/evidence tests**
```python
def test_maps_running_packet_to_active_work():
    payload = build_work_projection(builder_snapshot(run_state="running"))
    assert payload["items"][0]["state"] == "active"
    assert payload["items"][0]["source"]["initiative_id"] == "KPROOF-X"

def test_missing_gateway_approval_binding_is_explicitly_unavailable():
    item = build_work_projection(builder_snapshot())["items"][0]
    assert item["approval"]["state"] == "unavailable"
    assert "binding" in item["approval"]["reason"].lower()
```
- [ ] **Step 2:** run `pytest tests/test_work_projection.py -q`; expected RED because module/function is absent.
- [ ] **Step 3:** implement the minimal pure mapper with deterministic current-packet selection, product states, bounded evidence summary, source health, and 30-second `valid_until`.
- [ ] **Step 4:** add table tests for `ready`, `blocked`, `paused`, `failed`, `completed`, partial integrity, and unavailable evidence; run focused tests GREEN.
- [ ] **Step 5:** run `git diff --check`; commit `feat(work): add authoritative Builder projection`.

### Task 2: Fail-loud Gateway route
**Files:** Create `gateway/routes/work.py`; Modify `gateway/routes/register.py`; Create `tests/test_work_routes.py`.
**Consumes:** `build_status_snapshot()` and `build_work_projection()`.
**Produces:** `GET /work` only; no mutation endpoint.
- [ ] **Step 1: write RED route tests**
```python
def test_get_work_returns_product_projection(client, monkeypatch):
    monkeypatch.setattr(work_route, "build_status_snapshot", lambda: builder_snapshot())
    response = client.get("/work")
    assert response.status_code == 200
    assert response.json()["items"][0]["source"]["kind"] == "builder"

def test_get_work_fails_loud_when_builder_snapshot_unavailable(client, monkeypatch):
    monkeypatch.setattr(work_route, "build_status_snapshot", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    response = client.get("/work")
    assert response.status_code == 503
    assert "boom" in response.json()["detail"]
```
- [ ] **Step 2:** run `pytest tests/test_work_routes.py -q`; expected RED because route is absent.
- [ ] **Step 3:** add the thin route and register it; catch snapshot exceptions as HTTP 503 with concrete bounded detail.
- [ ] **Step 4:** run Work route/projection tests plus `tests/test_builder_status_readonly.py` and `tests/test_architecture_fitness.py` GREEN.
- [ ] **Step 5:** commit `feat(work): expose Gateway Work route`.

### Task 3: Evidence and independent acceptance
**Files:** Modify only outcome-contract verifier table/final state after evidence exists.
**Consumes:** reviewed SHA, canonical Builder DB, exact test commands.
**Produces:** reproducible receipt and independent criterion verdicts.
- [ ] **Step 1:** run the focused suite and `git diff --check` on the reviewed SHA.
- [ ] **Step 2:** point only `KITTY_BUILDER_DATA_DIR` at the canonical local Builder data and call the Work projection read path; record KPROOF identity/state without modifying the DB.
- [ ] **Step 3:** run an independent review-only tool process with only the outcome contract, changed SHA/diff, and allowed checks. It must return `PASS`, `FAIL`, or `UNVERIFIED` for AC-1..AC-5.
- [ ] **Step 4:** if FAIL, repair only named gaps, maximum two cycles; rerun focused checks and verifier.
- [ ] **Step 5:** update the outcome contract with exact evidence and final state. Do not push or merge.

## Self-review
- Spec coverage: this plan covers only the first approved vertical-slice packet; Console and Discord consumption intentionally follow after this API is independently accepted.
- Placeholder scan: none.
- Type consistency: one mapper `build_work_projection(snapshot, observed_at=None)` feeds one read-only `GET /work` route.
- Authority check: Work reads supported Builder projection only; no new durable state or approval inference.

## Execution choice
The campaign prompt already authorizes autonomous sequential execution. Use **Inline Execution** in this session so the campaign lead retains integration ownership while a separate process performs final review.