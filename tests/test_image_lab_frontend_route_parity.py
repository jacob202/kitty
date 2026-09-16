IMAGE_LAB = "gateway/kitty-chat/src/components/ImageLab.tsx"
IMAGE_GENERATION = "gateway/routes/image_generation.py"
IMAGE_STUDIO = "gateway/routes/image_studio.py"
IMAGE_JOBS = "gateway/routes/image_studio_jobs.py"
REGISTER = "gateway/routes/register.py"


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def test_image_lab_owning_routers_are_mounted() -> None:
    source = _read(REGISTER)
    assert source.count("image_studio_jobs,") >= 2
    assert source.count("image_generation,") >= 2
    assert source.count("image_studio,") >= 2


def test_image_lab_mutating_and_truth_routes_have_matching_methods() -> None:
    image_generation = _read(IMAGE_GENERATION)
    image_studio = _read(IMAGE_STUDIO)
    image_jobs = _read(IMAGE_JOBS)
    required = {
        '@router.get("/image/status")': image_generation,
        '@router.post("/studio/sessions")': image_studio,
        '@router.get("/studio/sessions/{session_id}")': image_studio,
        '@router.patch("/studio/sessions/{session_id}")': image_studio,
        '@router.post("/studio/sessions/{session_id}/anchor")': image_studio,
        '@router.post("/studio/agent")': image_studio,
        '@router.get("/studio/characters")': image_studio,
        '@router.post("/studio/characters/{character_id}/references")': image_studio,
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
        "fetch(`/proxy/studio/sessions/${encodeURIComponent(sessionId)}`",
        "fetch('/proxy/studio/characters'",
        "fetch(`/proxy/studio/characters/${characterId}/references`",
        "fetch(`/proxy/studio/sessions/${encodeURIComponent(sessionId)}/anchor`",
        "fetch('/proxy/studio/agent'",
        "fetch('/proxy/studio/batches'",
        "fetch(`/proxy/studio/batches?session_id=${encodeURIComponent(stored)}`",
        "fetch(`/proxy/studio/batches/${batchId}`",
        "fetch(`/proxy/studio/batches/${batchId}/cancel`",
    )
    missing = [fragment for fragment in required_frontend_fragments if fragment not in source]
    assert not missing, f"Image Lab network controls drifted from the parity gate: {missing}"
