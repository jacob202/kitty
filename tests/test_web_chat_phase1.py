import io
from types import SimpleNamespace

from flask import Flask

from src.api.core_routes import core_bp
from src.api.dispatcher import dispatch
from src.core.domain_router import Domain, RoutingDecision
from src.core.specialist_framework import SpecialistResponse
from src.space_kitty import core_orchestrator as core_module


class _DummyJournal:
    def log(self, *_args, **_kwargs):
        pass


class _DummyHoncho:
    def get_approach_recommendation(self):
        return ""

    def analyze_conversation(self, *_args, **_kwargs):
        pass


class _DummyCorrectionMemory:
    def capture_context_snapshot(self, *_args, **_kwargs):
        pass

    def get_recent_snapshots(self, **_kwargs):
        return []


class _DummyContextManager:
    def __init__(self):
        self.journal = _DummyJournal()
        self.honcho = _DummyHoncho()
        self.correction_memory = _DummyCorrectionMemory()

    def build_unified_context(self, *_args, **_kwargs):
        return ""


class _DummyReasoningLayer:
    def __init__(self, emit_callback=None):
        self.emit_callback = emit_callback

    def reason(self, **_kwargs):
        return SimpleNamespace(id="reasoning-1", conclusion="")


class _DummySpecialists:
    specialists = {}

    def get_specialist(self, _name):
        return None


class _DummyCheckpoint:
    def save_mood(self, *_args, **_kwargs):
        pass

    def save_checkpoint(self, **_kwargs):
        pass

    def get_last_checkpoint(self, **_kwargs):
        return None


class _DummyPersonality:
    def get_system_context(self):
        return "You are Kitty."

    def detect_mood(self, *_args, **_kwargs):
        return "calm"


class _DummyRouter:
    def route(self, _query):
        return RoutingDecision(
            domain=Domain.GENERAL,
            confidence=0.9,
            specialist="Kitty",
            reasoning="default",
        )

    def get_routing_for_domain(self, domain):
        return RoutingDecision(
            domain=domain,
            confidence=0.9,
            specialist="Kitty",
            reasoning="mapped",
        )


class _DummySupervisor:
    def __init__(self):
        self.ran = []

    def run(self, inp):
        self.ran.append(inp)


def _response(text: str, specialist: str = "Kitty") -> SpecialistResponse:
    return SpecialistResponse(
        content=text,
        confidence=0.9,
        sources=[],
        safety_warnings=[],
        suggested_followups=[],
        diagnostics={"specialist": specialist},
    )


def test_core_orchestrator_process_handles_missing_council_enum(monkeypatch):
    monkeypatch.setattr(core_module, "ContextManager", _DummyContextManager)
    monkeypatch.setattr(core_module, "DomainRouter", _DummyRouter)
    monkeypatch.setattr(core_module, "SpecialistRegistry", _DummySpecialists)
    monkeypatch.setattr(core_module, "CheckpointManager", _DummyCheckpoint)
    monkeypatch.setattr(core_module, "KittyPersonality", _DummyPersonality)
    monkeypatch.setattr(core_module, "ReasoningLayer", _DummyReasoningLayer)
    monkeypatch.setattr(core_module, "VOICE_AVAILABLE", False)
    monkeypatch.setattr(
        core_module.CoreOrchestrator,
        "_general_response",
        lambda self, *_args, **_kwargs: _response("general fallback"),
    )

    orch = core_module.CoreOrchestrator(socketio=None)

    response = orch.process("hello")

    assert response.content == "general fallback"


