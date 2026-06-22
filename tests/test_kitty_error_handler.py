"""Tests for the FastAPI exception handler that translates ``KittyError`` to a
consistent JSON error shape.

The handler lives in ``gateway/app.py`` and is registered on the app. These
tests exercise it via ``TestClient`` with a small temporary route that raises
each ``KittyError`` subclass, and a direct unit test of the handler callable.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.errors import (
    AuthError,
    AuthForbidden,
    ConfigError,
    KittyError,
    ProviderError,
    ProviderTimeout,
    StorageConflict,
    StorageNotFound,
    StorageUnavailable,
    ValidationError,
)


def _client():
    return TestClient(app, raise_server_exceptions=False)


# Each pair: (path, error instance) — exercising the 9 subclasses + base.
_CASES = [
    ("/test/_kitty_base", KittyError("base boom", details={"k": "v"})),
    ("/test/_kitty_config", ConfigError("missing x")),
    ("/test/_kitty_validation", ValidationError("bad input")),
    ("/test/_kitty_auth", AuthError("no token")),
    ("/test/_kitty_forbidden", AuthForbidden("nope")),
    ("/test/_kitty_notfound", StorageNotFound("no record")),
    ("/test/_kitty_conflict", StorageConflict("dup")),
    ("/test/_kitty_unavailable", StorageUnavailable("locked")),
    ("/test/_kitty_provider", ProviderError("upstream 500")),
    ("/test/_kitty_timeout", ProviderTimeout("upstream 504")),
]


def _register_test_routes():
    router = APIRouter()

    for path, err in _CASES:
        def _make(_err):
            def handler():
                raise _err
            return handler

        router.add_api_route(path, _make(err), methods=["GET"])

    app.include_router(router)


_register_test_routes()


def test_handler_translates_each_subclass_to_its_status():
    client = _client()
    for path, err in _CASES:
        r = client.get(path)
        assert r.status_code == err.status_code, (path, err.status_code, r.status_code)
        body = r.json()
        assert body["error"] == err.code, (path, body, err.code)
        assert body["message"] == err.message


def test_handler_includes_details_only_when_present():
    client = _client()
    r = client.get("/test/_kitty_base")
    body = r.json()
    assert body["details"] == {"k": "v"}


def test_handler_omits_details_when_empty():
    client = _client()
    r = client.get("/test/_kitty_config")
    body = r.json()
    assert "details" not in body
    assert body == {"error": "config_error", "message": "missing x"}


def test_handler_does_not_swallow_unexpected_exceptions():
    """A bare ``RuntimeError`` must surface as a real 500, not a KittyError body."""
    router = APIRouter()

    def boom():
        raise RuntimeError("not a kitty error")

    router.add_api_route("/test/_unrelated", boom, methods=["GET"])
    app.include_router(router)

    client = _client()
    r = client.get("/test/_unrelated")
    assert r.status_code == 500
    if r.headers.get("content-type", "").startswith("application/json"):
        body = r.json()
        assert body.get("error") != "internal_error" or body.get("message") != "..."
