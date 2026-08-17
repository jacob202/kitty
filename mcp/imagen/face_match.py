"""Reusable exact-reference face matcher for the character benchmark.

Unlike ``verify.score_face_match`` (which globs an entire reference
directory and re-initializes InsightFace per call), this matcher scores a
generated image against exactly one reference embedding — the character's
locked reference — and initializes InsightFace once per benchmark run.

Fails closed: any missing dependency, undecodable reference, or reference
with no detectable face raises ``FaceScorerUnavailable`` rather than
returning a neutral or passing score.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class FaceScorerUnavailable(Exception):
    """InsightFace/opencv missing, or the locked reference has no usable face."""


@dataclass(frozen=True)
class FaceScore:
    similarity: float
    reference_faces: int
    candidate_faces: int


class FaceMatcher:
    """Loads InsightFace once, embeds the locked reference once, scores N candidates."""

    def __init__(self, reference_path: Path | str) -> None:
        self._reference_path = Path(reference_path)
        self._app: Any = None
        self._reference_embedding: Any = None

    def ensure_ready(self) -> None:
        """Load the face model and embed the reference, once. Idempotent."""
        if self._app is not None:
            return
        self._load()

    def score(self, image_data: bytes) -> FaceScore:
        """Score ``image_data`` against the locked reference embedding."""
        self.ensure_ready()
        import cv2
        import numpy as np

        arr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise FaceScorerUnavailable("candidate image could not be decoded")

        faces = self._app.get(img)
        if not faces:
            return FaceScore(similarity=0.0, reference_faces=1, candidate_faces=0)

        candidate_embedding = faces[0].embedding
        ref = np.asarray(self._reference_embedding)
        cand = np.asarray(candidate_embedding)
        similarity = float(
            np.dot(ref, cand) / (np.linalg.norm(ref) * np.linalg.norm(cand) + 1e-8)
        )
        return FaceScore(similarity=similarity, reference_faces=1, candidate_faces=len(faces))

    def _load(self) -> None:
        if importlib.util.find_spec("insightface") is None:
            raise FaceScorerUnavailable("insightface is not installed")
        if importlib.util.find_spec("cv2") is None:
            raise FaceScorerUnavailable("opencv (cv2) is not installed")

        import cv2
        import numpy as np
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))

        ref_bytes = self._reference_path.read_bytes()
        ref_arr = np.frombuffer(ref_bytes, np.uint8)
        ref_img = cv2.imdecode(ref_arr, cv2.IMREAD_COLOR)
        if ref_img is None:
            raise FaceScorerUnavailable(
                f"could not decode locked reference: {self._reference_path}"
            )

        ref_faces = app.get(ref_img)
        if not ref_faces:
            raise FaceScorerUnavailable(
                f"no face detected in locked reference: {self._reference_path}"
            )

        self._app = app
        self._reference_embedding = ref_faces[0].embedding
