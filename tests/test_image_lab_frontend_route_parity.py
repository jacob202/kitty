from __future__ import annotations


IMAGE_LAB = "gateway/kitty-chat/src/components/ImageLab.tsx"
EXTENDED = "gateway/routes/extended.py"
IMAGE_JOBS = "gateway/routes/image_studio_jobs.py"
REGISTER = "gateway/routes/register.py"


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def test_image_lab_owning_routers_are_mounted() -> None:
    source = _read(REGISTER)
    assert source.count("image_studio_jobs,") >= 2
    assert source.count("extended,") >= 2


def test_image_lab_mutating_and_truth_routes_have_matching_methods() -> None:
    extended = _read(EXTENDED)
    image_jobs = _read(IMAGE_JOBS)
    required = {
        '@router.get("/image/status")': extended,
        '@router.post("/studio/sessions")': extended,
        '@router.get("/studio/sessions/{session_id}")': extended,
        '@router.post("/studio/sessions/{session_id}/anchor")': extended,
        '@router.post("/studio/agent")': extended,
        '@router.post("/studio/estimate")': image_jobs,
        '@router.post("/studio/batches")': image_jobs,
        '@router.get("/studio/batches")': image_jobs,
        '@router.get("/studio/batches/{batch_id}")': image_jobs,
        '@router.post("/studio/batches/{batch_id}/cancel")': image_jobs,
    }
    missing = [contract for contract, source in required.items() if contract not in source]
    assert not missing, f"Image Lab frontend contract has missing Gateway routes: {missing}"


def test_image_lab_frontend_still_uses_the_routes_guarded_above() -> None:
    source = _read(IMAGE_LAB)
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
