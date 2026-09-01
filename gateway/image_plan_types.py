"""Kitty ImagePlan types — plan type definitions and builder for the
bounded plan → renderer boundary.

Adapted from GenEvolve's ``GenEvolveResult`` and ``_finalize_answer``
(``genevolve/agent.py:150-171, 357-391``).  Kitty's version is local-first:
references are validated local character IDs, guidance is curated Markdown,
and dispatch always goes through the existing ``image_runner.run()`` lifecycle.

The plan type is a validated, serialisable preview that the user can inspect
and approve before generation begins — it never calls a renderer on its own.

Pointers:
  - plan type (this module) vs plan store (image_plan_store): the type defines
    the shape and validation; the store persists approved plans under stable IDs.
  - ``ImageIntent`` is provider-neutral; the renderer receives the refined prompt
    + resolved references separately — the plan type never embeds renderer args.
  - Content-lane defaults to SAFE (ADR 0040 #8) so callers that don't opt in are
    never private; the builder deliberately does not derive a lane from prompt text.
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
    """Stable character slot in a scene with optional spatial placement."""

    slot_id: str
    character_id: str
    display_name: str | None = None
    position: str | None = None
    depth_order: int | None = None


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize v1 without adding null placement keys to legacy cast slots."""
        payload = asdict(self)
        payload["cast"] = []
        for slot in self.cast:
            item: dict[str, Any] = {
                "slot_id": slot.slot_id,
                "character_id": slot.character_id,
                "display_name": slot.display_name,
            }
            if slot.position is not None:
                item["position"] = slot.position
            if slot.depth_order is not None:
                item["depth_order"] = slot.depth_order
            payload["cast"].append(item)
        return payload


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
        d["intent"] = self.intent.to_dict() if self.intent is not None else None
        return d


class ImagePlanError(ValueError):
    """Raised when a plan cannot be built safely (e.g. missing character)."""


