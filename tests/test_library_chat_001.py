"""LIBRARY-CHAT-001: Library → Chat image attachment bridge tests.

Covers the backend half of the pilot acceptance:
  1. A ready PNG/JPEG/WebP <= 5 MiB resolves into a chat-ready attachment.
  2. Unsupported type or size over 5 MiB is rejected before dispatch with
     plain-language copy and no internal paths/ids/status in the message.
  3. The chat-completions route injects resolved image parts into the outgoing
     user message when attachment_ids are supplied.
"""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway import artifact_store
from gateway import db as kitty_db
from gateway.routes import chats as chats_route
from gateway.routes import completions as completions_route


@pytest.fixture
def chat_client(monkeypatch, tmp_path):
    db_file = tmp_path / "kitty" / "kitty.db"
    monkeypatch.setattr(artifact_store, "ARTIFACTS_DB_FILE", db_file)
    artifact_store.init_db()

    app = FastAPI()
    app.include_router(chats_route.router)
    app.include_router(completions_route.router)
    return TestClient(app)


def _register_image(tmp_path, *, name="camera-reference.png", media_type="image/png", size=2048):
    path = tmp_path / name
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * size)
    return artifact_store.register_file(
        path,
        kind="capture",
        media_type=media_type,
        project_id=1,
        created_by="test",
    )


class TestUseInChat:
    def test_ready_png_resolves_to_chat_attachment(self, chat_client, tmp_path):
        artifact = _register_image(tmp_path)
        r = chat_client.post("/chats/use-in-chat", json={"artifact_id": artifact["id"]})
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == artifact["id"]
        assert body["display_name"] == "camera-reference.png"
        assert body["media_type"] == "image/png"
        assert body["size"] == artifact["size_bytes"]
        assert "data_url" not in body

    def test_ready_jpeg_and_webp_are_supported(self, chat_client, tmp_path):
        for name, mime in (("a.jpg", "image/jpeg"), ("a.webp", "image/webp")):
            artifact = _register_image(tmp_path, name=name, media_type=mime)
            r = chat_client.post("/chats/use-in-chat", json={"artifact_id": artifact["id"]})
            assert r.status_code == 200, r.text
            assert r.json()["media_type"] == mime

    def test_non_image_is_rejected_with_plain_copy(self, chat_client, tmp_path):
        path = tmp_path / "notes.pdf"
        path.write_text("hello")
        artifact = artifact_store.register_file(path, kind="document", media_type="application/pdf", project_id=1, created_by="test")
        r = chat_client.post("/chats/use-in-chat", json={"artifact_id": artifact["id"]})
        assert r.status_code == 415
        assert "Only images" in r.json()["detail"]
        assert artifact["id"] not in r.json()["detail"]

    def test_unsupported_image_type_is_rejected_with_plain_copy(self, chat_client, tmp_path):
        artifact = _register_image(tmp_path, name="anim.gif", media_type="image/gif")
        r = chat_client.post("/chats/use-in-chat", json={"artifact_id": artifact["id"]})
        assert r.status_code == 415
        assert "PNG, JPEG, or WebP" in r.json()["detail"]

    def test_over_5mb_image_is_rejected_before_dispatch(self, chat_client, tmp_path):
        artifact = _register_image(tmp_path, name="huge.png", media_type="image/png", size=5 * 1024 * 1024 + 1)
        r = chat_client.post("/chats/use-in-chat", json={"artifact_id": artifact["id"]})
        assert r.status_code == 413
        assert "5 MB" in r.json()["detail"]

    def test_file_that_grows_over_limit_after_registration_is_rejected(self, chat_client, tmp_path):
        artifact = _register_image(tmp_path, size=1024)
        path = Path(artifact["storage_uri"])
        path.write_bytes(b"0" * (5 * 1024 * 1024 + 1))

        r = chat_client.post("/chats/use-in-chat", json={"artifact_id": artifact["id"]})

        assert r.status_code == 413
        assert "5 MB" in r.json()["detail"]

    def test_not_ready_artifact_is_rejected_with_plain_copy(self, chat_client, tmp_path):
        artifact = _register_image(tmp_path)
        with kitty_db.connect(artifact_store.ARTIFACTS_DB_FILE) as conn:
            conn.execute("UPDATE artifacts SET state = ? WHERE id = ?", ("pending", artifact["id"]))
            conn.commit()
        r = chat_client.post("/chats/use-in-chat", json={"artifact_id": artifact["id"]})
        assert r.status_code == 409
        assert "not ready" in r.json()["detail"]

    def test_unknown_artifact_is_404_with_plain_copy(self, chat_client):
        r = chat_client.post("/chats/use-in-chat", json={"artifact_id": "artifact_missing"})
        assert r.status_code == 404
        assert "no longer exists" in r.json()["detail"]

    def test_missing_artifact_id_is_400(self, chat_client):
        r = chat_client.post("/chats/use-in-chat", json={})
        assert r.status_code == 400
        assert "artifact_id" in r.json()["detail"]


