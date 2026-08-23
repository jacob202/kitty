"""Provider-neutral FLUX.2 semantic compiler, version flux2@1.

Kitty owns the meaning; Black Forest Labs does not own Kitty's plan schema.
This module turns Kitty's plan semantics into a single deterministic,
provider-independent compiled request (ADR 0040 decisions 3/4/5):

    ImageIntent semantics
        ↓  Flux2Compiler v1 (this module)
        ↓  CompiledFlux2Request
        ↓  transport serializer (gateway/flux2_transport.py → BFL wire fields)

Compilation is pure and deterministic: no LLM call, no randomness, no network.
The user never authors a provider prompt; the compiler assembles one from the
approved plan's meaning.

The compiled object contains MEANING (prompt prose, ordered semantic
references, protected traits, requested changes), never BFL wire fields such
as ``input_image`` / ``input_image_2``. Those belong to the transport adapter
(ADR 0040 decision 4; packet IL-03).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Sequence

FLUX2_COMPILER_VERSION = "flux2@1"

# Retrieval anchor for the vendored upstream guidance that this compiler's
# rules are pinned to (gateway/vendored/flux2-guidance/PROVENANCE.md).
COMPILER_GUIDANCE_REF = (
    "black-forest-labs/skills@a6f74cc70a85179ab74c578ed65dcf3d8dafca9e"
)
COMPILER_GUIDANCE_RETRIEVED_AT = "2026-08-19"

# Operation kinds the compiler understands (mirrors plan ALLOWED_OPERATIONS).
OPERATION_TXT2IMG = "txt2img"
OPERATION_IMG2IMG = "img2img"
VALID_OPERATIONS = frozenset({OPERATION_TXT2IMG, OPERATION_IMG2IMG})


class Flux2CompilerError(ValueError):
    """Raised when a plan cannot be compiled deterministically."""


@dataclass(frozen=True)
class CompiledReference:
    """A semantic, ordered reference binding.

    ``reference_id`` is the local/reference identity (e.g. the anchor job id or
    a character ref path); ``role`` is the semantic role the image plays in the
    composition; ``order`` is the deterministic slot/order (1-based) used both
    to number references in prose ("subject from image 1") and, downstream, to
    address the corresponding transport parameter.
    """

    reference_id: str
    role: str
    order: int
    name: str | None = None

    def to_dict(self) -> dict:
        return {
            "reference_id": self.reference_id,
            "role": self.role,
            "order": self.order,
            "name": self.name,
        }


@dataclass(frozen=True)
class CompiledFlux2Request:
    """Provider-neutral output of the flux2@1 compiler."""

    compiler_id: str = FLUX2_COMPILER_VERSION
    prompt: str = ""
    references: tuple[CompiledReference, ...] = ()
    operation: str = OPERATION_TXT2IMG
    seed: int | None = None
    width: int = 1024
    height: int = 1024
    quality_tier: str = "quality"
    protected_traits: tuple[str, ...] = ()
    requested_changes: tuple[str, ...] = ()
    # Deterministically untranslatable negative constraints kept as compiler
    # evidence rather than silently dropped (ADR 0040 decision 5).
    unresolved_negatives: tuple[str, ...] = ()
    guidance_ref: str = COMPILER_GUIDANCE_REF

    def to_dict(self) -> dict:
        return {
            "compiler_id": self.compiler_id,
            "prompt": self.prompt,
            "references": [r.to_dict() for r in self.references],
            "operation": self.operation,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "quality_tier": self.quality_tier,
            "protected_traits": list(self.protected_traits),
            "requested_changes": list(self.requested_changes),
            "unresolved_negatives": list(self.unresolved_negatives),
            "guidance_ref": self.guidance_ref,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


# ---------------------------------------------------------------------------
# Deterministic negative → positive translation
# ---------------------------------------------------------------------------
# Pinned to the vendored "negative-prompt-alternatives" quick-reference card
# and core principle 1 (FLUX has no negative prompts; describe what you want).
# This is a curated, deterministic catalog — not a home-grown encyclopedia.

_NEGATIVE_KEYWORDS: dict[str, str] = {
    "no people": "empty, solitary, deserted",
    "no crowds": "quiet, peaceful, secluded",
    "no background people": "an isolated subject, clean background, solo figure",
    "no makeup": "natural skin, bare face, fresh-faced",
    "no blemishes": "clear skin, smooth complexion, healthy glow",
    "no wrinkles": "youthful skin, smooth features",
    "no glasses": "visible eyes, unobstructed gaze, clear eye contact",
    "no hat": "bare head, visible hair",
    "no jewelry": "minimal accessories, understated",
    "no color": "monochrome, black and white, grayscale",
    "not colorful": "muted tones, subdued palette, desaturated",
    "no bright colors": "neutral tones, earth tones, soft pastels",
    "no text": "clean surfaces, unmarked, text-free",
    "no watermark": "pristine image, clean composition",
    "no logos": "unbranded, plain surfaces",
    "not modern": "traditional, classical, vintage",
    "no cgi": "photorealistic, authentic, natural, organic",
    "not cartoonish": "realistic, lifelike, naturalistic",
    "no blur": "sharp focus, crisp details, tack-sharp",
    "no noise": "clean image, smooth gradients, low ISO",
    "no artifacts": "pristine quality, clean render, flawless",
    "no cars": "a pedestrian area, car-free zone, walking street",
    "no buildings": "open landscape, natural scenery, wilderness",
    "no furniture": "empty room, bare space, minimalist interior",
    "no rain": "clear sky, dry weather, sunny day",
    "no clouds": "clear blue sky, cloudless, perfect visibility",
    "not dark": "well-lit, bright, daylight, illuminated",
    "no distractions": "clean composition, focused framing, minimal elements",
    "nothing in background": "solid background, isolated subject, clean backdrop",
    "no clutter": "organized, tidy, minimal, streamlined",
    "no waxy skin": "natural skin texture, visible pores, realistic variation",
    "no extra fingers": "anatomically correct hands with five natural fingers",
}


def _detect_negative(normalized_clause: str) -> str | None:
    """Return the positive replacement for a negative clause, if any.

    Matches on longest-key-substring so "no background people" wins over the
    shorter "no people". Purely deterministic.
    """
    best_key: str | None = None
    best_len = 0
    for key in _NEGATIVE_KEYWORDS:
        if key in normalized_clause and len(key) > best_len:
            best_key = key
            best_len = len(key)
    if best_key is None:
        return None
    return _NEGATIVE_KEYWORDS[best_key]


def translate_negative_prompt(
    negative_prompt: str | None,
) -> tuple[list[str], list[str]]:
    """Translate legacy negative prompt into positive clauses.

    Returns ``(positive_clauses, unresolved)``. Every source clause is either
    replaced with a positive description (per the pinned upstream rules) or
    preserved verbatim in ``unresolved`` as compiler evidence — never silently
    discarded (ADR 0040 decision 5).
    """
    if not negative_prompt or not negative_prompt.strip():
        return [], []
    positive: list[str] = []
    unresolved: list[str] = []
    for raw in re.split(r"[,;]\s*", negative_prompt):
        clause = raw.strip()
        if not clause:
            continue
        # Strip "no"/"without"/"avoid" prefixes so keyword matching works on
        # the object of the negation ("blurry" vs "no blur").
        normalized = clause.lower()
        replacement = _detect_negative(normalized)
        if replacement is not None:
            positive.append(replacement)
        else:
            unresolved.append(clause)
    return positive, unresolved


# ---------------------------------------------------------------------------
# Reference-in-prose role fragments (added deterministically)
# ---------------------------------------------------------------------------
_ROLE_FRAGMENTS: dict[str, str] = {
    "subject": "the subject",
    "identity": "the person",
    "person": "the person",
    "face": "the face",
    "body": "the body",
    "outfit": "the outfit",
    "clothing": "the clothing",
    "location": "the environment",
    "environment": "the environment",
    "pose": "the pose",
    "expression": "the expression",
    "style": "the style",
    "lighting": "the lighting",
    "object": "the object",
    "anchor": "the original image",
}


def _reference_sentence(references: Sequence[CompiledReference]) -> str:
    """Deterministic prose sentence referencing images by slot number."""
    ordered = sorted(references, key=lambda r: r.order)
    fragments = []
    for ref in ordered:
        fragment = _ROLE_FRAGMENTS.get(
            ref.role, "the subject" if ref.role == "subject" else "the content"
        )
        if ref.role == "anchor":
            fragment = f"the original image (image {ref.order})"
        else:
            fragment = f"{fragment} from image {ref.order}"
        fragments.append(fragment)
    return "Recompose using " + ", and ".join(fragments) + "."


def _change_sentence(requested_changes: Sequence[str]) -> str | None:
    if not requested_changes:
        return None
    joined = "; ".join(str(c).strip() for c in requested_changes if str(c).strip())
    if not joined:
        return None
    return f"Apply the following changes: {joined}."


def _preservation_sentence(
    protected_traits: Sequence[str], *, is_edit: bool
) -> str:
    """Deterministic preservation language (explicit, not a reroll).

    For an edit we always keep the subject stable even when the caller supplied
    no protected traits, so an edit compiles into change + preservation rather
    than silently degrading into a reroll (packet IL-03).
    """
    if protected_traits:
        traits = ", ".join(str(t).strip() for t in protected_traits if str(t).strip())
        return (
            f"While keeping {traits} exactly the same, maintaining exact likeness "
            "and the subject's identity, pose, clothing, and expression."
        )
    if is_edit:
        return (
            "Keep the subject's identity, pose, clothing, and expression exactly "
            "the same; maintain exact likeness and full fidelity to the reference."
        )
    return ""


def compile_flux2_request(
    prompt_text: str,
    *,
    references: Sequence[CompiledReference] = (),
    operation: str = OPERATION_TXT2IMG,
    seed: int | None = None,
    width: int = 1024,
    height: int = 1024,
    quality_tier: str = "quality",
    protected_traits: Sequence[str] = (),
    requested_changes: Sequence[str] = (),
    negative_prompt: str | None = None,
) -> CompiledFlux2Request:
    """Compile plan semantics into a deterministic flux2@1 request.

    The user's authored prose is preserved verbatim and front-loaded (subject
    first), per the pinned guidance that FLUX prioritizes earlier text. Ordered
    references, requested changes, preservation language, and positive negative
    replacements are appended deterministically. No LLM, no randomness.
    """
    if not prompt_text or not prompt_text.strip():
        raise Flux2CompilerError("compile_flux2_request requires non-empty prompt_text")
    if operation not in VALID_OPERATIONS:
        raise Flux2CompilerError(
            f"compile_flux2_request: operation {operation!r} not in "
            f"{sorted(VALID_OPERATIONS)}"
        )
    if width < 1 or height < 1:
        raise Flux2CompilerError(
            f"compile_flux2_request: invalid dimensions {width}x{height}"
        )

    base = prompt_text.strip()
    sentences = [base]

    positive_negatives, unresolved = translate_negative_prompt(negative_prompt)

    is_edit = operation == OPERATION_IMG2IMG
    ordered_refs = tuple(sorted(references, key=lambda r: r.order))

    if is_edit:
        change = _change_sentence(requested_changes)
        preserve = _preservation_sentence(protected_traits, is_edit=True)
        if change:
            sentences.append(change)
        if preserve:
            sentences.append(preserve)
    elif protected_traits:
        # A txt2img protected identity: keep likeness deterministic too.
        preserve = _preservation_sentence(protected_traits, is_edit=False)
        if preserve:
            sentences.append(preserve)

    if ordered_refs:
        sentences.append(_reference_sentence(ordered_refs))
    if positive_negatives:
        sentences.append(
            "Depict " + ", ".join(positive_negatives) + "."
        )

    compiled = CompiledFlux2Request(
        prompt=" ".join(sentences),
        references=ordered_refs,
        operation=operation,
        seed=seed,
        width=width,
        height=height,
        quality_tier=quality_tier,
        protected_traits=tuple(str(t).strip() for t in protected_traits if str(t).strip()),
        requested_changes=tuple(
            str(c).strip() for c in requested_changes if str(c).strip()
        ),
        unresolved_negatives=tuple(unresolved),
        guidance_ref=COMPILER_GUIDANCE_REF,
    )
    return compiled
