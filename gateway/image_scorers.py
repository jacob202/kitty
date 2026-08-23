"""Fail-closed production scorer adapters for Image Lab evaluation.

The canonical evaluator lives in :mod:`gateway.image_evaluation`.  This module
only adapts concrete local evidence sources into versioned ``ScorerResult``
objects.  Missing dependencies, unreadable images, unavailable local models,
or ambiguous model output are infrastructure failures, never neutral scores.
"""

from __future__ import annotations

import base64
import io
import math
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlparse

import httpx
from PIL import Image, UnidentifiedImageError

from gateway.image_evaluation import EvaluationUnavailable, ScorerResult
from mcp.imagen.face_match import FaceMatcher, FaceScorerUnavailable

MECHANICS_SCORER_VERSION = "mechanics-pil@1"
IDENTITY_SCORER_VERSION = "identity-insightface-buffalo_l@1"
OLLAMA_RUBRIC_ADAPTER_VERSION = "ollama-rubric@1"
_MIN_DIMENSION = 256
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _read_image_bytes(image_path: str) -> bytes:
    try:
        return Path(image_path).read_bytes()
    except OSError as exc:
        raise EvaluationUnavailable(f"could not read scorer image {image_path!r}") from exc


def mechanics_scorer(image_path: str) -> ScorerResult:
    """Decode a candidate and verify basic artifact mechanics with Pillow."""
    data = _read_image_bytes(image_path)
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            rgb = image.convert("RGB")
            extrema = rgb.getextrema()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise EvaluationUnavailable("mechanics scorer could not decode candidate image") from exc

    blank = all(low == high for low, high in extrema)
    too_small = width < _MIN_DIMENSION or height < _MIN_DIMENSION
    labels: list[str] = []
    if blank:
        labels.append("mechanics_blank")
    if too_small:
        labels.append("mechanics_too_small")
    passed = not labels
    return ScorerResult(
        passed=passed,
        score={
            "width": width,
            "height": height,
            "size_bytes": len(data),
            "blank": blank,
        },
        version=MECHANICS_SCORER_VERSION,
        labels=labels or ["mechanics_ok"],
    )


def make_identity_scorer(
    reference_path: str,
    *,
    threshold: float = 0.45,
) -> Callable[[str], ScorerResult]:
    """Create an exact-reference InsightFace scorer that fails closed."""
    if not math.isfinite(float(threshold)) or not 0 <= float(threshold) <= 1:
        raise EvaluationUnavailable("identity threshold must be finite and between 0 and 1")
    reference = Path(reference_path)
    if not reference.is_file():
        raise EvaluationUnavailable("identity reference image is missing")
    matcher = FaceMatcher(reference)

    def score(image_path: str) -> ScorerResult:
        data = _read_image_bytes(image_path)
        try:
            result = matcher.score(data)
        except (FaceScorerUnavailable, OSError, ValueError) as exc:
            raise EvaluationUnavailable(f"identity scorer unavailable: {exc}") from exc
        passed = result.similarity >= threshold
        return ScorerResult(
            passed=passed,
            score={
                "similarity": result.similarity,
                "threshold": threshold,
                "reference_faces": result.reference_faces,
                "candidate_faces": result.candidate_faces,
            },
            version=IDENTITY_SCORER_VERSION,
            labels=["identity_ok" if passed else "identity_fail"],
        )

    return score


def _require_loopback(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in _LOOPBACK_HOSTS:
        raise EvaluationUnavailable("ImageBench local VLM endpoint must be loopback-only")
    return base_url.rstrip("/")


def _verify_ollama_model_revision(base_url: str, model: str, expected_revision: str) -> None:
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=5)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise EvaluationUnavailable("local VLM model provenance is unavailable") from exc
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise EvaluationUnavailable("local VLM model provenance response is malformed")
    match = next(
        (
            item
            for item in models
            if isinstance(item, dict) and (item.get("name") == model or item.get("model") == model)
        ),
        None,
    )
    if match is None:
        raise EvaluationUnavailable(f"local VLM model {model!r} is not installed")
    actual_revision = match.get("digest")
    if not isinstance(actual_revision, str) or not actual_revision.strip():
        raise EvaluationUnavailable("local VLM model digest is unavailable")
    if actual_revision.strip() != expected_revision:
        raise EvaluationUnavailable(
            f"local VLM model revision mismatch: expected {expected_revision!r}, "
            f"observed {actual_revision.strip()!r}"
        )


