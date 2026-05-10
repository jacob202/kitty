import scripts.eval_loop as eval_loop


def test_append_log_matches_four_column_iteration_table(tmp_path, monkeypatch):
    log_path = tmp_path / "iteration_log.md"
    monkeypatch.setattr(eval_loop, "ITERATION_LOG", log_path)

    eval_loop.append_log(1, "100.00%", "PASS", change="verification run")

    content = log_path.read_text()
    assert "| Attempt | Change | Eval Score | Status |" in content
    assert "| 1 | verification run | 100.00% | PASS |" in content


def test_flask_env_offline_clears_remote_provider_keys(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    env = eval_loop._flask_env(offline=True)

    assert env["OPENROUTER_API_KEY"] == ""
    assert env["ANTHROPIC_API_KEY"] == ""


def test_run_loop_writes_daily_summary_on_pytest_failure(monkeypatch):
    calls = {"summary": 0}

    monkeypatch.setattr(eval_loop, "run_pytest", lambda **kwargs: (False, ""))
    monkeypatch.setattr(eval_loop, "save_snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(eval_loop, "append_log", lambda *args, **kwargs: None)

    def _summary():
        calls["summary"] += 1
        return None

    monkeypatch.setattr(eval_loop, "_write_daily_summary", _summary)

    rc = eval_loop.run_loop(1)
    assert rc == 1
    assert calls["summary"] == 1


def test_run_loop_fails_when_browser_flow_fails(monkeypatch):
    calls = {"summary": 0}

    class _DummyProc:
        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    monkeypatch.setattr(eval_loop, "run_pytest", lambda **kwargs: (True, ""))
    monkeypatch.setattr(eval_loop, "start_flask", lambda **kwargs: _DummyProc())
    monkeypatch.setattr(
        eval_loop,
        "call_eval_route",
        lambda: {"ok": True, "score": {"rate": 1.0, "passed": 5, "total": 5}},
    )
    monkeypatch.setattr(eval_loop, "save_snapshot", lambda *args, **kwargs: None)
    monkeypatch.setattr(eval_loop, "append_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(eval_loop, "check_regression", lambda *args, **kwargs: {"is_regression": False, "reason": None})
    monkeypatch.setattr(eval_loop, "run_browser_flow_smoke", lambda: (False, 0.5, None))

    def _summary():
        calls["summary"] += 1
        return None

    monkeypatch.setattr(eval_loop, "_write_daily_summary", _summary)

    rc = eval_loop.run_loop(1, browser_flow=True)
    assert rc == 1
    assert calls["summary"] == 1


def test_suppress_offline_noise_removes_only_known_warning():
    raw = (
        "line one\n"
        "No LLM API key configured for web chat. Set OPENROUTER_API_KEY in .env and restart.\n"
        "line two\n"
    )
    cleaned = eval_loop._suppress_offline_noise(raw)
    assert "No LLM API key configured for web chat." not in cleaned
    assert "line one" in cleaned
    assert "line two" in cleaned
