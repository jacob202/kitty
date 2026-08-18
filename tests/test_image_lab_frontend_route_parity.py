from __future__ import annotations

from fastapi import FastAPI

from gateway.paths import ROOT
from gateway.routes.register import register_routes


IMAGE_LAB = ROOT / "gateway" / "kitty-chat" / "src" / "components" / "ImageLab.tsx"


def _registered_methods() -> set[tuple[str, str]]:
    app = FastAPI()
    register_routes(app)
    methods: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        for method in getattr(route, "methods", set()) or set():
            if isinstance(path, str):
                methods.add((method, path))
    return methods


def test_image_lab_mutating_and_truth_routes_are_registered_with_matching_methods() -> None:
    registered = _registered_methods()
    required = {
        ("GET", "/image/status"),
        ("POST", "/studio/estimate"),
        ("POST", "/studio/sessions"),
        ("GET", "/studio/sessions/{session_id}"),
        ("POST", "/studio/sessions/{session_id}/anchor"),
        ("POST", "/studio/agent"),
        ("POST", "/studio/batches"),
        ("GET", "/studio/batches"),
        ("GET", "/studio/batches/{batch_id}"),
        ("POST", "/studio/batches/{batch_id}/cancel"),
    }
    missing = sorted(required - registered)
    assert not missing, f"Image Lab frontend contract has unregistered Gateway routes: {missing}"


def test_image_lab_frontend_still_uses_the_routes_guarded_above() -> None:
    source = IMAGE_LAB.read_text(encoding="utf-8")
    required_frontend_fragments = (
        "useImageStatus()",
        "fetch('/proxy/studio/estimate'",
        "fetch('/proxy/studio/sessions'",
        "fetch(`/proxy/studio/sessions/${encodeURIComponent(stored)}`",
        "fetch(`/proxy/studio/sessions/${encodeURIComponent(sessionId)}/anchor`",
        "fetch('/proxy/studio/agent'",
        "fetch('/proxy/studio/batches'",
        "fetch(`/proxy/studio/batches?session_id=${encodeURIComponent(stored)}`",
        "fetch(`/proxy/studio/batches/${batchId}`",
        "fetch(`/proxy/studio/batches/${batchId}/cancel`",
    )
    missing = [fragment for fragment in required_frontend_fragments if fragment not in source]
    assert not missing, f"Image Lab network controls drifted from the parity gate: {missing}"
