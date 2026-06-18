"""Unit and integration-style tests for backend/main.py — FastAPI app routes and helpers."""
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-main-tests")

import pytest


# ---------------------------------------------------------------------------
# Helper function tests (pure, no I/O)
# ---------------------------------------------------------------------------

class TestLastUserMessage:
    """_last_user_message() must return the most recent user-role message content."""

    def test_returns_content_of_single_user_message(self):
        from backend.main import Message, _last_user_message
        messages = [Message(role="user", content="hello")]
        assert _last_user_message(messages) == "hello"

    def test_returns_most_recent_user_message(self):
        from backend.main import Message, _last_user_message
        messages = [
            Message(role="user", content="first"),
            Message(role="assistant", content="reply"),
            Message(role="user", content="second"),
        ]
        assert _last_user_message(messages) == "second"

    def test_skips_assistant_messages(self):
        from backend.main import Message, _last_user_message
        messages = [
            Message(role="user", content="the one"),
            Message(role="assistant", content="should be ignored"),
        ]
        assert _last_user_message(messages) == "the one"

    def test_returns_empty_string_when_no_user_messages(self):
        from backend.main import Message, _last_user_message
        messages = [Message(role="assistant", content="only assistant")]
        assert _last_user_message(messages) == ""

    def test_returns_empty_string_for_empty_list(self):
        from backend.main import _last_user_message
        assert _last_user_message([]) == ""

    def test_iterates_in_reverse_order(self):
        """The last user message in the list must be returned, not the first."""
        from backend.main import Message, _last_user_message
        messages = [
            Message(role="user", content="early"),
            Message(role="user", content="middle"),
            Message(role="user", content="latest"),
        ]
        assert _last_user_message(messages) == "latest"


class TestOpenaiChunk:
    """_openai_chunk() must produce a valid SSE-formatted OpenAI streaming chunk."""

    def test_starts_with_data_prefix(self):
        from backend.main import _openai_chunk
        chunk = _openai_chunk("hello", "test-model")
        assert chunk.startswith("data: ")

    def test_ends_with_double_newline(self):
        from backend.main import _openai_chunk
        chunk = _openai_chunk("hello", "test-model")
        assert chunk.endswith("\n\n")

    def test_is_valid_json_after_data_prefix(self):
        from backend.main import _openai_chunk
        chunk = _openai_chunk("hello", "test-model")
        json_part = chunk[len("data: "):].strip()
        parsed = json.loads(json_part)
        assert isinstance(parsed, dict)

    def test_object_is_chat_completion_chunk(self):
        from backend.main import _openai_chunk
        chunk = _openai_chunk("hi", "test-model")
        data = json.loads(chunk[len("data: "):].strip())
        assert data["object"] == "chat.completion.chunk"

    def test_model_field_matches(self):
        from backend.main import _openai_chunk
        chunk = _openai_chunk("hi", "my-model")
        data = json.loads(chunk[len("data: "):].strip())
        assert data["model"] == "my-model"

    def test_content_present_when_not_finish(self):
        from backend.main import _openai_chunk
        chunk = _openai_chunk("hello world", "m", finish=False)
        data = json.loads(chunk[len("data: "):].strip())
        assert data["choices"][0]["delta"]["content"] == "hello world"

    def test_finish_reason_none_when_not_finish(self):
        from backend.main import _openai_chunk
        chunk = _openai_chunk("text", "m", finish=False)
        data = json.loads(chunk[len("data: "):].strip())
        assert data["choices"][0]["finish_reason"] is None

    def test_finish_true_has_stop_finish_reason(self):
        from backend.main import _openai_chunk
        chunk = _openai_chunk("", "m", finish=True)
        data = json.loads(chunk[len("data: "):].strip())
        assert data["choices"][0]["finish_reason"] == "stop"

    def test_finish_true_has_empty_delta(self):
        from backend.main import _openai_chunk
        chunk = _openai_chunk("", "m", finish=True)
        data = json.loads(chunk[len("data: "):].strip())
        assert data["choices"][0]["delta"] == {}

    def test_id_starts_with_chatcmpl(self):
        from backend.main import _openai_chunk
        chunk = _openai_chunk("hi", "m")
        data = json.loads(chunk[len("data: "):].strip())
        assert data["id"].startswith("chatcmpl-")

    def test_has_created_timestamp(self):
        from backend.main import _openai_chunk
        chunk = _openai_chunk("hi", "m")
        data = json.loads(chunk[len("data: "):].strip())
        assert isinstance(data["created"], int)
        assert data["created"] > 0


