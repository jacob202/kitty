"""Verification loop — generate, score, keep best, stop early.

``generate_until`` runs a criteria-verified generation pipeline: generate N
images scoring each against a criteria file, stop early when one passes all
hard gates, keep the best-N across all attempts.

Every attempt is logged to ``~/Pictures/kitty-gen/runs/<run-id>/attempts.jsonl``.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from mcp.imagen import engines
from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.logger import log
from mcp.imagen.retry import retry_with_backoff

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Attempt:
    """One generate + score cycle."""

    attempt_number: int
    image_data: bytes
    saved_path: Path
    scores: dict[str, float] = field(default_factory=dict)
    passed: bool = False
    seed: int | None = None


@dataclass
class Criteria:
    """Parsed criteria file — defines what 'good' means for one goal."""

    name: str
    face_match: dict[str, Any] | None = None
    rubric: list[dict[str, Any]] = field(default_factory=list)
    mechanical: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Criteria loader
# ---------------------------------------------------------------------------


def load_criteria(name: str) -> Criteria:
    """Load a criteria file from ``config/imagen/criteria/<name>.json``.

    Returns a best-effort default if the file doesn't exist (no hard gates,
    soft scores only) so the loop degrades gracefully without a criteria file.
    """
    path = _criteria_path(name)
    if not path.exists():
        log.warning("criteria file not found: %s — using default soft-only gate", path)
        return Criteria(name=name)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("failed to parse criteria %s: %s", path, e)
        return Criteria(name=name)

    rubric_entries = []
    for entry in raw.get("rubric", []):
        if isinstance(entry, str):
            rubric_entries.append({"text": entry, "hard": False})
        elif isinstance(entry, dict):
            rubric_entries.append(entry)

    return Criteria(
        name=name,
        face_match=raw.get("face_match"),
        rubric=rubric_entries,
        mechanical=raw.get("mechanical"),
    )


def _criteria_path(name: str) -> Path:
    return settings.faces_dir.parent / "criteria" / f"{name}.json"


# ---------------------------------------------------------------------------
# Scorers — each returns a float in [0.0, 1.0]; 1.0 = perfect
# ---------------------------------------------------------------------------


def score_mechanical(image_data: bytes, cfg: dict[str, Any] | None) -> float:
    """Check resolution floor, file-size sanity, and blank/black detection.

    1.0 = passes all mechanical checks; 0.0 = fails a hard one.
    """
    if cfg is None:
        return 1.0

    min_width = cfg.get("min_width", 0)
    min_height = cfg.get("min_height", 0)
    min_size_bytes = cfg.get("min_size_bytes", 1024)
    max_size_bytes = cfg.get("max_size_bytes", 20 * 1024 * 1024)
    reject_blank = cfg.get("reject_blank", True)

    if len(image_data) < min_size_bytes:
        return 0.0
    if len(image_data) > max_size_bytes:
        return 0.0

    if reject_blank and _is_blank(image_data):
        return 0.0

    if min_width > 0 or min_height > 0:
        w, h = _guess_dimensions(len(image_data))
        if w < min_width or h < min_height:
            return 0.0

    return 1.0


def _is_blank(image_data: bytes, threshold: int = 32) -> bool:
    """Quick check if an image is mostly blank/black — reads enough bytes to guess."""
    try:
        import io

        from PIL import Image as PILImage

        pil_img: PILImage.Image = PILImage.open(io.BytesIO(image_data))
        if pil_img.mode == "RGBA":
            pil_img = pil_img.convert("RGB")
        extrema = pil_img.getextrema()
        if isinstance(extrema[0], tuple):
            channel_extrema = cast(tuple[tuple[int, int], ...], extrema)
            avg_max = sum(mx for _, mx in channel_extrema) / len(channel_extrema)
            avg_min = sum(mn for mn, _ in channel_extrema) / len(channel_extrema)
        else:
            scalar_extrema = cast(tuple[float, float], extrema)
            avg_max = float(scalar_extrema[1])
            avg_min = float(scalar_extrema[0])
        return avg_max < threshold and avg_min < threshold
    except Exception:
        return False


def _guess_dimensions(data_len: int) -> tuple[int, int]:
    """Rough PNG dimension guess from file size — used for mechanical pre-check.

    Returns (1, 1) when guess is unreliable so min_width/height passes through.
    """
    if data_len < 100:
        return 1, 1
    approx_pixels = data_len // 3
    side = int(approx_pixels ** 0.5)
    return max(side, 1), max(side, 1)


def score_vision_rubric(
    image_data: bytes,
    rubric_entries: list[dict[str, Any]],
    prompt: str,
) -> tuple[float, list[str]]:
    """Score image against rubric lines via a local VLM (Ollama).

    Returns (score, details) where score is the fraction of passed checks and
    details lists which lines failed (for the log).
    """
    if not rubric_entries:
        return 1.0, []

    prompt_text = _build_rubric_prompt(rubric_entries, prompt)
    try:
        response = _ollama_vision(image_data, prompt_text)
    except Exception as e:
        log.warning("vision rubric call failed: %s", e)
        return 0.5, ["vision_rubric unavailable"]

    return _parse_rubric_response(response, rubric_entries)


def _build_rubric_prompt(entries: list[dict[str, Any]], prompt: str) -> str:
    lines = "\n".join(f"- {e['text']}" for e in entries)
    return (
        f"Original prompt: {prompt}\n\n"
        f"Score this generated image against these criteria. "
        f"Answer YES or NO for each line:\n{lines}\n\n"
        f"Reply with one YES/NO per line, in order."
    )


@retry_with_backoff(attempts=2)
def _ollama_vision(image_data: bytes, prompt_text: str) -> str:
    """Send an image to Ollama's local VLM for scoring."""
    import base64

    import httpx

    b64 = base64.b64encode(image_data).decode("utf-8")
    payload = {
        "model": settings.vision_model,
        "prompt": prompt_text,
        "images": [b64],
        "stream": False,
    }
    url = f"{settings.ollama_url.rstrip('/')}/api/generate"
    resp = httpx.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json().get("response", "")


