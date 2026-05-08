import json

from scripts import daily_flow_scorecard as scorecard


def test_run_scorecard_all_pass(monkeypatch):
    def fake_request_json(url, method="GET", payload=None):
        if url.endswith("/api/brief"):
            return 200, {"next_action": "Do thing"}, "{}"
        if url.endswith("/api/chat"):
            return 200, {"response": "hello"}, "{}"
        if url.endswith("/api/command") and payload == {"command": "/help"}:
            return 200, {"response": "**Commands**\n- /help"}, "{}"
        if url.endswith("/api/command") and payload == {"command": "/stuck"}:
            return 200, {"action": {"next_action": "one step"}}, "{}"
        if url.endswith("/api/eval/run"):
            return 200, {"score": {"rate": 1.0}}, "{}"
        raise AssertionError(f"unexpected call: {url} {method} {payload}")

    monkeypatch.setattr(scorecard, "_request_json", fake_request_json)
    checks, rate = scorecard.run_scorecard("http://localhost:5001")

    assert len(checks) == 5
    assert all(c.passed for c in checks)
    assert rate == 1.0


def test_run_scorecard_fails_when_smoke_below_baseline(monkeypatch):
    def fake_request_json(url, method="GET", payload=None):
        if url.endswith("/api/brief"):
            return 200, {"next_action": "Do thing"}, "{}"
        if url.endswith("/api/chat"):
            return 200, {"response": "hello"}, "{}"
        if url.endswith("/api/command") and payload == {"command": "/help"}:
            return 200, {"response": "**Commands**\n- /help"}, "{}"
        if url.endswith("/api/command") and payload == {"command": "/stuck"}:
            return 200, {"action": {"next_action": "one step"}}, "{}"
        if url.endswith("/api/eval/run"):
            return 200, {"score": {"rate": 0.80}}, "{}"
        raise AssertionError(f"unexpected call: {url} {method} {payload}")

    monkeypatch.setattr(scorecard, "_request_json", fake_request_json)
    checks, rate = scorecard.run_scorecard("http://localhost:5001", smoke_baseline=0.95)

    assert len(checks) == 5
    assert any(not c.passed for c in checks)
    assert rate == 0.8
    failed = [c for c in checks if not c.passed]
    assert failed[0].name == "smoke_eval_baseline"


def test_write_artifact_shape(tmp_path):
    checks = [
        scorecard.CheckResult(name="brief_available", passed=True, status=200),
        scorecard.CheckResult(name="chat_responds", passed=False, status=500, reason="status=500"),
    ]
    path = scorecard.write_artifact(
        checks,
        rate=0.5,
        base_url="http://localhost:5001",
        output_dir=tmp_path,
    )

    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["suite"] == "daily_flow"
    assert data["scores"]["daily_flow"]["passed"] == 1
    assert data["scores"]["daily_flow"]["total"] == 2
    assert data["scores"]["daily_flow"]["rate"] == 0.5
