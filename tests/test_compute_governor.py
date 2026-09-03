"""Contract tests for the compute governor's spend decisions."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from gateway import compute_governor as cg

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
SHA_A = "a" * 40
SHA_B = "b" * 40


@pytest.fixture()
def db(tmp_path: Path) -> Path:
    path = tmp_path / "receipts.db"
    cg.init_db(path)
    return path


def _dispatch(**overrides) -> cg.Dispatch:
    base = {
        "task_type": "review",
        "work_kind": "independent_review",
        "subject_ref": "pr/276",
        "head_sha": SHA_A,
        "artifact": "gateway/compute_governor.py",
        "acceptance_tests": ("python -m pytest tests/test_compute_governor.py -q",),
        "allowed_scope": ("gateway/", "tests/"),
        "exclusions": ("data/", "logs/"),
        "risk_class": "routine",
        "stopping_condition": "acceptance tests pass or a named defect is filed",
    }
    base.update(overrides)
    return cg.Dispatch(**base)


def _reserve(spent: float = 0.0, budget: float = 20.0) -> cg.ReserveState:
    return cg.ReserveState(weekly_budget_cad=budget, estimated_spend_cad=spent)


# --- deduplication ---------------------------------------------------------


def test_settled_pass_blocks_a_second_pass_on_the_same_sha(db: Path):
    dispatch = _dispatch()
    first = cg.decide(db, dispatch, reserve=_reserve())
    assert first.action == cg.ACTION_RUN

    cg.record_receipt(db, dispatch, outcome=cg.OUTCOME_SETTLED, route=cg.ROUTE_CHEAP, now=NOW)
    second = cg.decide(db, dispatch, reserve=_reserve())

    assert second.action == cg.ACTION_REJECT
    assert any("nothing changed since" in reason for reason in second.reasons)


def test_a_failed_pass_does_not_consume_the_allowance(db: Path):
    # Work that failed is still owed. Only a settled pass spends the budget.
    dispatch = _dispatch()
    cg.record_receipt(db, dispatch, outcome=cg.OUTCOME_FAILED, route=cg.ROUTE_CHEAP, retries=1, now=NOW)

    assert cg.decide(db, dispatch, reserve=_reserve()).action == cg.ACTION_RUN


def test_recording_two_settled_passes_for_one_sha_fails_loud(db: Path):
    dispatch = _dispatch()
    cg.record_receipt(db, dispatch, outcome=cg.OUTCOME_SETTLED, route=cg.ROUTE_CHEAP, now=NOW)

    with pytest.raises(cg.GovernorError, match="already exists"):
        cg.record_receipt(db, dispatch, outcome=cg.OUTCOME_SETTLED, route=cg.ROUTE_CHEAP, now=NOW)


def test_plan_and_review_are_budgeted_separately(db: Path):
    # One planning pass AND one review per SHA — a settled plan must not block
    # the independent review that checks it.
    plan = _dispatch(task_type="plan", work_kind="planning_pass")
    cg.record_receipt(db, plan, outcome=cg.OUTCOME_SETTLED, route=cg.ROUTE_CHEAP, now=NOW)

    assert cg.decide(db, _dispatch(), reserve=_reserve()).action == cg.ACTION_RUN
    assert cg.decide(db, plan, reserve=_reserve()).action == cg.ACTION_REJECT


# --- changed-SHA reauthorization ------------------------------------------


def test_new_head_sha_reauthorizes_the_work(db: Path):
    cg.record_receipt(db, _dispatch(), outcome=cg.OUTCOME_SETTLED, route=cg.ROUTE_CHEAP, now=NOW)

    moved = cg.decide(db, _dispatch(head_sha=SHA_B), reserve=_reserve())

    assert moved.action == cg.ACTION_RUN


def test_changed_requirements_change_the_dispatch_fingerprint(db: Path):
    original = _dispatch()
    amended = _dispatch(acceptance_tests=("python -m pytest tests/ -q", "ruff check gateway/"))

    assert original.fingerprint() != amended.fingerprint()


def test_blocker_evidence_alone_does_not_change_the_fingerprint(db: Path):
    # Naming a new reason to escalate is not a changed requirement; if it were,
    # any dispatch could re-authorize itself by restating urgency.
    plain = _dispatch(risk_class="risky")
    escalated = _dispatch(risk_class="risky", blocker_evidence="CI red on typecheck")

    assert plain.fingerprint() == escalated.fingerprint()


# --- override behaviour ----------------------------------------------------


def test_human_override_reauthorizes_a_settled_pass(db: Path):
    dispatch = _dispatch()
    cg.record_receipt(db, dispatch, outcome=cg.OUTCOME_SETTLED, route=cg.ROUTE_CHEAP, now=NOW)

    decision = cg.decide(db, dispatch, reserve=_reserve(), override_reason="Jacob: reviewer was wrong")

    assert decision.action == cg.ACTION_RUN
    assert any("human override" in reason for reason in decision.reasons)


def test_blank_override_is_not_an_override(db: Path):
    dispatch = _dispatch()
    cg.record_receipt(db, dispatch, outcome=cg.OUTCOME_SETTLED, route=cg.ROUTE_CHEAP, now=NOW)

    assert cg.decide(db, dispatch, reserve=_reserve(), override_reason="   ").action == cg.ACTION_REJECT


# --- rejected work kinds and incomplete dispatches -------------------------


@pytest.mark.parametrize("work_kind", sorted(cg.REJECTED_WORK_KINDS))
def test_rejected_work_kinds_never_run(db: Path, work_kind: str):
    decision = cg.decide(db, _dispatch(work_kind=work_kind), reserve=_reserve())

    assert decision.action == cg.ACTION_REJECT
    assert decision.route is None


def test_dispatch_missing_scope_and_tests_is_rejected_with_reasons(db: Path):
    decision = cg.decide(db, _dispatch(acceptance_tests=(), allowed_scope=()), reserve=_reserve())

    assert decision.action == cg.ACTION_REJECT
    assert any("acceptance_tests" in error for error in decision.errors)
    assert any("allowed_scope" in error for error in decision.errors)


def test_blocker_risk_class_requires_evidence(db: Path):
    decision = cg.decide(db, _dispatch(risk_class="blocker"), reserve=_reserve())

    assert decision.action == cg.ACTION_REJECT
    assert any("blocker_evidence" in error for error in decision.errors)


# --- routing ---------------------------------------------------------------


def test_routine_work_routes_to_the_cheap_model(db: Path):
    decision = cg.decide(db, _dispatch(), reserve=_reserve())

    assert (decision.action, decision.route) == (cg.ACTION_RUN, cg.ROUTE_CHEAP)
    assert any("deepseek-v4-flash" in reason for reason in decision.reasons)


def test_verified_blocker_routes_to_frontier(db: Path):
    dispatch = _dispatch(risk_class="blocker", blocker_evidence="pytest fails on main at HEAD")

    decision = cg.decide(db, dispatch, reserve=_reserve())

    assert (decision.action, decision.route) == (cg.ACTION_RUN, cg.ROUTE_FRONTIER)
    assert any("pytest fails on main" in reason for reason in decision.reasons)


# --- reserve enforcement ---------------------------------------------------


def test_frontier_downgrades_to_free_below_the_frontier_floor(db: Path):
    dispatch = _dispatch(risk_class="risky")

    decision = cg.decide(db, dispatch, reserve=_reserve(spent=16.0))  # 20% left

    assert (decision.action, decision.route) == (cg.ACTION_DOWNGRADE, cg.ROUTE_CHEAP)


def test_routine_work_defers_when_it_cannot_be_afforded(db: Path):
    # The floors guard the frontier route, but nothing may run on money that
    # is not there. 6 CAD budget, 5.999 spent: one cheap pass costs more.
    decision = cg.decide(db, _dispatch(), reserve=_reserve(spent=5.999, budget=6.0))

    assert decision.action == cg.ACTION_DEFER
    assert any("cheap route projects" in reason for reason in decision.reasons)


def test_frontier_downgrades_when_the_pass_costs_more_than_is_left(db: Path):
    # Above the ratio floor (35% left) but below the price of one frontier
    # pass: a small weekly budget makes the ratio look healthier than the money.
    dispatch = _dispatch(risk_class="risky")

    decision = cg.decide(db, dispatch, reserve=_reserve(spent=0.13, budget=0.20))

    assert (decision.action, decision.route) == (cg.ACTION_DOWNGRADE, cg.ROUTE_CHEAP)
    assert any("rather than overrunning the week" in reason for reason in decision.reasons)


def test_frontier_defers_below_the_hard_floor(db: Path):
    dispatch = _dispatch(risk_class="risky")

    decision = cg.decide(db, dispatch, reserve=_reserve(spent=19.5))  # 2.5% left

    assert decision.action == cg.ACTION_DEFER
    assert decision.route is None


def test_reserve_floors_do_not_stall_routine_work(db: Path):
    # The ratio floors guard the frontier route only. Routine work runs while it
    # is still affordable, because a stalled repair costs more than it saves.
    decision = cg.decide(db, _dispatch(), reserve=_reserve(spent=19.9))

    assert (decision.action, decision.route) == (cg.ACTION_RUN, cg.ROUTE_CHEAP)


def test_zero_budget_reserve_fails_loud(db: Path):
    with pytest.raises(cg.GovernorError, match="weekly_budget_cad"):
        cg.ReserveState(weekly_budget_cad=0.0, estimated_spend_cad=0.0).remaining_ratio


# --- retry accounting and the weekly ledger --------------------------------


def test_retries_accumulate_across_attempts_on_one_sha(db: Path):
    dispatch = _dispatch()
    cg.record_receipt(db, dispatch, outcome=cg.OUTCOME_FAILED, route=cg.ROUTE_CHEAP, retries=2, now=NOW)
    cg.record_receipt(db, dispatch, outcome=cg.OUTCOME_FAILED, route=cg.ROUTE_CHEAP, retries=1, now=NOW)

    # 3 declared retries plus the second attempt itself.
    assert cg.count_retries(db, task_type="review", subject_ref="pr/276", head_sha=SHA_A) == 4


def test_negative_retries_are_rejected(db: Path):
    with pytest.raises(cg.GovernorError, match="retries"):
        cg.record_receipt(db, _dispatch(), outcome=cg.OUTCOME_FAILED, route=cg.ROUTE_CHEAP, retries=-1)


def test_weekly_ledger_totals_by_route_and_labels_itself_an_estimate(db: Path):
    cg.record_receipt(
        db, _dispatch(), outcome=cg.OUTCOME_SETTLED, route=cg.ROUTE_CHEAP,
        model="qwen3-coder:free", estimated_usage_cad=0.0, now=NOW,
    )
    cg.record_receipt(
        db, _dispatch(task_type="plan", work_kind="planning_pass", risk_class="risky"),
        outcome=cg.OUTCOME_SETTLED, route=cg.ROUTE_FRONTIER,
        model="deepseek-v4-pro", retries=1, estimated_usage_cad=0.42, now=NOW,
    )

    ledger = cg.weekly_ledger(db, week_of=date(2026, 7, 26))

    assert ledger["runs"] == 2
    assert ledger["retries"] == 1
    assert ledger["estimated_usage_cad"] == pytest.approx(0.42)
    assert ledger["estimated_usage_cad_by_route"] == {"cheap": 0.0, "frontier": 0.42}
    assert "NOT a provider meter" in ledger["basis"]


def test_ledger_excludes_other_weeks(db: Path):
    cg.record_receipt(
        db, _dispatch(), outcome=cg.OUTCOME_SETTLED, route=cg.ROUTE_CHEAP,
        estimated_usage_cad=1.0, now=datetime(2026, 7, 12, tzinfo=timezone.utc),
    )

    assert cg.weekly_ledger(db, week_of=date(2026, 7, 26))["runs"] == 0


# --- config ----------------------------------------------------------------


def test_reserve_config_defaults_when_absent(tmp_path: Path):
    assert cg.load_reserve_config(tmp_path / "missing.json") == cg.DEFAULT_RESERVE_CONFIG


def test_malformed_reserve_config_fails_loud(tmp_path: Path):
    path = tmp_path / "compute_governor.json"
    path.write_text('{"weekly_budget_cad": -3}', encoding="utf-8")

    with pytest.raises(cg.GovernorError, match="positive number"):
        cg.load_reserve_config(path)


def test_inverted_floors_fail_loud(tmp_path: Path):
    path = tmp_path / "compute_governor.json"
    path.write_text(json.dumps({"hard_floor_ratio": 0.5, "frontier_floor_ratio": 0.25}), encoding="utf-8")

    with pytest.raises(cg.GovernorError, match="hard_floor_ratio"):
        cg.load_reserve_config(path)


def test_reserve_from_ledger_reflects_recorded_spend(db: Path):
    cg.record_receipt(
        db, _dispatch(), outcome=cg.OUTCOME_SETTLED, route=cg.ROUTE_FRONTIER,
        estimated_usage_cad=5.0, now=NOW,
    )

    reserve = cg.reserve_from_ledger(db, cg.DEFAULT_RESERVE_CONFIG, week_of=date(2026, 7, 26))

    budget = cg.DEFAULT_RESERVE_CONFIG["weekly_budget_cad"]
    assert reserve.estimated_spend_cad == pytest.approx(5.0)
    assert reserve.remaining_ratio == pytest.approx((budget - 5.0) / budget)


# --- dispatch parsing and the dry-run explainer ----------------------------


def test_dispatch_from_mapping_requires_identity_keys():
    with pytest.raises(cg.GovernorError, match="missing required keys"):
        cg.dispatch_from_mapping({"task_type": "review"})


def test_explain_names_the_action_and_every_reason(db: Path):
    decision = cg.decide(db, _dispatch(acceptance_tests=()), reserve=_reserve())

    text = cg.explain(decision)

    assert text.startswith("REJECT")
    assert "acceptance_tests" in text


# --- cost estimation -------------------------------------------------------


def test_pass_costs_come_from_the_shared_price_registry():
    # Recomputed by hand from gateway/token_spend_report's snapshot prices:
    # OpenRouter Flash 60k in @ 0.09 + 8k out @ 0.18 = 0.00684 USD; pro 120k in @ 0.435 +
    # 15k out @ 0.87 = 0.06525 USD. Both converted at the recorded FX rate.
    from gateway.token_spend_report import USD_TO_CAD

    assert cg.estimate_pass_cost_cad(cg.ROUTE_CHEAP) == pytest.approx(0.00684 * USD_TO_CAD)
    assert cg.estimate_pass_cost_cad(cg.ROUTE_FRONTIER) == pytest.approx(0.06525 * USD_TO_CAD)


def test_the_free_ladder_costs_nothing():
    assert cg.estimate_pass_cost_cad(cg.ROUTE_FREE) == 0.0


def test_cached_input_is_priced_at_the_cached_rate():
    plain = cg.estimate_cost_cad("deepseek-v4-pro", input_tokens=100_000, output_tokens=0)
    cached = cg.estimate_cost_cad(
        "deepseek-v4-pro", input_tokens=0, output_tokens=0, cached_input_tokens=100_000
    )

    assert cached < plain


def test_an_unpriced_model_fails_loud_instead_of_costing_zero():
    with pytest.raises(cg.GovernorError, match="no snapshot price"):
        cg.estimate_cost_cad("some-new-model", input_tokens=1000, output_tokens=100)


def test_unknown_route_fails_loud():
    with pytest.raises(cg.GovernorError, match="unknown route"):
        cg.estimate_pass_cost_cad("premium")


def test_default_budget_covers_a_modelled_week_without_downgrading():
    # 10 tasks x 3 head SHAs x (plan + review + implement), 85% routine.
    config = cg.DEFAULT_RESERVE_CONFIG
    passes = 10 * 3 * 3
    routine = int(passes * 0.85)
    modelled = (
        routine * cg.estimate_pass_cost_cad(cg.ROUTE_CHEAP)
        + (passes - routine) * cg.estimate_pass_cost_cad(cg.ROUTE_FRONTIER)
    ) * 1.5  # retry headroom

    downgrade_at = config["weekly_budget_cad"] * (1 - config["frontier_floor_ratio"])

    assert modelled < downgrade_at, (
        f"a modelled week costs CAD {modelled:.2f} but the frontier floor bites at "
        f"CAD {downgrade_at:.2f} spent — recompute the budget"
    )


def test_explicit_free_route_runs_without_spend_even_when_reserve_is_empty(db: Path):
    dispatch = _dispatch(requested_route=cg.ROUTE_FREE)

    decision = cg.decide(db, dispatch, reserve=_reserve(spent=20.0, budget=20.0))

    assert (decision.action, decision.route) == (cg.ACTION_RUN, cg.ROUTE_FREE)
    assert cg.estimate_pass_cost_cad(decision.route) == 0.0


def test_requested_route_is_part_of_dispatch_identity():
    free = _dispatch(requested_route=cg.ROUTE_FREE)
    paid = _dispatch(requested_route=cg.ROUTE_CHEAP)

    assert free.fingerprint() != paid.fingerprint()


def test_dispatch_from_mapping_preserves_requested_route():
    payload = {
        "task_type": "implement",
        "work_kind": "implementation",
        "subject_ref": "init/p1",
        "head_sha": SHA_A,
        "artifact": "packet init/p1",
        "acceptance_tests": ["pytest -q"],
        "allowed_scope": ["gateway/"],
        "exclusions": ["data/"],
        "risk_class": "routine",
        "stopping_condition": "tests pass",
        "requested_route": "free",
    }

    dispatch = cg.dispatch_from_mapping(payload)

    assert dispatch.requested_route == cg.ROUTE_FREE

# --- routing policy receipt snapshots -------------------------------------


def test_record_receipt_round_trips_canonical_routing_policy(db: Path):
    policy = {
        "harness": {"name": "coding", "workspace_mode": "write"},
        "handoff": {"context_mode": "artifacts_compact"},
        "worker_candidates": ["openrouter/model-a", "openrouter/model-b"],
        "budget": {"weekly_cad": 6.0, "per_attempt_cad": 0.10},
    }

    receipt_id = cg.record_receipt(
        db,
        _dispatch(),
        outcome=cg.OUTCOME_SETTLED,
        route=cg.ROUTE_CHEAP,
        policy=policy,
        now=NOW,
    )

    with cg.connect(db) as conn:
        row = conn.execute(
            "SELECT policy_json FROM work_receipts WHERE receipt_id = ?", (receipt_id,)
        ).fetchone()

    assert json.loads(row["policy_json"]) == policy
    assert row["policy_json"] == json.dumps(
        policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def test_init_db_adds_policy_column_to_legacy_receipt_store(tmp_path: Path):
    legacy = tmp_path / "legacy.db"
    with sqlite3.connect(legacy) as conn:
        conn.executescript(
            """
            CREATE TABLE work_receipts (
                receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                subject_ref TEXT NOT NULL,
                head_sha TEXT NOT NULL,
                dispatch_hash TEXT NOT NULL,
                work_kind TEXT NOT NULL,
                risk_class TEXT NOT NULL,
                route TEXT NOT NULL,
                model TEXT,
                provider TEXT,
                outcome TEXT NOT NULL,
                retries INTEGER NOT NULL DEFAULT 0,
                estimated_usage_cad REAL NOT NULL DEFAULT 0.0,
                override_reason TEXT,
                created_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX idx_receipts_settled_pass
                ON work_receipts(task_type, subject_ref, head_sha)
                WHERE outcome = 'settled' AND override_reason IS NULL;
            """
        )

    cg.init_db(legacy)

    with cg.connect(legacy) as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(work_receipts)")}
    assert "policy_json" in columns


def test_non_json_routing_policy_fails_before_recording_receipt(db: Path):
    with pytest.raises(cg.GovernorError, match="policy must be JSON-serializable"):
        cg.record_receipt(
            db,
            _dispatch(),
            outcome=cg.OUTCOME_SETTLED,
            route=cg.ROUTE_CHEAP,
            policy={"bad": object()},
            now=NOW,
        )

    with cg.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM work_receipts").fetchone()[0] == 0



def test_init_db_concurrently_migrates_legacy_policy_column(tmp_path: Path):
    from concurrent.futures import ThreadPoolExecutor

    legacy = tmp_path / "legacy-concurrent.db"
    with sqlite3.connect(legacy) as conn:
        conn.executescript(
            """
            CREATE TABLE work_receipts (
                receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                subject_ref TEXT NOT NULL,
                head_sha TEXT NOT NULL,
                dispatch_hash TEXT NOT NULL,
                work_kind TEXT NOT NULL,
                risk_class TEXT NOT NULL,
                route TEXT NOT NULL,
                model TEXT,
                provider TEXT,
                outcome TEXT NOT NULL,
                retries INTEGER NOT NULL DEFAULT 0,
                estimated_usage_cad REAL NOT NULL DEFAULT 0.0,
                override_reason TEXT,
                created_at TEXT NOT NULL
            );
            """
        )

    for _ in range(20):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: cg.init_db(legacy), range(8)))

    with cg.connect(legacy) as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(work_receipts)")}
    assert "policy_json" in columns


def test_connect_retries_transient_wal_lock(tmp_path: Path, monkeypatch):
    import time as time_module

    calls: list[str] = []
    sleeps: list[float] = []

    class FakeCursor:
        def __init__(self, value: str):
            self.value = value

        def fetchone(self):
            return (self.value,)

    class FakeConnection:
        row_factory = None
        wal_attempts = 0
        wal_enabled = False

        def execute(self, sql: str):
            calls.append(sql)
            if sql == "PRAGMA journal_mode":
                return FakeCursor("wal" if self.wal_enabled else "delete")
            if sql == "PRAGMA journal_mode=WAL":
                self.wal_attempts += 1
                if self.wal_attempts == 1:
                    raise sqlite3.OperationalError("database is locked")
                self.wal_enabled = True
                return FakeCursor("wal")
            return FakeCursor("")

    fake = FakeConnection()

    monkeypatch.setattr(cg.sqlite3, "connect", lambda *_args, **_kwargs: fake)
    monkeypatch.setattr(time_module, "sleep", sleeps.append)
    assert cg.connect(tmp_path / "busy.db") is fake
    assert fake.wal_attempts == 2
    assert sleeps


def test_connect_sets_busy_timeout_before_wal(tmp_path: Path, monkeypatch):
    calls: list[str] = []

    class FakeCursor:
        def fetchone(self):
            return ("delete",)

    class FakeConnection:
        row_factory = None

        def execute(self, sql: str):
            calls.append(sql)
            return FakeCursor()

    fake = FakeConnection()

    def fake_connect(path, *, timeout):
        assert path == tmp_path / "busy.db"
        assert timeout >= 30.0
        return fake

    monkeypatch.setattr(cg.sqlite3, "connect", fake_connect)
    assert cg.connect(tmp_path / "busy.db") is fake
    assert calls[:3] == [
        "PRAGMA busy_timeout=30000",
        "PRAGMA journal_mode",
        "PRAGMA journal_mode=WAL",
    ]
