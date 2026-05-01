"""Regression tests for /unified behavior in web-shim mode."""

from flask import Flask

from src.api.streaming_routes import streaming_bp


class SupervisorWithoutUnified:
    pass


def test_unified_returns_501_when_supervisor_lacks_handler():
    app = Flask(__name__)
    app.secret_key = "test"
    app.supervisor = SupervisorWithoutUnified()
    app.register_blueprint(streaming_bp)

    client = app.test_client()
    response = client.post("/unified", json={"message": "hello"})

    assert response.status_code == 501
    assert response.get_json() == {
        "ok": False,
        "error": "Unified request not yet implemented",
    }
