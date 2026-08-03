"""Contract tests for third-party OpenAI-compatible Kitty clients."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from gateway.app import app
from gateway.routes import openai_compat


def _ids() -> list[str]:
    return [entry["id"] for entry in openai_compat.list_models()["data"]]


def test_automatic_routing_lists_the_full_truthful_menu():
    with patch("gateway.provider_prefs.active_provider", return_value=None):
        assert _ids() == [
            "kitty-auto",
            "kitty-fast",
            "kitty-think",
            "kitty-code",
            "kitty-vision",
        ]


def test_openrouter_lists_the_full_menu_because_it_maps_virtual_routes():
    with patch("gateway.provider_prefs.active_provider", return_value="openrouter"):
        assert _ids() == [
            "kitty-auto",
            "kitty-fast",
            "kitty-think",
            "kitty-code",
            "kitty-vision",
        ]


def test_exact_provider_hides_model_choices_it_cannot_guarantee():
    with patch("gateway.provider_prefs.active_provider", return_value="local"):
        menu = openai_compat.list_models()["data"]

    assert [entry["id"] for entry in menu] == ["kitty-auto"]
    assert menu[0]["name"] == "Kitty — Local"
    assert "cannot guarantee" in menu[0]["description"]


def test_hidden_model_ids_remain_retrievable_for_saved_chats():
    with patch("gateway.provider_prefs.active_provider", return_value="gemini"):
        assert "kitty-vision" not in _ids()
        assert openai_compat.retrieve_model("kitty-vision")["id"] == "kitty-vision"


def test_model_retrieval_matches_catalogue_entry():
    with patch("gateway.provider_prefs.active_provider", return_value=None):
        client = TestClient(app)
        retrieved = client.get("/v1/models/kitty-auto")

    assert retrieved.status_code == 200
    assert retrieved.json()["id"] == "kitty-auto"
    assert retrieved.json()["name"] == "Kitty Auto"


def test_unknown_model_fails_loudly():
    response = TestClient(app).get("/v1/models/not-a-kitty-model")

    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown model: not-a-kitty-model"}
