from __future__ import annotations

from gateway.paths import ROOT
from gateway.routes import extended, image_studio_jobs


IMAGE_LAB = ROOT / "gateway" / "kitty-chat" / "src" / "components" / "ImageLab.tsx"
REGISTER = ROOT / "gateway" / "routes" / "register.py"


def _route_methods(*routers) -> set[tuple[str, str]]:
    methods: set[tuple[str, str]] = set()
    for router in routers:
        for route in router.routes:
            path = getattr(route, "path", None)
            for method in getattr(route, "methods", set()) or set():
                if isinstance(path, str):
                    methods.add((method, path))
    return methods


def test_image_lab_owning_routers_are_mounted() -> None:
    source = REGISTER.read_text(encoding="utf-8")
    assert source.count("image_studio_jobs,") >= 2
    assert source.count("extended,") >= 2


def test_image_lab_mutating_and_truth_routes_have_matching_methods() -> None:
    registered = _route_methods(extended.router, image_studio_jobs.router)
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
    assert not missing, f"Image Lab frontend contract has missing Gateway routes: {missing}"


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