def _parse_rubric_response(
    response: str, entries: list[dict[str, Any]]
) -> tuple[float, list[str]]:
    """Parse Ollama's YES/NO response into a score and failure list."""
    lines = response.strip().split("\n")
    passed = 0
    failed_lines: list[str] = []

    for i, entry in enumerate(entries):
        answer = lines[i].strip().upper() if i < len(lines) else "NO"
        if answer.startswith("YES"):
            passed += 1
        elif entry.get("hard", False):
            failed_lines.append(f"HARD FAIL: {entry['text']}")

    total = len(entries)
    score = passed / total if total > 0 else 1.0
    return score, failed_lines


def score_face_match(image_data: bytes, cfg: dict[str, Any] | None) -> float:
    """Compare image face(s) against a reference set via InsightFace.

    1.0 = strong face match; 0.0 = no face or no reference set configured.

    InsightFace is a heavy optional dependency. If not installed this scorer
    returns 1.0 (no penalty) and logs a warning.
    """
    if cfg is None:
        return 1.0

    character = cfg.get("character", "")
    ref_dir = settings.faces_dir / character

    if not ref_dir.exists():
        log.warning("face_match: reference directory not found: %s", ref_dir)
        return 1.0

    ref_images = sorted(ref_dir.glob("*"))
    if not ref_images:
        return 1.0

    import importlib.util

    if importlib.util.find_spec("insightface") is None:
        log.warning("face_match: insightface not installed — skipping")
        return 1.0

    import numpy as np
    from insightface.app import FaceAnalysis

    try:
        import cv2
        import numpy as np

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))

        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return 0.0

        faces = app.get(img)
        if not faces:
            return 0.0

        target_emb = faces[0].embedding

        best_sim = 0.0
        for ref_path in ref_images:
            ref_bytes = ref_path.read_bytes()
            ref_np = np.frombuffer(ref_bytes, np.uint8)
            ref_img = cv2.imdecode(ref_np, cv2.IMREAD_COLOR)
            if ref_img is None:
                continue
            ref_faces = app.get(ref_img)
            if not ref_faces:
                continue
            ref_emb = ref_faces[0].embedding
            sim = float(np.dot(target_emb, ref_emb) / (
                np.linalg.norm(target_emb) * np.linalg.norm(ref_emb) + 1e-8
            ))
            if sim > best_sim:
                best_sim = sim

        # Convert cosine similarity to a score in [0, 1] where threshold maps to 0.5
        score = best_sim
        return score
    except Exception as e:
        log.warning("face_match scoring error: %s", e)
        return 0.5


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def generate_until(
    prompt: str,
    criteria_name: str,
    engine: str = "",
    max_attempts: int = 8,
    keep: int = 3,
    private: bool = False,
    init_image: str | None = None,
) -> list[dict[str, Any]]:
    """Generate, score, keep best, stop early.

    Args:
        prompt: Generation prompt.
        criteria_name: Name of a criteria file in ``config/imagen/criteria/``.
        engine: Engine name (default from settings).
        max_attempts: Maximum generation rounds (default 8).
        keep: How many best candidates to return (default 3).
        private: When True, refuse cloud engines.

    Returns:
        A list of result dicts with keys:
          image_data (bytes), saved_path (str), scores (dict), attempt (int),
          passed (bool), seed (int or None)
        Sorted by best score first, limited to ``keep``.
    """
    eng_name = engine or settings.default_engine
    eng = engines.get(eng_name)

    if private:
        _check_private(eng_name)

    criteria = load_criteria(criteria_name)
    run_id = uuid.uuid4().hex[:12]
    run_dir = Path.home() / "Pictures" / "kitty-gen" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "attempts.jsonl"

    attempts: list[Attempt] = []
    reseed = _make_seed_source()

    for attempt_num in range(1, max_attempts + 1):
        seed_val = reseed()
        try:
            data = eng.generate(prompt, seed=seed_val, init_image=init_image)
        except RefusalError as e:
            log.warning("attempt %d refused: %s", attempt_num, str(e)[:200])
            continue
        except Exception as e:
            log.warning("attempt %d failed: %s", attempt_num, str(e)[:200])
            continue

        path = run_dir / f"attempt_{attempt_num:03d}.png"
        path.write_bytes(data)

        # Score
        scores: dict[str, float] = {}
        score_mech = score_mechanical(data, criteria.mechanical)
        scores["mechanical"] = score_mech
        if score_mech < 0.5:
            # Failed mechanical — skip further scoring
            attempts.append(Attempt(
                attempt_number=attempt_num,
                image_data=data,
                saved_path=path,
                scores=scores,
                passed=False,
                seed=seed_val,
            ))
            _log_attempt(log_path, attempt_num, seed_val, scores, passed=False)
            continue

        score_face = score_face_match(data, criteria.face_match)
        scores["face_match"] = score_face

        score_rubric, rubric_fails = score_vision_rubric(data, criteria.rubric, prompt)
        scores["vision_rubric"] = score_rubric

        passed = bool(
            score_mech >= 0.5
            and score_face >= (criteria.face_match.get("threshold", 0.6) if criteria.face_match else 0.0)
            and score_rubric >= 0.5
            and not rubric_fails
        )

        attempt = Attempt(
            attempt_number=attempt_num,
            image_data=data,
            saved_path=path,
            scores=scores,
            passed=passed,
            seed=seed_val,
        )
        attempts.append(attempt)

        _log_attempt(log_path, attempt_num, seed_val, scores, passed=passed)

        if passed:
            log.info("attempt %d PASSED all criteria — stopping early", attempt_num)
            break

    # Sort by average score, best first
    attempts.sort(key=lambda a: sum(a.scores.values()) / max(len(a.scores), 1), reverse=True)

    results = []
    for a in attempts[:keep]:
        results.append({
            "image_data": a.image_data,
            "saved_path": str(a.saved_path),
            "scores": dict(a.scores),
            "attempt": a.attempt_number,
            "passed": a.passed,
            "seed": a.seed,
        })

    return results


def _check_private(engine: str) -> None:
    """Raise if engine is a cloud service and private flag is set."""
    cloud_engines = {"nano_banana", "imagen4", "dalle"}
    if engine in cloud_engines:
        raise ValueError(
            f"Engine {engine!r} is a cloud service and private=True was set. "
            "Use drawthings or comfyui for private personal creative work."
        )


def _make_seed_source():
    """Return a function that generates a new random seed each call."""
    import os

    def _next() -> int:
        return int.from_bytes(os.urandom(4), "little") & 0xFFFFFFFF

    return _next


def _log_attempt(
    log_path: Path,
    attempt_num: int,
    seed: int | None,
    scores: dict[str, float],
    passed: bool,
) -> None:
    """Append one JSON line to the run's attempts log."""
    entry = {
        "attempt": attempt_num,
        "seed": seed,
        "scores": scores,
        "passed": passed,
        "timestamp": time.time(),
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
