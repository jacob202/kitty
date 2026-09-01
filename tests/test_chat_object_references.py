from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from gateway import chat_lifecycle
from gateway.context_assembler import ContextBundle
from gateway.routes import completions as completions_route


def test_durable_chat_object_prompt_lists_only_scoped_real_ids(monkeypatch):
    monkeypatch.setattr(
        completions_route.action_queue,
        "list_actions",
        lambda limit=50: [
            {
                "id": 42,
                "title": "Schedule dentist",
                "status": "proposed",
                "kind": "calendar.event.create",
                "risk_tier": "T2",
                "source_kind": "chat",
                "source_id": "message-7",
                "scope_type": "global",
                "scope_id": "",
            },
            {
                "id": 99,
                "title": "Other project",
                "status": "proposed",
                "kind": "todo.create",
                "risk_tier": "T0",
                "source_kind": "manual",
                "source_id": None,
                "scope_type": "project",
                "scope_id": "other",
            },
        ],
    )
    monkeypatch.setattr(
        completions_route.artifact_store,
        "list_artifacts",
        lambda **kwargs: [
            {
                "id": "artifact_report",
                "display_name": "report.md",
                "state": "ready",
                "media_type": "text/markdown",
            }
        ],
    )

    block = completions_route._durable_chat_object_system(
        conversation_id="chat-1",
        user_message_id="message-7",
        project_id=7,
        project_name="kitty",
    )

    assert "kitty-action" in block
    assert '"action_id":42' in block
    assert "Schedule dentist" in block
    assert "99" not in block
    assert "kitty-artifact" in block
    assert '"artifact_id":"artifact_report"' in block


def test_streaming_chat_wires_scoped_durable_ids_into_model_visible_protocol(monkeypatch):
    captured = {}

    async def fake_stream(payload):
        captured["system"] = payload["messages"][0]["content"]
        if '"artifact_id":"artifact_report"' in captured["system"]:
            yield b'data: {"choices":[{"delta":{"content":"Here is the report.\\n\\n```kitty-artifact\\n{\\"artifact_id\\":\\"artifact_report\\"}\\n```"}}]}\n\n'
        yield b"data: [DONE]\n\n"

    monkeypatch.setattr(
        completions_route.action_queue,
        "list_actions",
        lambda limit=50: [],
    )
    monkeypatch.setattr(
        completions_route.artifact_store,
        "list_artifacts",
        lambda **kwargs: [
            {
                "id": "artifact_report",
                "display_name": "report.md",
                "state": "ready",
                "media_type": "text/markdown",
            }
        ],
    )
    bundle = ContextBundle(system="SYS", injected_memory_items=[])
    with patch("gateway.routes.completions.classify_domain", return_value="soul"), patch(
        "gateway.routes.completions.route_model", return_value="kitty-default"
    ), patch(
        "gateway.context_assembler.assemble_context",
        new=AsyncMock(return_value=bundle),
    ), patch(
        "gateway.routes.completions.iter_chat_completions_stream",
        new=fake_stream,
    ), patch(
        "gateway.routes.completions.chat_lifecycle.start_turn",
        return_value=chat_lifecycle.TurnHandle(
            conversation_id="chat-1", turn_id="turn-1", attempt_id="attempt-1", sequence=1
        ),
    ), patch(
        "gateway.routes.completions.chat_lifecycle.finish_turn"
    ), patch(
        "gateway.routes.completions.chats_store.get_chat",
        return_value={"id": "chat-1"},
    ):
        from gateway.app import app

        response = TestClient(app).post(
            "/v1/chat/completions",
            json={
                "conversation_id": "chat-1",
                "user_message_id": "message-7",
                "messages": [{"role": "user", "content": "show me the report"}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    assert '"artifact_id":"artifact_report"' in captured["system"]
    assert b"kitty-artifact" in response.content
    assert b"artifact_report" in response.content
