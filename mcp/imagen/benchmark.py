"""Face-locked character benchmark — ten face-visible scenes scored against
exactly one locked reference image.

This benchmark proves facial identity conditioning only. A single portrait
cannot establish ground truth for body shape, body hair, or anything outside
the frame of that photo — no scene here tests for it, and none should be
added that do.

Every scene verdict, and the overall run verdict, is one of
``PASS_AUTOMATED`` / ``FAIL`` / ``BLOCKED``. ``PASS_AUTOMATED`` means the
automated checks passed; it is never final — ``final_review_required`` is
always ``True`` and a human still has to look at the quarantined images.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp.imagen import engines
from mcp.imagen.character_lock import CharacterLockError, resolve_locked_reference
from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.face_match import FaceMatcher, FaceScorerUnavailable

SCENES: list[dict[str, str]] = [
    {
        "name": "neutral_portrait",
        "prompt": "a neutral head-and-shoulders portrait, plain background, looking at camera",
    },
    {
        "name": "three_quarter_portrait",
        "prompt": "a three-quarter angle portrait, soft studio light, looking slightly off camera",
    },
    {
        "name": "outdoor_daylight",
        "prompt": "standing outdoors in bright daylight, face clearly visible, casual clothing",
    },
    {
        "name": "indoor_window_light",
        "prompt": "sitting indoors near a window, soft natural window light on the face",
    },
    {
        "name": "cafe",
        "prompt": "sitting at a cafe table, warm ambient light, face visible, holding a coffee cup",
    },
    {
        "name": "city_street",
        "prompt": "walking on a city street during the day, face visible toward camera",
    },
    {
        "name": "park",
        "prompt": "standing in a park with trees in the background, daylight, face visible",
    },
    {
        "name": "warm_indoor_light",
        "prompt": "in a living room under warm indoor lighting, relaxed expression, face visible",
    },
    {
        "name": "workbench",
        "prompt": "at a workbench in a workshop, focused expression, face visible, good lighting",
    },
    {
        "name": "seated_casual_portrait",
        "prompt": "a seated casual portrait, relaxed pose, natural light, face clearly visible",
    },
]

FACE_MATCH_PASS_THRESHOLD = 0.45
MIN_DIMENSION = 256


@dataclass
class SceneResult:
    scene: str
    seed: int
    prompt: str
    result: str  # PASS_AUTOMATED | FAIL | BLOCKED
    mechanical_ok: bool | None = None
    face_similarity: float | None = None
    error: str | None = None
    saved_path: str | None = None


@dataclass
class BenchmarkReport:
    character: str
    engine: str
    locked_reference_sha256: str
    run_id: str
    scenes: list[SceneResult] = field(default_factory=list)
    automated_verdict: str = "BLOCKED"
    final_review_required: bool = True
    quarantine_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "character": self.character,
            "engine": self.engine,
            "locked_reference_sha256": self.locked_reference_sha256,
            "run_id": self.run_id,
            "quarantine_dir": self.quarantine_dir,
            "scenes": [vars(s) for s in self.scenes],
            "automated_verdict": self.automated_verdict,
            "final_review_required": self.final_review_required,
        }


def run_character_benchmark(
    character: str,
    engine_name: str = "runware",
    seed_base: int = 1000,
) -> BenchmarkReport:
    """Run the 10-scene face-locked benchmark for ``character`` on ``engine_name``.

    The reference is resolved exclusively via the character lock — there is
    no fallback to any other image in any directory.
    """
    run_id = uuid.uuid4().hex[:12]
    quarantine_dir = _quarantine_dir(character, run_id)

    try:
        locked = resolve_locked_reference(character)
    except CharacterLockError as e:
        return _blocked_report(character, engine_name, "", run_id, quarantine_dir, str(e))

    try:
        eng = engines.get(engine_name)
    except ValueError as e:
        return _blocked_report(
            character, engine_name, locked.sha256, run_id, quarantine_dir, str(e)
        )

    matcher = FaceMatcher(locked.path)
    try:
        matcher.ensure_ready()
    except FaceScorerUnavailable as e:
        return _blocked_report(
            character, engine_name, locked.sha256, run_id, quarantine_dir, str(e)
        )

    quarantine_dir.mkdir(parents=True, exist_ok=True)

    scenes = [
        _run_scene(eng, matcher, locked.path, scene, seed_base + i, quarantine_dir)
        for i, scene in enumerate(SCENES)
    ]

    if any(s.result == "BLOCKED" for s in scenes):
        verdict = "BLOCKED"
    elif all(s.result == "PASS_AUTOMATED" for s in scenes):
        verdict = "PASS_AUTOMATED"
    else:
        verdict = "FAIL"

    report = BenchmarkReport(
        character=character,
        engine=engine_name,
        locked_reference_sha256=locked.sha256,
        run_id=run_id,
        scenes=scenes,
        automated_verdict=verdict,
        quarantine_dir=str(quarantine_dir),
    )
    _write_report(quarantine_dir, report)
    return report


def _run_scene(
    eng: Any,
    matcher: FaceMatcher,
    locked_path: Path,
    scene: dict[str, str],
    seed: int,
    quarantine_dir: Path,
) -> SceneResult:
    try:
        image_data = eng.generate(
            scene["prompt"],
            seed=seed,
            identity_images=[locked_path],
        )
    except RefusalError as e:
        return SceneResult(
            scene=scene["name"],
            seed=seed,
            prompt=scene["prompt"],
            result="FAIL",
            error=f"refused: {e}",
        )
    except Exception as e:
        return SceneResult(
            scene=scene["name"],
            seed=seed,
            prompt=scene["prompt"],
            result="BLOCKED",
            error=str(e),
        )

    saved_path = quarantine_dir / f"{scene['name']}.png"
    saved_path.write_bytes(image_data)

    mechanical_ok = _mechanical_ok(image_data)
    if not mechanical_ok:
        return SceneResult(
            scene=scene["name"],
            seed=seed,
            prompt=scene["prompt"],
            result="FAIL",
            mechanical_ok=False,
            saved_path=str(saved_path),
            error="mechanical check failed (too small, blank, or undecodable)",
        )

    try:
        face = matcher.score(image_data)
    except FaceScorerUnavailable as e:
        return SceneResult(
            scene=scene["name"],
            seed=seed,
            prompt=scene["prompt"],
            result="BLOCKED",
            mechanical_ok=True,
            saved_path=str(saved_path),
            error=str(e),
        )

    result = "PASS_AUTOMATED" if face.similarity >= FACE_MATCH_PASS_THRESHOLD else "FAIL"
    return SceneResult(
        scene=scene["name"],
        seed=seed,
        prompt=scene["prompt"],
        result=result,
        mechanical_ok=True,
        face_similarity=face.similarity,
        saved_path=str(saved_path),
    )


def _mechanical_ok(image_data: bytes) -> bool:
    """Real dimension decode via PIL — no byte-size guessing."""
    import io

    from PIL import Image, UnidentifiedImageError

    if len(image_data) < 1024:
        return False
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            width, height = img.size
    except (UnidentifiedImageError, OSError):
        return False
    return width >= MIN_DIMENSION and height >= MIN_DIMENSION


def _blocked_report(
    character: str,
    engine_name: str,
    sha: str,
    run_id: str,
    quarantine_dir: Path,
    error: str,
) -> BenchmarkReport:
    return BenchmarkReport(
        character=character,
        engine=engine_name,
        locked_reference_sha256=sha,
        run_id=run_id,
        scenes=[SceneResult(scene="setup", seed=0, prompt="", result="BLOCKED", error=error)],
        automated_verdict="BLOCKED",
        quarantine_dir=str(quarantine_dir),
    )


def _quarantine_dir(character: str, run_id: str) -> Path:
    return settings.output_dir / "quarantine" / character / run_id


def _write_report(quarantine_dir: Path, report: BenchmarkReport) -> None:
    (quarantine_dir / "report.json").write_text(
        json.dumps(report.to_dict(), indent=2), encoding="utf-8"
    )
