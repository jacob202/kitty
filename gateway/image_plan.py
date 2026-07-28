"""Kitty ImagePlan — bounded plan → renderer boundary.

Adapted from GenEvolve's ``GenEvolveResult`` and ``_finalize_answer``
(``genevolve/agent.py:150-171, 357-391``).  Kitty's version is local-first:
references are validated local character IDs, guidance is curated Markdown,
and dispatch always goes through the existing ``image_runner.run()`` lifecycle.

The plan is a validated, serialisable preview that the user can inspect
and approve before generation begins — it never calls a renderer on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class ReferenceProvenance:
    """Why a specific local reference was selected for this plan."""

    character_id: str
    name: str
    path: str  # validated local file path
    reason: str  # e.g. "primary character", "user selected"


@dataclass
class ImagePlan:
    """A validated, user-approvable image-generation plan.

    Produced by the plan endpoint and submitted to the generate endpoint.
    The renderer receives the refined prompt + resolved references; the
    plan metadata is attached to the image job for provenance.
    """

    original_prompt: str
    refined_prompt: str
    character_id: str | None = None
    character_ref_path: str | None = None
    recipe_id: str | None = None
    guidance_tags: list[str] = field(default_factory=list)
    references: list[ReferenceProvenance] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["references"] = [asdict(r) for r in self.references]
        return d


class ImagePlanError(ValueError):
    """Raised when a plan cannot be built safely (e.g. missing character)."""


def build_image_plan(
    prompt: str,
    *,
    character_id: str | None = None,
    recipe_id: str | None = None,
    guidance_tags: list[str] | None = None,
) -> ImagePlan:
    """Build a validated plan from user inputs.

    Resolves *character_id* through the character store and validates
    *guidance_tags* against the guidance bank.  Returns an ``ImagePlan``
    ready for user preview.

    Raises ``ImagePlanError`` if a referenced resource cannot be resolved.
    """
    from gateway import image_characters as ic
    from gateway.image_guidance import available_guidance_tags

    references: list[ReferenceProvenance] = []
    resolved_character_path: str | None = None

    if character_id:
        try:
            char = ic.get_character(character_id)
        except ic.CharacterError as exc:
            raise ImagePlanError(
                f"cannot resolve character {character_id!r}: {exc}"
            ) from exc

        ref_path = _primary_character_ref_path(char)
        if ref_path is None:
            raise ImagePlanError(
                f"character {character_id!r} has no reference image"
            )
        resolved_character_path = ref_path
        references.append(
            ReferenceProvenance(
                character_id=char.character_id,
                name=char.name,
                path=ref_path,
                reason="primary character" if character_id else "user selected",
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

    # TODO: in a future phase, refine the prompt with character context
    # and selected guidance.  For now, the refined prompt is the original.
    refined = prompt.strip()

    return ImagePlan(
        original_prompt=prompt.strip(),
        refined_prompt=refined,
        character_id=character_id,
        character_ref_path=resolved_character_path,
        recipe_id=recipe_id,
        guidance_tags=resolved_tags,
        references=references,
    )


def _primary_character_ref_path(char: Any) -> str | None:
    """Return the local path of the character's primary reference image."""
    from gateway import image_characters as ic

    try:
        refs = ic.list_character_refs(char.character_id)
    except ic.CharacterError:
        return None

    if not refs:
        return None

    # Prefer the primary reference, else the first non-soft-deleted reference.
    for ref in refs:
        if getattr(ref, "soft_deleted", False):
            continue
        if getattr(ref, "is_primary", False):
            return ref.storage_path
    for ref in refs:
        if getattr(ref, "soft_deleted", False):
            continue
        return ref.storage_path
    return None