def make_ollama_rubric_scorer(
    *,
    dimension: str,
    prompt: str,
    rubric: str,
    model: str,
    model_revision: str,
    base_url: str = "http://127.0.0.1:11434",
    auxiliary_image_paths: Iterable[str] = (),
) -> Callable[[str], ScorerResult]:
    """Create a strict binary rubric scorer backed by a pinned local Ollama VLM.

    The candidate is image 1.  Any auxiliary images follow in caller-specified
    order so role/edit scorers can compare against references while
    keeping the transport local.  The caller must pin a model revision/digest;
    a model name alone is insufficient scorer provenance.
    """
    dimension = dimension.strip()
    prompt = prompt.strip()
    rubric = rubric.strip()
    model = model.strip()
    model_revision = model_revision.strip()
    if not dimension or not prompt or not rubric or not model:
        raise EvaluationUnavailable("local VLM scorer configuration is incomplete")
    if not model_revision:
        raise EvaluationUnavailable("local VLM scorer requires a pinned model revision")
    endpoint = _require_loopback(base_url) + "/api/generate"
    auxiliary = tuple(str(Path(path)) for path in auxiliary_image_paths)
    version = f"{OLLAMA_RUBRIC_ADAPTER_VERSION}:{model}@{model_revision}"

    revision_verified = False

    def score(image_path: str) -> ScorerResult:
        nonlocal revision_verified
        if not revision_verified:
            _verify_ollama_model_revision(
                endpoint.rsplit("/api/generate", 1)[0], model, model_revision
            )
            revision_verified = True
        image_paths = (image_path, *auxiliary)
        try:
            images = [
                base64.b64encode(_read_image_bytes(path)).decode("ascii") for path in image_paths
            ]
        except EvaluationUnavailable:
            raise
        instruction = (
            "You are a deterministic image-evaluation scorer. "
            "Image 1 is the generated candidate. Additional images, when present, are references "
            "in the exact order supplied by the benchmark.\n\n"
            f"Original generation prompt: {prompt}\n"
            f"Dimension: {dimension}\n"
            f"Criterion: {rubric}\n\n"
            "Answer exactly YES or NO. Do not add explanation."
        )
        try:
            response = httpx.post(
                endpoint,
                json={
                    "model": model,
                    "prompt": instruction,
                    "images": images,
                    "stream": False,
                },
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise EvaluationUnavailable(f"local VLM scorer unavailable for {dimension!r}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("response"), str):
            raise EvaluationUnavailable("local VLM scorer returned malformed response evidence")
        answer = payload["response"].strip().upper()
        if answer.startswith("YES"):
            passed = True
        elif answer.startswith("NO"):
            passed = False
        else:
            raise EvaluationUnavailable("local VLM scorer must return strict YES or NO evidence")
        return ScorerResult(
            passed=passed,
            score=1.0 if passed else 0.0,
            version=version,
            labels=[f"{dimension}_{'ok' if passed else 'fail'}"],
        )

    return score


_VLM_RUBRICS = {
    "photorealism": (
        "The candidate should read as a plausible real camera photograph: natural skin, "
        "lighting, texture, optics, and detail without obvious CGI, illustration, or synthetic artifacts."
    ),
    "anatomy": (
        "Visible human anatomy must be physically plausible, with coherent proportions, joints, "
        "limbs, hands, feet, fingers, overlap, and foreshortening for the requested pose."
    ),
    "prompt_adherence": (
        "The candidate must visibly satisfy the material content and requested transformation in the original prompt."
    ),
    "reference_role": (
        "The candidate must use each supplied reference only for its requested semantic role and avoid leaking identity "
        "or unrelated traits from a non-identity reference."
    ),
    "composition": (
        "The candidate composition must be spatially coherent and match the requested subject count, placement, pose, and scene."
    ),
    "requested_change": (
        "The requested edit must be visibly present in the candidate compared with the supplied pre-edit reference."
    ),
    "edit_locality": (
        "Compared with the supplied pre-edit reference, non-target regions and protected traits must remain materially unchanged."
    ),
}
_REFERENCE_COMPARISON_SCORERS = frozenset({"reference_role", "requested_change", "edit_locality"})


def build_imagebench_scorers(
    *,
    required_scorers: Iterable[str],
    prompt: str,
    identity_reference_path: str | None = None,
    identity_threshold: float = 0.45,
    auxiliary_image_paths: Iterable[str] = (),
    vlm_model: str | None = None,
    vlm_model_revision: str | None = None,
    vlm_base_url: str = "http://127.0.0.1:11434",
) -> dict[str, Callable[[str], ScorerResult]]:
    """Build only the production scorers for which required evidence is configured.

    Missing configuration deliberately leaves a scorer absent.  Passing the returned
    mapping to :func:`gateway.image_evaluation.evaluate_image` therefore turns a
    missing identity reference, canonical structured assignment evidence, local VLM, pinned model revision, or comparison
    reference into the evaluator's normal fail-closed infrastructure error.
    """
    requested = [name.strip() for name in required_scorers if isinstance(name, str)]
    auxiliary = tuple(auxiliary_image_paths)
    scorers: dict[str, Callable[[str], ScorerResult]] = {}
    for name in requested:
        # Assignment is intentionally not adapted here: gateway.image_identity_assignment
        # owns that dimension and requires structured detections + similarity evidence.
        if name == "assignment":
            continue
        if name == "mechanics":
            scorers[name] = mechanics_scorer
            continue
        if name == "identity":
            if identity_reference_path:
                scorers[name] = make_identity_scorer(
                    identity_reference_path, threshold=identity_threshold
                )
            continue
        rubric = _VLM_RUBRICS.get(name)
        if rubric is None or not vlm_model or not vlm_model_revision:
            continue
        if name in _REFERENCE_COMPARISON_SCORERS and not auxiliary:
            continue
        scorers[name] = make_ollama_rubric_scorer(
            dimension=name,
            prompt=prompt,
            rubric=rubric,
            model=vlm_model,
            model_revision=vlm_model_revision,
            base_url=vlm_base_url,
            auxiliary_image_paths=auxiliary,
        )
    return scorers


__all__ = [
    "IDENTITY_SCORER_VERSION",
    "MECHANICS_SCORER_VERSION",
    "OLLAMA_RUBRIC_ADAPTER_VERSION",
    "build_imagebench_scorers",
    "make_identity_scorer",
    "make_ollama_rubric_scorer",
    "mechanics_scorer",
]
