"""No-spend readiness checks for hosted Image Lab providers."""

from __future__ import annotations

import httpx

from gateway import image_runner


class _Response:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_airforce_unavailable_when_free_account_has_no_balance(monkeypatch):
    monkeypatch.setenv("KITTY_IMAGE_AIRFORCE_ENABLED", "1")
    monkeypatch.setenv("AIRFORCE_API_KEY", "test-airforce-key")
    monkeypatch.setenv("AIRFORCE_MODEL", "grok-imagine-image-2.0")
    monkeypatch.setenv("KITTY_IMAGE_PROVIDER_HEALTH_TTL_SECONDS", "0")

    def fake_post(url, **kwargs):
        assert url == "https://api.airforce/mcp"
        return _Response(
            200,
            {
                "result": {
                    "isError": False,
                    "structuredContent": {
                        "balance_cents": 0.0,
                        "balance_usd": 0.0,
                        "plan": "free",
                    },
                }
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    available, reason = image_runner.airforce_images_available()

    assert available is False
    assert "balance" in reason.lower()


def test_airforce_available_with_positive_balance(monkeypatch):
    monkeypatch.setenv("KITTY_IMAGE_AIRFORCE_ENABLED", "1")
    monkeypatch.setenv("AIRFORCE_API_KEY", "test-airforce-key")
    monkeypatch.setenv("KITTY_IMAGE_PROVIDER_HEALTH_TTL_SECONDS", "0")

    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: _Response(
            200,
            {
                "result": {
                    "isError": False,
                    "structuredContent": {
                        "balance_cents": 250.0,
                        "balance_usd": 2.5,
                        "plan": "free",
                    },
                }
            },
        ),
    )
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: _Response(
            200,
            {"data": [{"id": "grok-imagine-image-2.0", "status": "operational"}]},
        ),
    )

    assert image_runner.airforce_images_available() == (True, "")


def test_airforce_unavailable_when_configured_model_is_in_outage(monkeypatch):
    monkeypatch.setenv("KITTY_IMAGE_AIRFORCE_ENABLED", "1")
    monkeypatch.setenv("AIRFORCE_API_KEY", "test-airforce-key")
    monkeypatch.setenv("AIRFORCE_MODEL", "grok-imagine-image-2.0")
    monkeypatch.setenv("KITTY_IMAGE_PROVIDER_HEALTH_TTL_SECONDS", "0")
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: _Response(
            200,
            {
                "result": {
                    "isError": False,
                    "structuredContent": {
                        "balance_cents": 250.0,
                        "balance_usd": 2.5,
                        "plan": "free",
                    },
                }
            },
        ),
    )
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: _Response(
            200,
            {"data": [{"id": "grok-imagine-image-2.0", "status": "major_outage"}]},
        ),
    )

    available, reason = image_runner.airforce_images_available()

    assert available is False
    assert "major_outage" in reason


def test_fal_unavailable_when_key_is_rejected(monkeypatch):
    monkeypatch.setenv("KITTY_IMAGE_FAL_ENABLED", "1")
    monkeypatch.setenv("FAL_KEY", "fal-key-id:fal-key-secret")
    monkeypatch.setenv("FAL_MODEL", "fal-ai/flux-pulid")
    monkeypatch.setenv("KITTY_IMAGE_PROVIDER_HEALTH_TTL_SECONDS", "0")
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: _Response(401, {}))

    available, reason = image_runner.fal_images_available()

    assert available is False
    assert "key" in reason.lower()
    assert "rejected" in reason.lower() or "unauthorized" in reason.lower()


def test_fal_available_when_key_can_list_active_model(monkeypatch):
    monkeypatch.setenv("KITTY_IMAGE_FAL_ENABLED", "1")
    monkeypatch.setenv("FAL_KEY", "fal-key-id:fal-key-secret")
    monkeypatch.setenv("FAL_MODEL", "fal-ai/flux-pulid")
    monkeypatch.setenv("KITTY_IMAGE_PROVIDER_HEALTH_TTL_SECONDS", "0")
    monkeypatch.setattr(
        httpx,
        "get",
        lambda *args, **kwargs: _Response(
            200,
            {
                "models": [
                    {
                        "endpoint_id": "fal-ai/flux-pulid",
                        "metadata": {"status": "active"},
                    }
                ]
            },
        ),
    )

    assert image_runner.fal_images_available() == (True, "")
