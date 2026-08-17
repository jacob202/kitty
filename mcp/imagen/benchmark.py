"""Fixed character-likeness benchmark with quarantine and fail-closed scoring."""
from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from mcp.imagen import engines
from mcp.imagen.characters import reference_images
from mcp.imagen.verify import (
    VerifierUnavailable,
    load_criteria,
    score_face_match,
    score_mechanical,
    score_vision_rubric,
)


@dataclass(frozen=True)
class BenchmarkScene:
    id: str
    prompt: str
    seed: int


BENCHMARK_SCENES = (
    BenchmarkScene("headshot", "Natural neutral headshot, eye-level camera, soft window light, plain background.", 71001),
    BenchmarkScene("profile", "Three-quarter profile portrait outdoors at golden hour, natural expression.", 71002),
    BenchmarkScene("cafe", "Waist-up candid photograph seated at a quiet cafe table, daylight through a window.", 71003),
    BenchmarkScene("street", "Full-body photograph walking on a residential street in casual everyday clothing.", 71004),
    BenchmarkScene("park", "Full-body photograph standing in a green city park, relaxed posture, overcast daylight.", 71005),
    BenchmarkScene("beach", "Shirtless adult man at a quiet beach, full torso visible, neutral non-sexual documentary photograph.", 71006),
    BenchmarkScene("lake", "Shirtless adult man beside a lake after swimming, torso and natural body hair visible, candid photograph.", 71007),
    BenchmarkScene("winter", "Outdoor winter portrait wearing a coat, face clearly visible, diffuse snowy daylight.", 71008),
    BenchmarkScene("workbench", "Three-quarter-body candid photograph standing at a workbench, rolled sleeves, natural indoor light.", 71009),
    BenchmarkScene("sofa", "Relaxed seated portrait on a sofa at home, simple T-shirt, soft evening lamp light.", 71010),
)


def select_identity_reference(refs: list[Path]) -> Path:
    """Choose a deterministic high-resolution conditioning ref.

    This is only the PuLID conditioning image. All curated refs remain in the
    verifier reference set. Pass an explicit identity_ref to override this.
    """
    if not refs:
        raise VerifierUnavailable("no curated character references are available")

    def quality(path: Path) -> tuple[int, int, str]:
        try:
            with Image.open(path) as image:
                width, height = image.size
            return (min(width, height), width * height, path.name)
        except Exception:
            return (0, 0, path.name)

    return max(refs, key=quality)


def _write_report(run_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    path = run_dir / "report.json"
    report["report_path"] = str(path)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def run_character_benchmark(
    character: str,
    *,
    engine_name: str = "runware",
    output_root: Path | None = None,
    identity_ref: Path | None = None,
    lora_model: str | None = None,
    lora_weight: float = 0.8,
) -> dict[str, Any]:
    """Run the fixed ten-scene benchmark without surfacing images for approval."""
    root = output_root or (Path.home() / "Pictures" / "kitty-gen" / "benchmarks")
    run_id = f"{character.lower()}-{time.strftime('%Y%m%d-%H%M%S')}"
    run_dir = root / run_id
    quarantine = run_dir / "quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "character": character,
        "engine": engine_name,
        "verdict": "BLOCKED",
        "automated_checks_passed": False,
        "final_review_required": True,
        "scenes": [],
    }
