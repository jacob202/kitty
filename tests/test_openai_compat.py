"""Contract tests for third-party OpenAI-compatible Kitty clients."""

from fastapi.testclient import TestClient

from gateway.app import app


def test_models_lists_stable_kitty_virtual_model():
    response = TestClient(app).get("/v1/models")

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "data": [
            {
                "id": "kitty-default",
                "object": "model",
                "created": 0,
                "owned_by": "kitty",
                "root": "kitty-default",
                "parent": None,
                "permission": [],
            }
        ],
    }


def test_model_retrieval_matches_list_entry():
    client = TestClient(app)

    listed = client.get("/v1/models").json()["data"][0]
    retrieved = client.get("/v1/models/kitty-default")

    assert retrieved.status_code == 200
    assert retrieved.json() == listed


def test_unknown_model_fails_loudly():
    response = TestClient(app).get("/v1/models/not-a-kitty-model")

    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown model: not-a-kitty-model"}
