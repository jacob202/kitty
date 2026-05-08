import json

from scripts import browser_smoke_flows as smoke


def test_voice_transition_contract_detects_missing_tokens():
    ok, missing = smoke.check_voice_transition_contract("<html><body>no voice flow</body></html>")
    assert ok is False
    assert "toggleVoiceInput" in missing


def test_run_browser_smoke_passes_on_current_template():
    checks, rate = smoke.run_browser_smoke(smoke.make_smoke_app())
    assert len(checks) == 4
    assert all(c.passed for c in checks)
    assert rate == 1.0


def test_write_artifact_shape(tmp_path):
    checks = [
        smoke.FlowCheck(name="page_load", passed=True, status=200),
        smoke.FlowCheck(name="text_chat_roundtrip", passed=False, status=500, reason="status=500"),
    ]
    path = smoke.write_artifact(checks, rate=0.5, output_dir=tmp_path)

    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["suite"] == "browser_flow"
    assert data["scores"]["browser_flow"]["passed"] == 1
    assert data["scores"]["browser_flow"]["total"] == 2
    assert data["scores"]["browser_flow"]["rate"] == 0.5
