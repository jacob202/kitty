from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from gateway import llm_client
from gateway.openwebui_routing_guards import (
    OpenWebUIRoutingMiddleware,
    normalize_direct_openrouter_models,
)


def _echo_app() -> TestClient:
    app = FastAPI()
    app.add_middleware(OpenWebUIRoutingMiddleware)

    @app.post("/v1/chat/completions")
    async def echo(request: Request):
        return await request.json()

    return TestClient(app)


def test_auto_image_request_routes_to_vision():
    response = _echo_app().post(
        "/v1/chat/completions",
        json={
            "model": "kitty-auto",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is in this?"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64,AA=="},
                        },
                    ],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["model"] == "kitty-vision"


def test_auto_preserves_domain_only_deep_classification(monkeypatch):
    from gateway import openwebui_routing_guards as guards

    monkeypatch.setattr(guards, "classify_domain", lambda _text: "health")

    def classify(_text, *, domain=None):
        if domain == "health":
            return SimpleNamespace(tier="deep", trigger="domain")
        return SimpleNamespace(tier="standard", trigger="default")

    monkeypatch.setattr(guards, "classify_complexity", classify)
    response = _echo_app().post(
        "/v1/chat/completions",
        json={
            "model": "kitty-auto",
            "messages": [{"role": "user", "content": "I have a fever?"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["model"] == "kitty-sonnet"


def test_explicit_model_is_not_rewritten(monkeypatch):
    from gateway import openwebui_routing_guards as guards

    monkeypatch.setattr(guards, "classify_domain", lambda _text: "health")
    monkeypatch.setattr(
        guards,
        "classify_complexity",
        lambda _text, **_kwargs: SimpleNamespace(tier="deep", trigger="domain"),
    )
    response = _echo_app().post(
        "/v1/chat/completions",
        json={
            "model": "kitty-fast",
            "messages": [{"role": "user", "content": "I have a fever?"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["model"] == "kitty-fast"


def test_direct_openrouter_models_drop_litellm_prefix(monkeypatch):
    mapping = {
        "kitty-think": "openrouter/qwen/qwen3-235b-a22b-thinking-2507",
        "kitty-vision": "openrouter/mistralai/mistral-small-3.2-24b-instruct",
    }
    monkeypatch.setattr(llm_client, "_LITELLM_TO_OPENROUTER", mapping)
    original = llm_client.PROVIDERS["openrouter"]
    monkeypatch.setitem(llm_client.PROVIDERS, "openrouter", original)

    normalize_direct_openrouter_models()

    assert mapping == {
        "kitty-think": "qwen/qwen3-235b-a22b-thinking-2507",
        "kitty-vision": "mistralai/mistral-small-3.2-24b-instruct",
    }
    resolver = llm_client.PROVIDERS["openrouter"].model_resolver
    assert resolver is not None
    assert resolver("kitty-think") == "qwen/qwen3-235b-a22b-thinking-2507"
