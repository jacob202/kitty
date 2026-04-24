"""Tests for context budget and reasoning explanation surface."""
import pytest
from src.core.context_budget import ContextBudget, ContextSlot


# ── Context Budget ─────────────────────────────────────────────────────────────

def test_budget_enforces_total_limit():
    budget = ContextBudget(preset="compact")  # 800 chars total
    budget.add(ContextSlot.IDENTITY, "x" * 300)
    budget.add(ContextSlot.CORRECTIONS, "y" * 300)
    budget.add(ContextSlot.RECENT, "z" * 300)
    assembled = budget.assemble()
    assert len(assembled) <= budget.total_chars


def test_budget_respects_slot_priority():
    budget = ContextBudget(preset="compact")  # 800 chars total, drops EPHEMERAL
    budget.add(ContextSlot.IDENTITY, "identity_content " * 15)   # high priority
    budget.add(ContextSlot.CORRECTIONS, "correction_content " * 15)  # also in compact
    assembled = budget.assemble()
    assert "identity_content" in assembled


def test_budget_skips_empty_slots():
    budget = ContextBudget(preset="balanced")
    budget.add(ContextSlot.IDENTITY, "hello world")
    assembled = budget.assemble()
    assert "hello world" in assembled
    # No noisy double-newlines from empty slots
    assert "\n\n\n" not in assembled


def test_budget_empty_produces_empty_string():
    budget = ContextBudget(preset="balanced")
    assert budget.assemble() == ""


def test_budget_single_slot_no_separator():
    budget = ContextBudget(preset="balanced")
    budget.add(ContextSlot.CORRECTIONS, "one correction only")
    assert budget.assemble() == "one correction only"


def test_budget_compact_drops_ephemeral():
    """Compact preset should ignore EPHEMERAL slot entirely."""
    budget = ContextBudget(preset="compact")
    budget.add(ContextSlot.IDENTITY, "identity")
    budget.add(ContextSlot.EPHEMERAL, "should be dropped")
    assembled = budget.assemble()
    assert "identity" in assembled
    assert "should be dropped" not in assembled


def test_budget_verbose_allows_all_slots():
    """Verbose preset should allow all slots with generous budgets."""
    budget = ContextBudget(preset="verbose")
    budget.add(ContextSlot.IDENTITY, "i" * 400)
    budget.add(ContextSlot.CORRECTIONS, "c" * 400)
    budget.add(ContextSlot.PROJECT, "p" * 400)
    budget.add(ContextSlot.RECENT, "r" * 400)
    budget.add(ContextSlot.EPHEMERAL, "e" * 400)
    assembled = budget.assemble()
    assert "i" in assembled
    assert "c" in assembled
    assert "p" in assembled
    assert "r" in assembled
    assert "e" in assembled


# ── Reasoning Surface ──────────────────────────────────────────────────────────

@pytest.fixture()
def client():
    from web import create_app
    app, _ = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_reasoning_last_returns_200(client):
    resp = client.get("/api/reasoning/last")
    assert resp.status_code == 200


def test_reasoning_last_has_trace_key(client):
    data = client.get("/api/reasoning/last").get_json()
    assert "trace" in data


def test_reasoning_last_null_trace_has_note(client):
    data = client.get("/api/reasoning/last").get_json()
    if data["trace"] is None:
        assert "note" in data


def test_reasoning_last_trace_shape_when_present(client):
    data = client.get("/api/reasoning/last").get_json()
    trace = data.get("trace")
    if trace is not None:
        assert "id" in trace
        assert "steps" in trace
        assert isinstance(trace["steps"], list)


def test_reasoning_layer_sourced_from_orchestrator():
    """_get_reasoning_layer() must prefer current_app.orchestrator over the supervisor shim."""
    from web import create_app
    app, _ = create_app()
    app.config["TESTING"] = True
    
    # Simulate a case where orchestrator is None
    app.orchestrator = None
    with app.test_request_context("/"):
        from src.api.reasoning_routes import _get_reasoning_layer
        layer = _get_reasoning_layer()
        assert layer is None, "Should return None if orchestrator is None and no direct layer exists"

    # Simulate a case where orchestrator is present
    class MockReasoning:
        pass
    class MockOrch:
        def __init__(self):
            self.reasoning = MockReasoning()
    
    mock_orch = MockOrch()
    app.orchestrator = mock_orch
    with app.test_request_context("/"):
        layer = _get_reasoning_layer()
        assert layer is mock_orch.reasoning, "Should prefer orchestrator.reasoning"