class TestCompletionInjection:
    def test_auto_with_pilot_image_selects_vision_and_injects_one_image_part(
        self, chat_client, tmp_path, monkeypatch
    ):
        artifact = _register_image(tmp_path)
        # Avoid the network: the injected payload is what we assert on.
        captured: dict = {}

        async def fake_stream(payload):
            captured["payload"] = payload
            yield b"data: [DONE]\n"

        monkeypatch.setattr(completions_route, "iter_chat_completions_stream", fake_stream)

        r = chat_client.post(
            "/api/chat/completions",
            json={
                "model": "kitty-auto",
                "stream": True,
                "attachment_ids": [artifact["id"]],
                "image_attachment_ids": [artifact["id"]],
                "messages": [{"role": "user", "content": "what do you see?"}],
            },
        )
        assert r.status_code == 200
        assert captured["payload"]["model"] == "kitty-vision"
        messages = captured["payload"]["messages"]
        user = [m for m in messages if m["role"] == "user"][-1]
        parts = user["content"]
        assert isinstance(parts, list)
        assert len([
            part
            for part in parts
            if part.get("type") == "image_url"
            and part["image_url"]["url"].startswith("data:image/png;base64,")
        ]) == 1
        assert {
            "type": "text",
            "text": "what do you see?",
        } in parts
        assert "image_attachment_ids" not in captured["payload"]

    def test_missing_pilot_image_finalizes_failed_turn_and_never_dispatches(
        self, chat_client, monkeypatch
    ):
        called = []
        finished = []
        errors = []

        async def fake_stream(payload):
            called.append(payload)
            yield b"data: [DONE]\n"

        handle = completions_route.chat_lifecycle.TurnHandle(
            "chat-1", "turn-1", "attempt-1", 1
        )

        def fake_finish(actual_handle, **kwargs):
            finished.append((actual_handle, kwargs))

        monkeypatch.setattr(completions_route, "iter_chat_completions_stream", fake_stream)
        monkeypatch.setattr(completions_route.chat_lifecycle, "start_turn", lambda **_: handle)
        monkeypatch.setattr(completions_route.chat_lifecycle, "finish_turn", fake_finish)
        monkeypatch.setattr(completions_route.chats_store, "get_chat", lambda _: {"id": "chat-1"})
        monkeypatch.setattr("gateway.buddy.on_request_error", lambda: errors.append(True))

        r = chat_client.post(
            "/api/chat/completions",
            json={
                "model": "kitty-auto",
                "stream": True,
                "conversation_id": "chat-1",
                "attachment_ids": ["artifact_stale"],
                "image_attachment_ids": ["artifact_stale"],
                "messages": [{"role": "user", "content": "what do you see?"}],
            },
        )
        assert r.status_code == 404
        assert called == []
        assert len(finished) == 1
        assert finished[0][0] == handle
        assert finished[0][1]["status"] == "failed"
        assert "404" in finished[0][1]["error"]
        assert r.json()["detail"]["kind"] == "attachment"
        assert "Remove it" in r.json()["detail"]["message"]
        assert errors

    def test_generic_pdf_attachment_reaches_upstream_without_image_resolution(
        self, chat_client, tmp_path, monkeypatch
    ):
        path = tmp_path / "notes.pdf"
        path.write_bytes(b"%PDF-1.4\nnotes")
        artifact = artifact_store.register_file(
            path,
            kind="document",
            media_type="application/pdf",
            project_id=1,
            created_by="test",
        )
        captured = []

        async def fake_stream(payload):
            captured.append(payload)
            yield b"data: [DONE]\n"

        monkeypatch.setattr(completions_route, "iter_chat_completions_stream", fake_stream)
        r = chat_client.post(
            "/api/chat/completions",
            json={
                "model": "kitty-default",
                "stream": True,
                "attachment_ids": [artifact["id"]],
                "messages": [{"role": "user", "content": "summarize this"}],
            },
        )
        assert r.status_code == 200
        assert len(captured) == 1
        assert captured[0]["attachment_ids"] == [artifact["id"]]
        assert captured[0]["messages"][-1]["content"] == "summarize this"

    def test_two_pilot_images_are_rejected_before_upstream_dispatch(
        self, chat_client, monkeypatch
    ):
        called = []

        async def fake_stream(payload):
            called.append(payload)
            yield b"data: [DONE]\n"

        monkeypatch.setattr(completions_route, "iter_chat_completions_stream", fake_stream)
        r = chat_client.post(
            "/api/chat/completions",
            json={
                "model": "kitty-auto",
                "stream": True,
                "attachment_ids": ["image-a", "image-b"],
                "image_attachment_ids": ["image-a", "image-b"],
                "messages": [{"role": "user", "content": "compare these"}],
            },
        )
        assert r.status_code == 400
        assert called == []

    def test_bad_attachment_id_fails_before_dispatch(self, chat_client, monkeypatch):
        called = []

        async def fake_stream(payload):
            called.append(payload)
            yield b"data: [DONE]\n"

        monkeypatch.setattr(completions_route, "iter_chat_completions_stream", fake_stream)

        r = chat_client.post(
            "/api/chat/completions",
            json={
                "model": "kitty-vision",
                "stream": True,
                "attachment_ids": ["artifact_does_not_exist"],
                "image_attachment_ids": ["artifact_does_not_exist"],
                "messages": [{"role": "user", "content": "what do you see?"}],
            },
        )
        assert r.status_code == 404
        assert called == []
        assert r.json()["detail"]["kind"] == "attachment"
        assert "Remove it" in r.json()["detail"]["message"]