def build_image_plan(
    prompt: str,
    *,
    character_id: str | None = None,
    cast: list[CastSlot] | None = None,
    reference_bindings: list[ReferenceBinding] | None = None,
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
    """Build a validated provider-neutral plan from user inputs.

    ``character_id`` remains the backward-compatible single-character input.
    ``cast`` is the multi-character path: each stable slot resolves a durable
    Character, and every reference binding is checked against that slot's
    Character before the plan can be approved or persisted.
    """
    import math

    from gateway import image_characters as ic
    from gateway.image_guidance_bank import available_guidance_tags
    from gateway.image_policy import ContentLane

    if operation not in {"txt2img", "img2img"}:
        raise ImagePlanError(
            f"unknown operation {operation!r}; must be 'txt2img' or 'img2img'"
        )
    if character_id and cast is not None:
        raise ImagePlanError("use character_id or cast, not both")

    lane = ContentLane.SAFE.value
    if content_lane is not None:
        text = str(content_lane).strip().lower()
        if text not in {candidate.value for candidate in ContentLane}:
            raise ImagePlanError(
                f"unknown content_lane {content_lane!r}; must be one of "
                f"{sorted(candidate.value for candidate in ContentLane)}"
            )
        lane = text

    requested_cast: list[CastSlot]
    if cast is not None:
        requested_cast = list(cast)
    elif character_id:
        requested_cast = [CastSlot(slot_id="subject_1", character_id=character_id)]
    else:
        requested_cast = []

    resolved_cast: list[CastSlot] = []
    characters_by_slot: dict[str, Any] = {}
    refs_by_slot: dict[str, dict[str, Any]] = {}
    seen_slots: set[str] = set()
    for slot in requested_cast:
        if not isinstance(slot, CastSlot):
            raise ImagePlanError("cast entries must be CastSlot values")
        slot_id = str(slot.slot_id).strip()
        cast_character_id = str(slot.character_id).strip()
        if not slot_id or not cast_character_id:
            raise ImagePlanError("cast slot_id and character_id must be non-empty")
        if slot_id in seen_slots:
            raise ImagePlanError(f"cast repeats slot_id {slot_id!r}")
        if slot.position is not None and not str(slot.position).strip():
            raise ImagePlanError(f"cast slot {slot_id!r} position must not be blank")
        if slot.depth_order is not None and (
            isinstance(slot.depth_order, bool)
            or not isinstance(slot.depth_order, int)
            or slot.depth_order <= 0
        ):
            raise ImagePlanError(
                f"cast slot {slot_id!r} depth_order must be a positive integer"
            )
        try:
            character = ic.get_character(cast_character_id)
        except ic.CharacterError as exc:
            raise ImagePlanError(
                f"cannot resolve character {cast_character_id!r}: {exc}"
            ) from exc
        try:
            stored_refs = list(ic.list_character_refs(cast_character_id))
        except ic.CharacterError as exc:
            raise ImagePlanError(
                f"cannot resolve references for character {cast_character_id!r}: {exc}"
            ) from exc
        refs_by_slot[slot_id] = {
            ref.ref_id: ref
            for ref in stored_refs
            if not getattr(ref, "soft_deleted", False)
        }
        characters_by_slot[slot_id] = character
        resolved_cast.append(
            CastSlot(
                slot_id=slot_id,
                character_id=cast_character_id,
                display_name=slot.display_name or character.name,
                position=str(slot.position).strip() if slot.position is not None else None,
                depth_order=slot.depth_order,
            )
        )
        seen_slots.add(slot_id)

    resolved_bindings: list[ReferenceBinding] = []
    references: list[ReferenceProvenance] = []
    provenance_seen: set[str] = set()

    def add_binding(binding: ReferenceBinding) -> None:
        if binding.cast_slot not in characters_by_slot:
            raise ImagePlanError(
                f"reference {binding.reference_id!r} targets unknown cast slot {binding.cast_slot!r}"
            )
        if binding.role not in ALLOWED_REFERENCE_ROLES:
            raise ImagePlanError(
                f"reference {binding.reference_id!r} has unsupported role {binding.role!r}"
            )
        if binding.weight is not None and (
            isinstance(binding.weight, bool)
            or not isinstance(binding.weight, (int, float))
            or not math.isfinite(float(binding.weight))
            or not 0.0 < float(binding.weight) <= 1.0
        ):
            raise ImagePlanError(
                f"reference {binding.reference_id!r} weight must be a finite value in (0, 1]"
            )
        slot_refs = refs_by_slot[binding.cast_slot]
        stored_ref = slot_refs.get(binding.reference_id)
        if stored_ref is None:
            actual_owner = next(
                (
                    characters_by_slot[slot_id].character_id
                    for slot_id, refs in refs_by_slot.items()
                    if binding.reference_id in refs
                ),
                None,
            )
            expected_owner = characters_by_slot[binding.cast_slot].character_id
            if actual_owner is not None:
                raise ImagePlanError(
                    f"reference {binding.reference_id!r} belongs to character {actual_owner!r}; "
                    f"cannot bind it to {binding.cast_slot!r} ({expected_owner!r})"
                )
            raise ImagePlanError(
                f"reference {binding.reference_id!r} is not stored for cast slot "
                f"{binding.cast_slot!r}"
            )
        resolved_bindings.append(
            ReferenceBinding(
                reference_id=binding.reference_id,
                role=binding.role,
                cast_slot=binding.cast_slot,
                weight=float(binding.weight) if binding.weight is not None else None,
            )
        )
        if binding.reference_id not in provenance_seen:
            character = characters_by_slot[binding.cast_slot]
            references.append(
                ReferenceProvenance(
                    character_id=character.character_id,
                    name=character.name,
                    path=stored_ref.storage_path,
                    reason=binding.role,
                    reference_id=stored_ref.ref_id,
                )
            )
            provenance_seen.add(binding.reference_id)

    if reference_bindings is not None:
        for binding in reference_bindings:
            if not isinstance(binding, ReferenceBinding):
                raise ImagePlanError("reference_bindings entries must be ReferenceBinding values")
            add_binding(binding)
    else:
        for slot in resolved_cast:
            primary = _primary_character_ref(characters_by_slot[slot.slot_id])
            if primary is None:
                raise ImagePlanError(
                    f"character {slot.character_id!r} has no reference image"
                )
            add_binding(
                ReferenceBinding(
                    reference_id=primary.ref_id,
                    role="identity",
                    cast_slot=slot.slot_id,
                )
            )

    if resolved_cast:
        bound_slots = {binding.cast_slot for binding in resolved_bindings}
        unbound = [slot.slot_id for slot in resolved_cast if slot.slot_id not in bound_slots]
        if unbound:
            raise ImagePlanError(
                f"every cast slot requires at least one bound reference; missing {unbound}"
            )

    known_tags = set(available_guidance_tags())
    resolved_tags: list[str] = []
    for tag in (guidance_tags or []):
        if tag not in known_tags:
            raise ImagePlanError(
                f"unknown guidance tag {tag!r}; available: "
                f"{', '.join(sorted(known_tags))}"
            )
        resolved_tags.append(tag)

    contexts = [
        (slot.display_name or characters_by_slot[slot.slot_id].name, characters_by_slot[slot.slot_id].description)
        for slot in resolved_cast
    ]
    refined = _refine_prompt(
        prompt.strip(),
        character_contexts=contexts,
        guidance_tags=resolved_tags,
    )

    intent = ImageIntent(
        operation=operation,
        cast=resolved_cast,
        references=resolved_bindings,
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

    legacy_character_id = resolved_cast[0].character_id if len(resolved_cast) == 1 else None
    legacy_ref_path = references[0].path if len(resolved_cast) == 1 and references else None
    return ImagePlan(
        original_prompt=prompt.strip(),
        refined_prompt=refined,
        character_id=legacy_character_id,
        character_ref_path=legacy_ref_path,
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
    character_contexts: list[tuple[str, str | None]] | None = None,
    guidance_tags: list[str] | None = None,
) -> str:
    """Build a refined prompt by appending character context and guidance.

    The original prompt is always preserved verbatim.  Character context and
    guidance are appended as separate sentences so the renderer can parse them
    independently — never modify the user's text.
    """
    from gateway.image_guidance_bank import get_guidance

    parts: list[str] = [prompt]

    contexts = character_contexts
    if contexts is None:
        contexts = [(character_name, character_desc)] if character_name else []
    for name, description in contexts:
        context = f"Subject: {name}."
        if description:
            context += f" {description}"
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
