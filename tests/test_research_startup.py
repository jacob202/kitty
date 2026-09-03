from gateway import app as gateway_app


def test_gateway_startup_reconciles_interrupted_research(monkeypatch):
    calls = []
    monkeypatch.setattr('gateway.research_runs.reconcile_interrupted', lambda: calls.append(True) or 2)

    gateway_app._reconcile_research_runs_on_startup()

    assert calls == [True]