class TestOpenaiResponse:
    """_openai_response() must produce a valid non-streaming OpenAI completion dict."""

    def test_object_is_chat_completion(self):
        from backend.main import _openai_response
        resp = _openai_response("hello", "test-model")
        assert resp["object"] == "chat.completion"

    def test_model_field_matches(self):
        from backend.main import _openai_response
        resp = _openai_response("hello", "my-model")
        assert resp["model"] == "my-model"

    def test_content_is_in_choices(self):
        from backend.main import _openai_response
        resp = _openai_response("response text", "m")
        assert resp["choices"][0]["message"]["content"] == "response text"

    def test_role_is_assistant(self):
        from backend.main import _openai_response
        resp = _openai_response("hi", "m")
        assert resp["choices"][0]["message"]["role"] == "assistant"

    def test_finish_reason_is_stop(self):
        from backend.main import _openai_response
        resp = _openai_response("hi", "m")
        assert resp["choices"][0]["finish_reason"] == "stop"

    def test_id_starts_with_chatcmpl(self):
        from backend.main import _openai_response
        resp = _openai_response("hi", "m")
        assert resp["id"].startswith("chatcmpl-")

    def test_usage_fields_present(self):
        from backend.main import _openai_response
        resp = _openai_response("hi", "m")
        assert "usage" in resp
        assert "prompt_tokens" in resp["usage"]
        assert "completion_tokens" in resp["usage"]
        assert "total_tokens" in resp["usage"]

    def test_has_created_field(self):
        from backend.main import _openai_response
        resp = _openai_response("hi", "m")
        assert isinstance(resp["created"], int)
        assert resp["created"] > 0


# ---------------------------------------------------------------------------
# FastAPI route tests using TestClient
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def test_client():
    """Create a FastAPI TestClient with mocked Anthropic client."""
    with patch("backend.main.client") as mock_anthropic:
        mock_anthropic.messages = MagicMock()
        from fastapi.testclient import TestClient
        from backend.main import app
        yield TestClient(app)


class TestHealthRoute:
    """GET /health must return status ok."""

    def test_health_returns_200(self, test_client):
        resp = test_client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_status_ok(self, test_client):
        resp = test_client.get("/health")
        assert resp.json() == {"status": "ok"}


class TestModelsRoute:
    """GET /v1/models must return a list of available model IDs."""

    def test_models_returns_200(self, test_client):
        resp = test_client.get("/v1/models")
        assert resp.status_code == 200

    def test_models_has_object_field(self, test_client):
        resp = test_client.get("/v1/models")
        assert resp.json()["object"] == "list"

    def test_models_has_data_list(self, test_client):
        resp = test_client.get("/v1/models")
        assert isinstance(resp.json()["data"], list)

    def test_models_returns_three_models(self, test_client):
        resp = test_client.get("/v1/models")
        assert len(resp.json()["data"]) == 3

    def test_each_model_has_id_and_object(self, test_client):
        resp = test_client.get("/v1/models")
        for model in resp.json()["data"]:
            assert "id" in model
            assert model["object"] == "model"

    def test_model_ids_are_non_empty_strings(self, test_client):
        resp = test_client.get("/v1/models")
        for model in resp.json()["data"]:
            assert isinstance(model["id"], str)
            assert model["id"]


class TestChatCompletionsValidation:
    """POST /v1/chat/completions must validate the request body."""

    def test_empty_messages_returns_400(self, test_client):
        resp = test_client.post(
            "/v1/chat/completions",
            json={"messages": [], "stream": False},
        )
        assert resp.status_code == 400

    def test_no_user_message_returns_400(self, test_client):
        resp = test_client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "assistant", "content": "hi"}],
                "stream": False,
            },
        )
        assert resp.status_code == 400

    def test_missing_messages_field_returns_422(self, test_client):
        resp = test_client.post(
            "/v1/chat/completions",
            json={"stream": False},
        )
        assert resp.status_code == 422

    def test_error_detail_on_empty_messages(self, test_client):
        resp = test_client.post(
            "/v1/chat/completions",
            json={"messages": [], "stream": False},
        )
        assert resp.status_code == 400
        assert "messages" in resp.json()["detail"].lower()


