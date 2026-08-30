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
from math import isfinite, sqrt
from pathlib import Path
from typing import Any, Sequence


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


@dataclass(frozen=True)
class CharacterFaceReference:
    """One face reference bound to an expected cast slot and Character."""

    cast_slot: str
    character_id: str
    path: Path | str
    position: str | None = None


@dataclass(frozen=True)
class FaceDetection:
    """One detected candidate face with geometry and embedding evidence."""

    detection_id: str
    bbox: tuple[float, float, float, float]
    embedding: Sequence[float]

    @property
    def center_x(self) -> float:
        return (float(self.bbox[0]) + float(self.bbox[2])) / 2.0

    @property
    def center_y(self) -> float:
        return (float(self.bbox[1]) + float(self.bbox[3])) / 2.0


@dataclass(frozen=True)
class MultiFaceAssignmentEvidence:
    """Raw face evidence plus canonical identity-assignment result."""

    character_ids: tuple[str, ...]
    detected: tuple[FaceDetection, ...]
    detected_cast_slots: tuple[str, ...]
    reference_similarity_matrix: tuple[tuple[float, ...], ...]
    character_similarity_matrix: tuple[tuple[float, ...], ...]
    assignment: Any


def _embedding_values(value: Sequence[float], *, field: str) -> tuple[float, ...]:
    try:
        values = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise FaceScorerUnavailable(f"{field} embedding is malformed") from exc
    if not values or any(not isfinite(item) for item in values):
        raise FaceScorerUnavailable(f"{field} embedding is malformed")
    return values


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    a = _embedding_values(left, field="reference")
    b = _embedding_values(right, field="candidate")
    if len(a) != len(b):
        raise FaceScorerUnavailable("face embedding dimensions do not match")
    a_norm = sqrt(sum(value * value for value in a))
    b_norm = sqrt(sum(value * value for value in b))
    if a_norm == 0.0 or b_norm == 0.0:
        raise FaceScorerUnavailable("face embedding has zero norm")
    return sum(x * y for x, y in zip(a, b)) / (a_norm * b_norm)


class _InsightFaceMultiBackend:
    """Lazy production backend for the multi-reference evidence path."""

    def __init__(self) -> None:
        self._app: Any = None

    def _ensure_ready(self) -> Any:
        if self._app is not None:
            return self._app
        if importlib.util.find_spec("insightface") is None:
            raise FaceScorerUnavailable("insightface is not installed")
        if importlib.util.find_spec("cv2") is None:
            raise FaceScorerUnavailable("opencv (cv2) is not installed")
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))
        self._app = app
        return app

    @staticmethod
    def _decode(data: bytes, *, label: str) -> Any:
        import cv2
        import numpy as np

        image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise FaceScorerUnavailable(f"{label} image could not be decoded")
        return image

    def embed_reference(self, path: Path | str) -> Sequence[float]:
        app = self._ensure_ready()
        reference_path = Path(path)
        image = self._decode(reference_path.read_bytes(), label="reference")
        faces = app.get(image)
        if not faces:
            raise FaceScorerUnavailable(f"no face detected in reference: {reference_path}")
        return faces[0].embedding

    def detect(self, image_data: bytes) -> list[FaceDetection]:
        image = self._decode(image_data, label="candidate")
        faces = self._ensure_ready().get(image)
        result: list[FaceDetection] = []
        for index, face in enumerate(faces):
            bbox = tuple(float(value) for value in face.bbox)
            if len(bbox) != 4:
                raise FaceScorerUnavailable("detected face bbox is malformed")
            result.append(
                FaceDetection(
                    detection_id=f"face_{index + 1}",
                    bbox=(bbox[0], bbox[1], bbox[2], bbox[3]),
                    embedding=face.embedding,
                )
            )
        return result