def test_core_orchestrator_select_model_honors_web_preferences(monkeypatch):
    monkeypatch.setattr(core_module, "ContextManager", _DummyContextManager)
    monkeypatch.setattr(core_module, "DomainRouter", _DummyRouter)
    monkeypatch.setattr(core_module, "SpecialistRegistry", _DummySpecialists)
    monkeypatch.setattr(core_module, "CheckpointManager", _DummyCheckpoint)
    monkeypatch.setattr(core_module, "KittyPersonality", _DummyPersonality)
    monkeypatch.setattr(core_module, "ReasoningLayer", _DummyReasoningLayer)
    monkeypatch.setattr(core_module, "VOICE_AVAILABLE", False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("KITTY_MODEL", "configured/model")
    monkeypatch.setenv("KITTY_MAX_MODEL", "max/model")
    monkeypatch.setenv("KITTY_BALANCED_REASON", "reason/model")

    orch = core_module.CoreOrchestrator(socketio=None)

    assert orch._select_model("hello", mode="fast", model_target="free") == "openrouter/free"
    assert orch._select_model("hello", mode="balanced", model_target="configured") == "configured/model"
    assert orch._select_model("hello", mode="balanced", reasoning=True, model_target="configured") == "reason/model"
    assert orch._select_model("hello", mode="max", model_target="configured") == "max/model"
    assert orch._select_model("hello", mode="balanced", model_target="local") is None


def test_dispatch_uses_web_llm_fallback_when_orchestrator_fails():
    sup = _DummySupervisor()

    class BrokenOrchestrator:
        def process(self, *_args, **_kwargs):
            raise AttributeError("type object 'Domain' has no attribute 'COUNCIL'")

    calls = []

    def fallback_chat(message, domain=None, stream=False):
        calls.append((message, domain, stream))
        return _response("fallback response")

    response = dispatch(
        "hello",
        domain="chat",
        sup=sup,
        orch=BrokenOrchestrator(),
        fallback_chat=fallback_chat,
        fallback_stream=True,
    )

    assert response.content == "fallback response"
    assert calls == [("hello", "chat", True)]
    assert sup.ran == []


def test_dispatch_passes_web_preferences_to_orchestrator():
    class RecordingOrchestrator:
        def __init__(self):
            self.calls = []

        def process(self, *_args, **kwargs):
            self.calls.append(kwargs)
            return _response("orchestrated")

    orch = RecordingOrchestrator()

    response = dispatch(
        "hello",
        domain="audio",
        orch=orch,
        mode="balanced",
        reasoning=True,
        model_target="configured",
    )

    assert response.content == "orchestrated"
    assert orch.calls == [
        {
            "domain": "audio",
            "context": None,
            "mode": "balanced",
            "reasoning": True,
            "model_target": "configured",
        }
    ]


def test_api_chat_falls_back_when_orchestrator_raises():
    app = Flask(__name__)
    app.register_blueprint(core_bp)
    app.supervisor = _DummySupervisor()

    class BrokenOrchestrator:
        def process(self, *_args, **_kwargs):
            raise RuntimeError("boom")

    class DummyWebLLM:
        def chat(self, message, domain=None, stream=False):
            assert message == "hello"
            assert domain == "chat"
            assert stream is False
            return _response("web fallback", specialist="WebLLM")

    app.orchestrator = BrokenOrchestrator()
    app.web_llm = DummyWebLLM()

    client = app.test_client()
    response = client.post("/api/chat", json={"message": "hello", "domain": "chat"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["response"] == "web fallback"
    assert payload["specialist"] == "WebLLM"


def test_create_app_disables_core_voice_components(monkeypatch):
    import web as web_module

    captured = {}

    class DummyOrchestrator:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

        def get_resume_summary(self):
            return None

    monkeypatch.setattr("src.space_kitty.core_orchestrator.CoreOrchestrator", DummyOrchestrator)

    app, _ = web_module.create_app()

    assert isinstance(app.orchestrator, DummyOrchestrator)
    assert captured["enable_voice_components"] is False


def test_create_app_registers_transcribe_route(monkeypatch):
    import web as web_module

    class DummyOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

        def get_resume_summary(self):
            return None

    class DummyResult:
        text = "voice works"
        language = "en"
        duration_seconds = 2.0

    class DummyTranscriber:
        def transcribe_file(self, _path):
            return DummyResult()

    monkeypatch.setattr("src.space_kitty.core_orchestrator.CoreOrchestrator", DummyOrchestrator)
    monkeypatch.setattr("src.api.voice_routes.get_transcriber", lambda: DummyTranscriber())

    app, _ = web_module.create_app()
    client = app.test_client()

    response = client.post(
        "/api/transcribe",
        data={"audio": (io.BytesIO(b"audio"), "sample.webm", "audio/webm")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json()["text"] == "voice works"


def test_socket_send_message_emits_done(monkeypatch):
    import web as web_module

    class DummyOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

        def get_resume_summary(self):
            return None

    monkeypatch.setattr("src.space_kitty.core_orchestrator.CoreOrchestrator", DummyOrchestrator)
    monkeypatch.setattr("src.api.dispatcher.dispatch", lambda *args, **kwargs: None)

    app, socketio = web_module.create_app()
    client = socketio.test_client(app)

    client.emit("send_message", {"text": "/brief"})
    socketio.sleep(0.1)

    received = client.get_received()

    assert any(event["name"] == "done" for event in received), received


def test_socket_send_message_emits_dispatch_response(monkeypatch):
    import web as web_module

    class DummyOrchestrator:
        def __init__(self, *args, **kwargs):
            pass

        def get_resume_summary(self):
            return None

    monkeypatch.setattr("src.space_kitty.core_orchestrator.CoreOrchestrator", DummyOrchestrator)
    calls = []

    def fake_dispatch(*args, **kwargs):
        calls.append(kwargs)
        return _response("socket response", specialist="Alex")

    monkeypatch.setattr("src.api.dispatcher.dispatch", fake_dispatch)

    app, socketio = web_module.create_app()
    client = socketio.test_client(app)

    client.emit(
        "send_message",
        {
            "text": "hello",
            "mode": "balanced",
            "reasoning": True,
            "modelTarget": "configured",
        },
    )
    socketio.sleep(0.1)

    received = client.get_received()

    assert calls == [
        {
            "sup": app.supervisor,
            "orch": app.orchestrator,
            "fallback_chat": app.web_llm.chat,
            "fallback_stream": True,
            "mode": "balanced",
            "reasoning": True,
            "model_target": "configured",
        }
    ]
    assert any(
        event["name"] == "token" and event["args"][0]["text"] == "socket response"
        for event in received
    ), received
    assert any(event["name"] == "done" for event in received), received