class TestChatCompletionsNonStreaming:
    """POST /v1/chat/completions with stream=False must return a complete response dict."""

    def _make_mock_response(self, text="test response"):
        mock_content = MagicMock()
        mock_content.text = text
        mock_resp = MagicMock()
        mock_resp.content = [mock_content]
        return mock_resp

    def test_non_streaming_returns_200(self, test_client):
        mock_resp = self._make_mock_response("hello there")
        with patch("backend.main.client") as mock_client:
            mock_client.messages.create = AsyncMock(return_value=mock_resp)
            with patch("backend.main.get_user_profile", return_value={}), \
                 patch("backend.main.search_memories", return_value=[]), \
                 patch("backend.main.add_memory"):
                resp = test_client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": False,
                    },
                )
        assert resp.status_code == 200

    def test_non_streaming_response_has_choices(self, test_client):
        mock_resp = self._make_mock_response("reply content")
        with patch("backend.main.client") as mock_client:
            mock_client.messages.create = AsyncMock(return_value=mock_resp)
            with patch("backend.main.get_user_profile", return_value={}), \
                 patch("backend.main.search_memories", return_value=[]), \
                 patch("backend.main.add_memory"):
                resp = test_client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": "tell me something"}],
                        "stream": False,
                    },
                )
        data = resp.json()
        assert "choices" in data
        assert data["choices"][0]["message"]["content"] == "reply content"

    def test_non_streaming_add_memory_called(self, test_client):
        mock_resp = self._make_mock_response("answer")
        with patch("backend.main.client") as mock_client:
            mock_client.messages.create = AsyncMock(return_value=mock_resp)
            with patch("backend.main.get_user_profile", return_value={}), \
                 patch("backend.main.search_memories", return_value=[]), \
                 patch("backend.main.add_memory") as mock_add_mem:
                test_client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": "what is 2+2?"}],
                        "stream": False,
                    },
                )
        mock_add_mem.assert_called_once()

    def test_non_streaming_add_memory_failure_does_not_crash(self, test_client):
        """add_memory errors must be swallowed and not surface as 500s."""
        mock_resp = self._make_mock_response("answer")
        with patch("backend.main.client") as mock_client:
            mock_client.messages.create = AsyncMock(return_value=mock_resp)
            with patch("backend.main.get_user_profile", return_value={}), \
                 patch("backend.main.search_memories", return_value=[]), \
                 patch("backend.main.add_memory", side_effect=Exception("DB down")):
                resp = test_client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": "hello"}],
                        "stream": False,
                    },
                )
        assert resp.status_code == 200

    def test_max_tokens_override_respected(self, test_client):
        """When max_tokens is provided in request, it should be forwarded to Anthropic."""
        mock_resp = self._make_mock_response("ok")
        with patch("backend.main.client") as mock_client:
            mock_client.messages.create = AsyncMock(return_value=mock_resp)
            with patch("backend.main.get_user_profile", return_value={}), \
                 patch("backend.main.search_memories", return_value=[]), \
                 patch("backend.main.add_memory"):
                resp = test_client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": False,
                        "max_tokens": 512,
                    },
                )
        assert resp.status_code == 200
        # Verify create was called with max_tokens=512
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs.get("max_tokens") == 512


class TestProfileRoute:
    """GET /profile and PATCH /profile must read/write the user profile."""

    def test_get_profile_returns_200(self, test_client):
        with patch("backend.main.get_user_profile", return_value={"name": "Alice"}):
            resp = test_client.get("/profile")
        assert resp.status_code == 200

    def test_get_profile_returns_profile_data(self, test_client):
        with patch("backend.main.get_user_profile", return_value={"name": "Alice"}):
            resp = test_client.get("/profile")
        assert resp.json() == {"name": "Alice"}

    def test_patch_profile_calls_update(self, test_client):
        with patch("backend.main.update_user_profile") as mock_update, \
             patch("backend.main.get_user_profile", return_value={"name": "Bob"}):
            resp = test_client.patch("/profile", json={"name": "Bob"})
        assert resp.status_code == 200
        mock_update.assert_called_once_with({"name": "Bob"})

    def test_patch_profile_returns_updated_profile(self, test_client):
        updated = {"name": "Charlie", "city": "NYC"}
        with patch("backend.main.update_user_profile"), \
             patch("backend.main.get_user_profile", return_value=updated):
            resp = test_client.patch("/profile", json={"city": "NYC"})
        assert resp.json() == updated


class TestChatCompletionsStreaming:
    """POST /v1/chat/completions with stream=True must return SSE text/event-stream."""

    def test_streaming_returns_200(self, test_client):
        async def _fake_stream(request):
            yield "data: {}\n\n"
            yield "data: [DONE]\n\n"

        with patch("backend.main._stream_response", side_effect=_fake_stream):
            resp = test_client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True,
                },
            )
        assert resp.status_code == 200

    def test_streaming_content_type_is_event_stream(self, test_client):
        async def _fake_stream(request):
            yield "data: [DONE]\n\n"

        with patch("backend.main._stream_response", side_effect=_fake_stream):
            resp = test_client.post(
                "/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "hello"}],
                    "stream": True,
                },
            )
        assert "text/event-stream" in resp.headers.get("content-type", "")


class TestCorsConfiguration:
    """CORS middleware should restrict to localhost origins."""

    def test_localhost_origin_allowed(self, test_client):
        resp = test_client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        # TestClient does not do actual CORS enforcement, but we verify the
        # allow_origins constant contains the expected values.
        from backend.main import _LOCALHOST_ORIGINS
        assert "http://localhost:3000" in _LOCALHOST_ORIGINS

    def test_localhost_origins_list_is_non_empty(self):
        from backend.main import _LOCALHOST_ORIGINS
        assert len(_LOCALHOST_ORIGINS) > 0

    def test_all_origins_are_localhost_or_127(self):
        """Every CORS origin must be localhost or 127.0.0.1 (never a public domain)."""
        from backend.main import _LOCALHOST_ORIGINS
        for origin in _LOCALHOST_ORIGINS:
            assert "localhost" in origin or "127.0.0.1" in origin, (
                f"Non-local origin found in CORS config: {origin}"
            )