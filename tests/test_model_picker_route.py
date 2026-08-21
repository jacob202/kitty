from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_model_picker_route_is_registered_and_returns_presets(monkeypatch) -> None:
    from gateway.routes import models as model_routes

    monkeypatch.setattr(
        model_routes,
        "build_model_picker",
        lambda: {
            "schema_version": 1,
            "discovery": {"state": "missing", "reason": "test", "checked_at": None},
            "presets": [
                {
                    "role": "code",
                    "label": "Code",
                    "route": "kitty-code",
                    "provider": "openrouter",
                    "model": "vendor/model",
                    "configured": True,
                    "catalogue": None,
                    "catalogue_state": "not_observed",
                    "alternatives": [],
                }
            ],
            "claims": {"role_tags": "heuristic", "alternatives": "cost-screened only"},
        },
    )
    app = FastAPI()
    app.include_router(model_routes.router)
    client = TestClient(app)
    response = client.get("/models/picker")
    assert response.status_code == 200
    body = response.json()
    assert body["presets"][0]["model"] == "vendor/model"
    assert body["discovery"]["state"] == "missing"


def test_gateway_registers_models_router() -> None:
    from gateway.routes import register

    source = register.__file__
    text = open(source, encoding="utf-8").read()
    assert "models," in text
