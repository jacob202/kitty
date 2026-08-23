"""Role-aware, capability-aware reference selection for Image Lab dispatch.

The approved ``ImagePlan`` persists typed reference bindings (role +
cast_slot) so the renderer knows *why* each local reference was attached.
Dispatch historically forwarded every bound reference to the selected
provider regardless of whether that provider's recipe declares support for
the binding's semantic role.  That silently mis-uses or drops a reference a
provider cannot carry, which violates the Image Lab invariant that a missing
provider capability fails loudly instead of silently degrading a render.

This module is the role-aware ReferenceSelector.  It validates each binding's
role against the selected provider's declared capabilities, orders identity
references deterministically by cast depth, and fails closed when a required
capability is absent.

No import of any external selector: the mechanism is adapted from the
role/capability model already defined in ``gateway.image_plan``
(``ALLOWED_REFERENCE_ROLES``) and ``gateway.image_recipes`` (the
``supports_*_refs`` capability flags).  It stays a pure decision layer —
byte resolution and renderer dispatch remain in the existing route/runner
lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from gateway.image_plan import ALLOWED_REFERENCE_ROLES

# Roles that carry a subject's identity; these are mandatory for any character
# cast and are gated on the recipe's character support.
_IDENTITY_ROLES = frozenset({"subject", "identity", "person", "face", "body"})

# Semantic role -> recipe capability flag that must be declared for the role
# to be carried by a provider.  Roles not listed here are treated as
# identity-adjacent and gated on character support.
_ROLE_CAPABILITY_FLAG = {
    "pose": "supports_pose_refs",
    "outfit": "supports_outfit_refs",
    "clothing": "supports_outfit_refs",
    "object": "supports_object_refs",
    "location": "supports_location_refs",
    "environment": "supports_location_refs",
    "style": "supports_style_refs",
    "lighting": "supports_style_refs",
    "expression": "supports_style_refs",
    "anchor": "supports_img2img",
}


class ReferenceSelectorError(ValueError):
    """Base error for role-aware reference selection."""


class UnknownReferenceRoleError(ReferenceSelectorError):
    """A binding names a role outside ALLOWED_REFERENCE_ROLES."""


class ReferenceCapabilityError(ReferenceSelectorError):
    """The selected provider cannot carry a requested reference role.

    Raised instead of silently omitting or mis-using the reference.
    """


@dataclass(frozen=True)
class SelectedReference:
    """A binding the selected provider can truthfully carry, in render order."""

    reference_id: str
    role: str
    cast_slot: str | None = None
    weight: float | None = None
    depth_order: int | None = None
    character_id: str | None = None
    position: str | None = None


def _role_requirement(role: str) -> str:
    """Recipe capability flag required to carry ``role``.

    Identity-family roles require character support; roles with a dedicated
    capability flag require that flag; anything else is treated as
    identity-adjacent and gated on character support so an unrecognised role
    can never silently fall through to a capability-less render.
    """
    if role in _IDENTITY_ROLES:
        return "supports_characters"
    return _ROLE_CAPABILITY_FLAG.get(role, "supports_characters")


def required_capability_for_role(role: str) -> str:
    """Public capability lookup for a single binding role."""
    if role not in ALLOWED_REFERENCE_ROLES:
        raise UnknownReferenceRoleError(
            f"reference role {role!r} is not in ALLOWED_REFERENCE_ROLES: "
            f"{sorted(ALLOWED_REFERENCE_ROLES)}"
        )
    return _role_requirement(role)


def _capability_flags(recipe: Any) -> dict[str, bool]:
    """Read the declared capability flags off a recipe object.

    Accepts a ``gateway.image_recipes.Recipe`` or any object exposing the same
    ``supports_*`` boolean attributes; unknown/missing flags default to
    ``False`` so an undeclared capability fails closed.
    """
    flags: dict[str, bool] = {}
    for flag in _ROLE_CAPABILITY_FLAG.values():
        flags[flag] = bool(getattr(recipe, flag, False))
    flags["supports_characters"] = bool(
        getattr(recipe, "supports_characters", False)
    )
    flags["supports_img2img"] = bool(getattr(recipe, "supports_img2img", False))
    return flags


def validate_capability(
    bindings: Sequence[dict[str, Any]] | Sequence[SelectedReference],
    *,
    recipe: Any,
    operation: str = "txt2img",
) -> None:
    """Fail closed if the provider cannot carry a requested reference role.

    Raises :class:`UnknownReferenceRoleError` for a role outside
    ``ALLOWED_REFERENCE_ROLES`` and :class:`ReferenceCapabilityError` when the
    provider recipe does not declare the capability the role requires.
    """
    flags = _capability_flags(recipe)
    for binding in bindings:
        role = _role_of(binding)
        required = required_capability_for_role(role)
        if flags.get(required) is False:
            raise ReferenceCapabilityError(
                f"reference {_id_of(binding)!r} role={role!r} requires provider "
                f"capability {required!r}, which recipe "
                f"{getattr(recipe, 'recipe_id', '<unknown>')!r} does not declare; "
                f"refusing to silently drop or mis-use the reference"
            )


def select_references(
    bindings: Sequence[dict[str, Any]],
    cast: Sequence[dict[str, Any]],
    *,
    recipe: Any,
    operation: str = "txt2img",
) -> list[SelectedReference]:
    """Return the ordered, capability-validated references to dispatch.

    Identity-family references come first, ordered by their cast slot depth;
    remaining references keep their plan order.  Missing capabilities fail
    loudly via :func:`validate_capability` — never by silent omission.
    """
    if recipe is None:
        raise ReferenceSelectorError("select_references requires a resolved recipe")
    validate_capability(bindings, recipe=recipe, operation=operation)

    slot_by_id = {
        str(slot.get("slot_id")): slot
        for slot in cast
        if isinstance(slot, dict) and slot.get("slot_id")
    }
    decorated: list[tuple[int, int, SelectedReference]] = []
    for index, binding in enumerate(bindings):
        role = str(binding["role"])
        cast_slot = binding.get("cast_slot")
        slot = slot_by_id.get(str(cast_slot)) if cast_slot else None
        depth = int(slot.get("depth_order") or 0) if slot else 0
        ref = SelectedReference(
            reference_id=str(binding["reference_id"]),
            role=role,
            cast_slot=str(cast_slot) if cast_slot else None,
            weight=(
                float(binding["weight"])
                if binding.get("weight") is not None
                else None
            ),
            depth_order=depth if depth else None,
            character_id=(
                str(slot.get("character_id"))
                if slot and slot.get("character_id")
                else None
            ),
            position=(
                str(slot.get("position"))
                if slot and slot.get("position") is not None
                else None
            ),
        )
        # identity refs first, ordered by cast depth; optional refs keep plan order.
        # Within the same identity bucket, depth ascending; stable plan order breaks ties.
        decorated.append((0 if role in _IDENTITY_ROLES else 1, depth, index, ref))

    decorated.sort(key=lambda item: (item[0], item[1], item[2]))
    return [ref for _, _, _, ref in decorated]


def _role_of(binding: dict[str, Any] | SelectedReference) -> str:
    if isinstance(binding, SelectedReference):
        return binding.role
    role = binding.get("role")
    if not role:
        raise UnknownReferenceRoleError(
            f"reference binding {binding!r} has no 'role'; every plan reference "
            "must declare its semantic role"
        )
    return str(role)


def _id_of(binding: dict[str, Any] | SelectedReference) -> str | None:
    if isinstance(binding, SelectedReference):
        return binding.reference_id
    return binding.get("reference_id")