class MultiFaceMatcher:
    """Build all-reference/all-face evidence and score cast identity assignment."""

    def __init__(
        self,
        references: Sequence[CharacterFaceReference],
        *,
        backend: Any | None = None,
    ) -> None:
        self._references = tuple(references)
        if not self._references:
            raise FaceScorerUnavailable("at least one character face reference is required")
        self._backend = backend or _InsightFaceMultiBackend()
        self._reference_embeddings: tuple[tuple[float, ...], ...] | None = None
        self._validate_references()

    def _validate_references(self) -> None:
        by_character: dict[str, tuple[str, str | None]] = {}
        for reference in self._references:
            if not reference.cast_slot or not reference.character_id:
                raise FaceScorerUnavailable("character reference ids must be non-empty")
            previous = by_character.get(reference.character_id)
            current = (reference.cast_slot, reference.position)
            if previous is not None and previous != current:
                raise FaceScorerUnavailable(
                    f"character {reference.character_id!r} has inconsistent cast metadata"
                )
            by_character[reference.character_id] = current
        if len(by_character) > 2:
            raise FaceScorerUnavailable("multi-face assignment v1 supports at most two characters")

    def _load_reference_embeddings(self) -> tuple[tuple[float, ...], ...]:
        if self._reference_embeddings is None:
            embeddings: list[tuple[float, ...]] = []
            for reference in self._references:
                try:
                    embedding = self._backend.embed_reference(reference.path)
                except OSError as exc:
                    raise FaceScorerUnavailable(
                        f"reference {reference.path!s} unavailable"
                    ) from exc
                embeddings.append(
                    _embedding_values(
                        embedding,
                        field=f"reference {reference.character_id}",
                    )
                )
            self._reference_embeddings = tuple(embeddings)
        return self._reference_embeddings

    def _character_groups(self) -> tuple[tuple[str, str, str | None, tuple[int, ...]], ...]:
        groups: dict[str, tuple[str, str | None, list[int]]] = {}
        order: list[str] = []
        for index, reference in enumerate(self._references):
            if reference.character_id not in groups:
                groups[reference.character_id] = (reference.cast_slot, reference.position, [])
                order.append(reference.character_id)
            groups[reference.character_id][2].append(index)
        return tuple(
            (character_id, groups[character_id][0], groups[character_id][1], tuple(groups[character_id][2]))
            for character_id in order
        )

    @staticmethod
    def _detected_slots(
        detected: Sequence[FaceDetection],
        groups: Sequence[tuple[str, str, str | None, tuple[int, ...]]],
    ) -> tuple[str, ...]:
        if len(groups) == 1:
            if not detected:
                return ()
            return (groups[0][1],) + tuple(
                f"unassigned_{index}" for index in range(1, len(detected))
            )
        positions = {position: cast_slot for _, cast_slot, position, _ in groups}
        if set(positions) != {"left", "right"}:
            raise FaceScorerUnavailable(
                "two-character identity assignment requires distinct left/right placement"
            )
        if len(detected) < 2:
            return tuple(f"unassigned_{index + 1}" for index in range(len(detected)))
        ranked = sorted(
            enumerate(detected),
            key=lambda item: (item[1].center_x, item[1].detection_id),
        )
        slots = [f"unassigned_{index + 1}" for index in range(len(detected))]
        slots[ranked[0][0]] = positions["left"]
        slots[ranked[-1][0]] = positions["right"]
        next_unassigned = 1
        for index, slot in enumerate(slots):
            if slot.startswith("unassigned_"):
                slots[index] = f"unassigned_{next_unassigned}"
                next_unassigned += 1
        return tuple(slots)

    def score_assignment(
        self,
        image_data: bytes,
        *,
        min_similarity: float = 0.45,
        min_margin: float = 0.05,
    ) -> MultiFaceAssignmentEvidence:
        from gateway.image_identity_assignment import (
            DetectedIdentity,
            ExpectedIdentity,
            score_identity_assignment,
        )

        reference_embeddings = self._load_reference_embeddings()
        detected = tuple(self._backend.detect(image_data))
        for face in detected:
            if not face.detection_id or len(face.bbox) != 4:
                raise FaceScorerUnavailable("detected face evidence is malformed")
        reference_matrix = tuple(
            tuple(_cosine(reference, face.embedding) for face in detected)
            for reference in reference_embeddings
        )
        groups = self._character_groups()
        character_matrix = tuple(
            tuple(
                sum(reference_matrix[index][column] for index in ref_indexes) / len(ref_indexes)
                for column in range(len(detected))
            )
            for _, _, _, ref_indexes in groups
        )
        detected_slots = self._detected_slots(detected, groups)
        expected = tuple(
            ExpectedIdentity(cast_slot=cast_slot, character_id=character_id)
            for character_id, cast_slot, _, _ in groups
        )
        detected_identities = tuple(
            DetectedIdentity(detection_id=face.detection_id, cast_slot=detected_slots[index])
            for index, face in enumerate(detected)
        )
        assignment = score_identity_assignment(
            expected,
            detected_identities,
            character_matrix,
            min_similarity=min_similarity,
            min_margin=min_margin,
        )
        return MultiFaceAssignmentEvidence(
            character_ids=tuple(character_id for character_id, _, _, _ in groups),
            detected=detected,
            detected_cast_slots=detected_slots,
            reference_similarity_matrix=reference_matrix,
            character_similarity_matrix=character_matrix,
            assignment=assignment,
        )
