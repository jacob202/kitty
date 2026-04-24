from types import SimpleNamespace
from pathlib import Path
import importlib


def test_main_allows_werkzeug_for_local_launcher(monkeypatch):
    import web as web_module

    run_calls = []

    class DummySocketIO:
        def run(self, app, **kwargs):
            run_calls.append((app, kwargs))

    dummy_app = SimpleNamespace()
    monkeypatch.setattr(web_module, "create_app", lambda: (dummy_app, DummySocketIO()))
    monkeypatch.setattr(web_module, "_local_ip", lambda: "127.0.0.1")
    monkeypatch.delenv("KITTY_HOST", raising=False)
    monkeypatch.delenv("KITTY_PORT", raising=False)
    monkeypatch.delenv("FLASK_DEBUG", raising=False)

    web_module.main()

    assert run_calls == [
        (
            dummy_app,
            {
                "host": "0.0.0.0",
                "port": 5001,
                "debug": False,
                "use_reloader": False,
                "allow_unsafe_werkzeug": True,
            },
        )
    ]


def test_launcher_uses_bounded_network_probe_and_resolved_curl():
    launcher = Path(__file__).resolve().parents[1] / "kitty"
    content = launcher.read_text()

    assert "CURL=" in content
    assert '"$CURL" -sf' in content
    assert "s.settimeout(1)" in content
    assert "subprocess.Popen(" in content
    assert "start_new_session=True" in content


def test_webui_uses_polling_transport_for_local_werkzeug_server():
    template = Path(__file__).resolve().parents[1] / "src" / "templates" / "index.html"
    content = template.read_text()

    assert "transports: ['polling']" in content
    assert "transports: ['websocket', 'polling']" not in content


def test_fast_mode_skips_local_mlx_unless_enabled(monkeypatch):
    monkeypatch.delenv("KITTY_ENABLE_LOCAL_MLX", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    import src.api.web_orchestrator as web_orchestrator

    web_orchestrator = importlib.reload(web_orchestrator)
    calls = []

    def fail_mlx(*_args, **_kwargs):
        raise AssertionError("MLX should be opt-in")

    def fake_openrouter(_messages, _client_id, model, _reasoning):
        calls.append(model)
        return "remote response"

    monkeypatch.setattr(web_orchestrator, "_stream_mlx", fail_mlx)
    monkeypatch.setattr(web_orchestrator, "_stream_openrouter", fake_openrouter)

    result = web_orchestrator.stream_response("hello", "client-1", mode="fast")

    assert result == "remote response"
    assert calls == [web_orchestrator._FREE_ROUTER]


def test_web_openrouter_default_is_free_tier(monkeypatch):
    monkeypatch.delenv("KITTY_MODEL", raising=False)

    import src.api.web_llm as web_llm
    import src.api.web_orchestrator as web_orchestrator

    web_llm = importlib.reload(web_llm)
    web_orchestrator = importlib.reload(web_orchestrator)

    assert web_llm.DEFAULT_OPENROUTER_MODEL == "openrouter/free"
    assert web_orchestrator._OR_BAL == "openrouter/free"


def test_web_orchestrator_prompt_prioritizes_friction_reduction():
    import src.api.web_orchestrator as web_orchestrator

    assert "one concrete next action" in web_orchestrator._SYSTEM
    assert "reduce friction" in web_orchestrator._SYSTEM


def test_missing_lightrag_degrades_specialist_kb_instead_of_raising(monkeypatch):
    import src.core.specialist_framework as specialist_framework
    import src.memory.lightrag_store as lightrag_store

    specialist_framework._lightrag_stores.clear()

    class BrokenLightRAGStore:
        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError("No module named 'lightrag'")

    monkeypatch.setattr(lightrag_store, "LightRAGStore", BrokenLightRAGStore)

    store = specialist_framework._get_lightrag_for_domain("audio")

    assert store is None
    assert specialist_framework._lightrag_stores["audio"] is None


def test_model_target_free_overrides_configured_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("KITTY_MODEL", "paid/configured-model")

    import src.api.web_orchestrator as web_orchestrator

    web_orchestrator = importlib.reload(web_orchestrator)
    calls = []

    def fake_openrouter(_messages, _client_id, model, _reasoning):
        calls.append(model)
        return "free response"

    monkeypatch.setattr(web_orchestrator, "_stream_openrouter", fake_openrouter)

    result = web_orchestrator.stream_response(
        "hello",
        "client-1",
        mode="balanced",
        model_target="free",
    )

    assert result == "free response"
    assert calls == ["openrouter/free"]


def test_model_target_configured_uses_configured_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("KITTY_MODEL", "paid/configured-model")

    import src.api.web_orchestrator as web_orchestrator

    web_orchestrator = importlib.reload(web_orchestrator)
    calls = []

    def fake_openrouter(_messages, _client_id, model, _reasoning):
        calls.append(model)
        return "configured response"

    monkeypatch.setattr(web_orchestrator, "_stream_openrouter", fake_openrouter)

    result = web_orchestrator.stream_response(
        "hello",
        "client-1",
        mode="balanced",
        model_target="configured",
    )

    assert result == "configured response"
    assert calls == ["paid/configured-model"]


def test_webui_exposes_model_target_toggle():
    template = Path(__file__).resolve().parents[1] / "src" / "templates" / "index.html"
    content = template.read_text()

    assert "target-btn" in content
    assert "setModelTarget" in content
    assert "modelTarget" in content


def test_webui_clears_streaming_cursor_on_done():
    template = Path(__file__).resolve().parents[1] / "src" / "templates" / "index.html"
    content = template.read_text()
    finish_response_body = content.split("function finishResponse(errText) {", 1)[1].split(
        "// ── Send",
        1,
    )[0]

    assert "currentBubble.innerHTML = renderMarkdown(escHtml(currentText));" in finish_response_body
