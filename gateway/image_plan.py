"""Kitty ImagePlan — bounded plan → renderer boundary.

Adapted from GenEvolve's ``GenEvolveResult`` and ``_finalize_answer``
(``genevolve/agent.py:150-171, 357-391``).  Kitty's version is local-first:
references are validated local character IDs, guidance is curated Markdown,
and dispatch always goes through the existing ``image_runner.run()`` lifecycle.

The plan is a validated, serialisable preview that the user can inspect
and approve before generation begins — it never calls a renderer on its own.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from gateway.image_policy import ContentLane

ALLOWED_REFERENCE_ROLES = frozenset(
    {
        "subject",
        "identity",
        "person",
        "face",
        "body",
        "outfit",
        "clothing",
        "location",
        "environment",
        "pose",
        "expression",
        "style",
        "lighting",
        "object",
        "anchor",
    }
)


@dataclass
class ReferenceProvenance:
    """Why a specific local reference was selected for this plan."""

    character_id: str
    name: str
    path: str  # validated local file path
    reason: str  # e.g. "primary character", "user selected"
    reference_id: str | None = None


@dataclass
class ReferenceBinding:
    """Typed reference assignment for character-bound generation."""

    reference_id: str
    role: str
    cast_slot: str
    weight: float | None = None


@dataclass
class CastSlot:
    """Stable character slot in a scene."""

    slot_id: str
    character_id: str
    display_name: str | None = None


@dataclass
class ImageIntent:
    """Provider-neutral intent contract layered onto existing plans."""

    intent_version: int = 1
    operation: str = "txt2img"
    cast: list[CastSlot] = field(default_factory=list)
    references: list[ReferenceBinding] = field(default_factory=list)
    scene: dict[str, Any] = field(default_factory=dict)
    target: dict[str, Any] = field(default_factory=dict)
    requested_changes: list[str] = field(default_factory=list)
    protected_traits: list[str] = field(default_factory=list)
    content_lane: str = ContentLane.SAFE.value
    consent_basis: str | None = None
    adult_confirmed: bool = False
    privacy_required: bool = False
    quality_request: dict[str, Any] = field(default_factory=dict)
    budget_request: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImagePlan:
    """A validated, user-approvable image-generation plan.

    Produced by the plan endpoint and submitted to the generate endpoint.
    The renderer receives the refined prompt + resolved references; the
    plan metadata is attached to the image job for provenance.

    Content-lane fields (ADR 0040 #8) default to the safe lane so a caller
    that does not opt in is never private; the plan builder deliberately does
    not derive a lane or consent from prompt text.
    """

    original_prompt: str
    refined_prompt: str
    character_id: str | None = None
    character_ref_path: str | None = None
    recipe_id: str | None = None
    guidance_tags: list[str] = field(default_factory=list)
    references: list[ReferenceProvenance] = field(default_factory=list)
    intent: ImageIntent | None = None
    content_lane: str = ContentLane.SAFE.value
    consent_basis: str | None = None
    adult_confirmed: bool = False
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["references"] = [asdict(r) for r in self.references]
        d["intent"] = asdict(self.intent) if self.intent is not None else None
        return d


class ImagePlanError(ValueError):
    """Raised when a plan cannot be built safely (e.g. missing character)."""


def build_image_plan(
    prompt: str,
    *,
    character_id: str | None = None,
    recipe_id: str | None = None,
    guidance_tags: list[str] | None = None,
    content_lane: str | None = None,
    consent_basis: str | None = None,
    adult_confirmed: bool = False,
    operation: str = "txt2img",
    scene: dict[str, Any] | None = None,
    target: dict[str, Any] | None = None,
    requested_changes: list[str] | None = None,
    protected_traits: list[str] | None = None,
    privacy_required: bool | None = None,
    quality_request: dict[str, Any] | None = None,
    budget_request: dict[str, Any] | None = None,
) -> ImagePlan:
    """Build a validated plan from user inputs.

    Resolves *character_id* through the character store and validates
    *guidance_tags* against the guidance bank.  Returns an ``ImagePlan``
    ready for user preview.

    *content_lane*/*consent_basis*/*adult_confirmed* are carried onto the plan
    only as declared trusted metadata — never derived from *prompt* text.
    *content_lane* defaults to ``safe``; anything outside {safe, private_adult}
    is a hard ``ImagePlanError`` (fail closed rather than silently degraded).

    Raises ``ImagePlanError`` if a referenced resource cannot be resolved.
    """
    from gateway import image_characters as ic
    from gateway.image_guidance import available_guidance_tags
    from gateway.image_policy import ContentLane

    if operation not in {"txt2img", "img2img"}:
        raise ImagePlanError(
            f"unknown operation {operation!r}; must be 'txt2img' or 'img2img'"
        )

    lane = ContentLane.SAFE.value
    if content_lane is not None:
        text = str(content_lane).strip().lower()
        if text not in {lane.value for lane in ContentLane}:
            raise ImagePlanError(
                f"unknown content_lane {content_lane!r}; must be one of "
                f"{sorted(lane.value for lane in ContentLane)}"
            )
        lane = text

    references: list[ReferenceProvenance] = []
    resolved_character_path: str | None = None

    char = None
    if character_id:
        try:
            char = ic.get_character(character_id)
        except ic.CharacterError as exc:
            raise ImagePlanError(
                f"cannot resolve character {character_id!r}: {exc}"
            ) from exc

        ref = _primary_character_ref(char)
        if ref is None:
            raise ImagePlanError(
                f"character {character_id!r} has no reference image"
            )
        resolved_character_path = ref.storage_path
        references.append(
            ReferenceProvenance(
                character_id=char.character_id,
                name=char.name,
                path=ref.storage_path,
                reason="primary character" if character_id else "user selected",
                reference_id=ref.ref_id,
            )
        )

    # Validate guidance tags against the known set.
    known_tags = set(available_guidance_tags())
    resolved_tags: list[str] = []
    for tag in (guidance_tags or []):
        if tag not in known_tags:
            raise ImagePlanError(
                f"unknown guidance tag {tag!r}; available: "
                f"{', '.join(sorted(known_tags))}"
            )
        resolved_tags.append(tag)

    # Build a refined prompt from character context and guidance tags.
    char_name = getattr(char, "name", None) if char else None
    char_desc = getattr(char, "description", None) if char else None
    refined = _refine_prompt(
        prompt.strip(),
        character_name=char_name,
        character_desc=char_desc,
        guidance_tags=resolved_tags,
    )

    cast: list[CastSlot] = []
    typed_references: list[ReferenceBinding] = []
    if char is not None and references:
        cast.append(
            CastSlot(
                slot_id="subject_1",
                character_id=char.character_id,
                display_name=char.name,
            )
        )
        ref_id = references[0].reference_id
        if ref_id is not None:
            typed_references.append(
                ReferenceBinding(
                    reference_id=ref_id,
                    role="identity",
                    cast_slot="subject_1",
                )
            )

    intent = ImageIntent(
        operation=operation,
        cast=cast,
        references=typed_references,
        scene=dict(scene or {}),
        target=dict(target or {}),
        requested_changes=list(requested_changes or []),
        protected_traits=list(protected_traits or []),
        content_lane=lane,
        consent_basis=consent_basis,
        adult_confirmed=bool(adult_confirmed),
        privacy_required=(
            lane == ContentLane.PRIVATE_ADULT.value
            if privacy_required is None
            else bool(privacy_required)
        ),
        quality_request=dict(quality_request or {}),
        budget_request=dict(budget_request or {}),
    )

    return ImagePlan(
        original_prompt=prompt.strip(),
        refined_prompt=refined,
        character_id=character_id,
        character_ref_path=resolved_character_path,
        recipe_id=recipe_id,
        guidance_tags=resolved_tags,
        references=references,
        intent=intent,
        content_lane=lane,
        consent_basis=consent_basis,
        adult_confirmed=bool(adult_confirmed),
    )


def _primary_character_ref(char: Any) -> Any | None:
    """Return the character's primary stored reference record."""
    from gateway import image_characters as ic

    try:
        refs = ic.list_character_refs(char.character_id)
    except ic.CharacterError:
        return None

    for ref in refs:
        if getattr(ref, "soft_deleted", False):
            continue
        if getattr(ref, "is_primary", False):
            return ref
    for ref in refs:
        if not getattr(ref, "soft_deleted", False):
            return ref
    return None


def _primary_character_ref_path(char: Any) -> str | None:
    """Backward-compatible path projection of the primary reference."""
    ref = _primary_character_ref(char)
    return ref.storage_path if ref is not None else None


def _refine_prompt(
    prompt: str,
    *,
    character_name: str | None = None,
    character_desc: str | None = None,
    guidance_tags: list[str] | None = None,
) -> str:
    """Build a refined prompt by appending character context and guidance.

    The original prompt is always preserved verbatim.  Character context and
    guidance are appended as separate sentences so the renderer can parse them
    independently — never modify the user's text.
    """
    from gateway.image_guidance import get_guidance

    parts: list[str] = [prompt]

    if character_name:
        context = f"Subject: {character_name}."
        if character_desc:
            context += f" {character_desc}"
        parts.append(context)

    for tag in (guidance_tags or []):
        guidance = get_guidance(tag)
        if guidance is None:
            continue
        instructions = _extract_guidance_instructions(guidance)
        if instructions:
            parts.append(instructions)

    return " ".join(parts)


def _extract_guidance_instructions(guidance_md: str) -> str:
    """Pull out the actionable prompt-writing advice from a guidance file.

    Skips the renderer/model metadata header, section headings, and
    the Source/Version footer. Returns only the bullet-list
    instructions as a single sentence block.
    """
    lines: list[str] = []
    for line in guidance_md.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("**Renderer:**") or stripped.startswith("**Model:**"):
            continue
        if stripped.startswith("#") or stripped.startswith("---"):
            continue
        if stripped.startswith("Version:") or stripped.startswith("Source:"):
            continue
        if stripped.startswith("- "):
            instruction = stripped[2:].strip()
            lines.append(instruction)
    if not lines:
        return ""
    return "Guidance: " + ". ".join(lines[:6]) + "."
