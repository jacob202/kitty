"""Role-aware ReferenceSelector tests — fail-closed, capability-aware selection."""

from __future__ import annotations

import importlib
from dataclasses import dataclass

import pytest


def _module():
    return importlib.import_module("gateway.image_reference_selector")


def _recipe(**overrides):
    @dataclass
    class FakeRecipe:
        recipe_id: str = "fake"
        supports_characters: bool = False
        max_characters: int = 0
        supports_pose_refs: bool = False
        supports_outfit_refs: bool = False
        supports_object_refs: bool = False
        supports_location_refs: bool = False
        supports_style_refs: bool = False
        supports_img2img: bool = False

    return FakeRecipe(**overrides)


_CAST_TWO = [
    {"slot_id": "left_slot", "character_id": "char-a", "display_name": "A", "position": "left", "depth_order": 1},
    {"slot_id": "right_slot", "character_id": "char-b", "display_name": "B", "position": "right", "depth_order": 2},
]

_BINDING_TWO = [
    {
        "reference_id": "ref-a",
        "role": "identity",
        "cast_slot": "left_slot",
        "weight": 1.0,
    },
    {
        "reference_id": "ref-b",
        "role": "identity",
        "cast_slot": "right_slot",
        "weight": 1.0,
    },
]


def test_two_identity_bindings_pass_with_character_capability():
    sel = _module()
    recipe = _recipe(supports_characters=True, max_characters=2)
    selected = sel.select_references(_BINDING_TWO, _CAST_TWO, recipe=recipe)
    assert [r.reference_id for r in selected] == ["ref-a", "ref-b"]
    assert selected[0].cast_slot == "left_slot"
    assert selected[0].position == "left"
    assert selected[0].depth_order == 1
    assert selected[1].position == "right"
    assert selected[1].depth_order == 2


def test_identity_binding_fails_closed_without_character_capability():
    sel = _module()
    recipe = _recipe(supports_characters=False)
    with pytest.raises(sel.ReferenceCapabilityError) as excinfo:
        sel.select_references(_BINDING_TWO, _CAST_TWO, recipe=recipe)
    assert "supports_characters" in str(excinfo.value)
    assert "ref-a" in str(excinfo.value)


def test_pose_binding_requires_pose_capability():
    sel = _module()
    binding = [
        {"reference_id": "pose-ref", "role": "pose", "cast_slot": "left_slot", "weight": 0.5}
    ]
    recipe = _recipe(supports_characters=True, max_characters=1, supports_pose_refs=False)
    with pytest.raises(sel.ReferenceCapabilityError) as excinfo:
        sel.select_references(binding, _CAST_TWO, recipe=recipe)
    assert "supports_pose_refs" in str(excinfo.value)
    assert "pose-ref" in str(excinfo.value)

    capable = _recipe(supports_characters=True, max_characters=1, supports_pose_refs=True)
    selected = sel.select_references(binding, _CAST_TWO, recipe=capable)
    assert [r.reference_id for r in selected] == ["pose-ref"]


def test_outfit_and_clothing_roles_use_outfit_capability():
    sel = _module()
    for role in ("outfit", "clothing"):
        binding = [{"reference_id": f"{role}-ref", "role": role, "cast_slot": None}]
        recipe = _recipe(supports_characters=True, max_characters=1, supports_outfit_refs=False)
        with pytest.raises(sel.ReferenceCapabilityError):
            sel.select_references(binding, [], recipe=recipe)
        capable = _recipe(supports_characters=True, max_characters=1, supports_outfit_refs=True)
        selected = sel.select_references(binding, [], recipe=capable)
        assert [r.reference_id for r in selected] == [f"{role}-ref"]


def test_object_location_style_roles_map_to_their_capability_flags():
    sel = _module()
    cases = {
        "object": "supports_object_refs",
        "location": "supports_location_refs",
        "environment": "supports_location_refs",
        "style": "supports_style_refs",
        "lighting": "supports_style_refs",
        "expression": "supports_style_refs",
    }
    for role, flag in cases.items():
        binding = [{"reference_id": f"{role}-ref", "role": role, "cast_slot": None}]
        recipe = _recipe(supports_characters=True, max_characters=1, **{flag: False})
        with pytest.raises(sel.ReferenceCapabilityError) as excinfo:
            sel.select_references(binding, [], recipe=recipe)
        assert flag in str(excinfo.value)
        capable = _recipe(supports_characters=True, max_characters=1, **{flag: True})
        assert sel.select_references(binding, [], recipe=capable)


def test_anchor_role_requires_img2img_capability():
    sel = _module()
    binding = [{"reference_id": "anchor-ref", "role": "anchor", "cast_slot": None}]
    recipe = _recipe(supports_characters=True, max_characters=1, supports_img2img=False)
    with pytest.raises(sel.ReferenceCapabilityError) as excinfo:
        sel.select_references(binding, [], recipe=recipe, operation="img2img")
    assert "supports_img2img" in str(excinfo.value)

    capable = _recipe(supports_characters=True, max_characters=1, supports_img2img=True)
    assert sel.select_references(binding, [], recipe=capable, operation="img2img")


def test_unknown_role_fails_loud():
    sel = _module()
    binding = [{"reference_id": "x", "role": "not_a_real_role", "cast_slot": None}]
    recipe = _recipe(supports_characters=True, max_characters=1)
    with pytest.raises(sel.UnknownReferenceRoleError):
        sel.select_references(binding, [], recipe=recipe)
    with pytest.raises(sel.UnknownReferenceRoleError):
        sel.required_capability_for_role("not_a_real_role")


def test_missing_role_field_fails_loud():
    sel = _module()
    binding = [{"reference_id": "x"}]
    recipe = _recipe(supports_characters=True, max_characters=1)
    with pytest.raises(sel.UnknownReferenceRoleError):
        sel.select_references(binding, [], recipe=recipe)


def test_identity_references_ordered_before_optional_references():
    sel = _module()
    recipe = _recipe(
        supports_characters=True,
        max_characters=2,
        supports_pose_refs=True,
        supports_style_refs=True,
    )
    bindings = [
        {"reference_id": "style-ref", "role": "style", "cast_slot": None},
        {"reference_id": "pose-ref", "role": "pose", "cast_slot": "left_slot"},
        {"reference_id": "ref-b", "role": "identity", "cast_slot": "right_slot"},
        {"reference_id": "ref-a", "role": "identity", "cast_slot": "left_slot"},
    ]
    selected = sel.select_references(bindings, _CAST_TWO, recipe=recipe)
    ids = [r.reference_id for r in selected]
    # identity refs first (depth 1 left then depth 2 right), then optional refs in plan order
    assert ids == ["ref-a", "ref-b", "style-ref", "pose-ref"]


def test_null_recipe_fails_loud():
    sel = _module()
    with pytest.raises(sel.ReferenceSelectorError):
        sel.select_references(_BINDING_TWO, _CAST_TWO, recipe=None)


def test_validate_capability_is_stable_against_recipe_dicts_and_objects():
    sel = _module()
    recipe = _recipe(supports_characters=True, max_characters=2)
    sel.validate_capability(_BINDING_TWO, recipe=recipe)

    class DictRecipe(dict):
        pass

    dict_recipe = DictRecipe(supports_characters=True)
    # dict attributes do not exist; must fail closed on missing capability flags
    with pytest.raises(sel.ReferenceCapabilityError):
        sel.validate_capability(_BINDING_TWO, recipe=dict_recipe)
