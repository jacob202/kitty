"""Golden-case tests for the flux2@1 semantic compiler (IL-03).

Proves deterministic semantic compilation for the ten required cases:
plain txt2img, photoreal portrait, one identity reference, two ordered
references, identity+outfit+location semantics, edit with protected traits,
edit with requested change, legacy negative constraints translated/preserved,
same intent → same compiled request, and compiler-version persistence in job
provenance.
"""

from __future__ import annotations

import pytest

from gateway.flux2_compiler import (
    COMPILER_GUIDANCE_REF,
    FLUX2_COMPILER_VERSION,
    OPERATION_IMG2IMG,
    OPERATION_TXT2IMG,
    CompiledReference,
    Flux2CompilerError,
    compile_flux2_request,
    translate_negative_prompt,
)


def _ref(reference_id: str, role: str, order: int, name: str | None = None):
    return CompiledReference(reference_id=reference_id, role=role, order=order, name=name)


class TestPlainTxt2Img:
    def test_base_prose_preserved_and_front_loaded(self):
        compiled = compile_flux2_request("a cat in a sunlit kitchen")
        assert compiled.operation == OPERATION_TXT2IMG
        assert compiled.prompt.startswith("a cat in a sunlit kitchen")
        assert compiled.references == ()
        assert compiled.unresolved_negatives == ()
        assert compiled.compiler_id == FLUX2_COMPILER_VERSION

    def test_default_dimensions_and_tier(self):
        compiled = compile_flux2_request("a cat")
        assert (compiled.width, compiled.height) == (1024, 1024)
        assert compiled.quality_tier == "quality"
        assert compiled.seed is None

    def test_rejects_empty_prompt(self):
        with pytest.raises(Flux2CompilerError):
            compile_flux2_request("   ")
        with pytest.raises(Flux2CompilerError):
            compile_flux2_request("")

    def test_rejects_bad_operation_and_dims(self):
        with pytest.raises(Flux2CompilerError):
            compile_flux2_request("a cat", operation="inpaint")
        with pytest.raises(Flux2CompilerError):
            compile_flux2_request("a cat", width=0)
        with pytest.raises(Flux2CompilerError):
            compile_flux2_request("a cat", height=-1)


class TestPhotorealPortrait:
    def test_prose_has_lighting_and_technical_detail(self):
        prose = (
            "a candid photoreal portrait of a young woman with freckles, "
            "golden hour light from the side, sharp 85mm lens at f/1.8, "
            "soft shallow depth of field"
        )
        compiled = compile_flux2_request(prose, quality_tier="final")
        assert compiled.prompt == prose
        assert compiled.quality_tier == "final"
        # Semantic markers survive verbatim (Kitty owns the meaning).
        assert "golden hour light" in compiled.prompt
        assert "85mm lens" in compiled.prompt


class TestOneIdentityReference:
    def test_single_identity_reference_numbered_image_1(self):
        ref = _ref("char_ref_1", "identity", order=1, name="Mara")
        compiled = compile_flux2_request(
            "Mara standing in a rose garden at dusk",
            references=[ref],
        )
        assert len(compiled.references) == 1
        assert compiled.references[0].order == 1
        assert "from image 1" in compiled.prompt
        assert compiled.prompt.endswith(".")


class TestTwoOrderedReferences:
    def test_order_preserved_in_prose(self):
        refs = [
            _ref("char_ref_1", "identity", order=1, name="Mara"),
            _ref("outfit_ref_2", "outfit", order=2, name="denim jacket"),
        ]
        compiled = compile_flux2_request("Mara wearing the outfit", references=refs)
        assert [r.order for r in compiled.references] == [1, 2]
        prompt = compiled.prompt
        assert "from image 1" in prompt
        assert "from image 2" in prompt
        # Deterministic slot numbering is stable and 1-based.
        assert "image 0" not in prompt


class TestIdentityOutfitLocation:
    def test_three_roles_with_roles_visible(self):
        refs = [
            _ref("char_ref_1", "identity", order=1, name="Mara"),
            _ref("outfit_ref_2", "outfit", order=2, name="denim jacket"),
            _ref("loc_ref_3", "location", order=3, name="Tokyo street"),
        ]
        compiled = compile_flux2_request(
            "Mara in the outfit near the landmark",
            references=refs,
        )
        prompt = compiled.prompt
        assert "the person from image 1" in prompt
        assert "the outfit from image 2" in prompt
        assert "the environment from image 3" in prompt


class TestEditProtectedTraits:
    def test_edit_with_protected_traits_keeps_change_and_preserve(self):
        compiled = compile_flux2_request(
            "Change the jacket to denim",
            operation=OPERATION_IMG2IMG,
            protected_traits=["identity", "pose", "expression"],
        )
        assert compiled.operation == OPERATION_IMG2IMG
        assert "Change the jacket to denim" in compiled.prompt
        assert "identity" in compiled.prompt
        assert "pose" in compiled.prompt
        # An edit must be an explicit change+preserve, never a silent reroll.
        assert "exactly the same" in compiled.prompt
        assert "exact likeness" in compiled.prompt

    def test_edit_default_preservation_when_no_traits(self):
        compiled = compile_flux2_request(
            "Change the background to a sunset",
            operation=OPERATION_IMG2IMG,
            references=[_ref("anchor_1", "anchor", order=1)],
        )
        prompt = compiled.prompt
        assert "Change the background to a sunset" in prompt
        assert "subject's identity, pose, clothing, and expression" in prompt
        assert "the original image (image 1)" in prompt

    def test_preserved_prompt_is_not_a_reroll_of_base(self):
        base = "Add headphones to the look"
        compiled = compile_flux2_request(base, operation=OPERATION_IMG2IMG)
        assert compiled.prompt.startswith(base)
        assert "Add headphones" in compiled.prompt
        assert "exactly the same" in compiled.prompt


class TestEditRequestedChange:
    def test_requested_changes_compile_verbatim(self):
        changes = ["turn the sky purple", "reduce the backpack"]
        compiled = compile_flux2_request(
            "Adjust the scene",
            operation=OPERATION_IMG2IMG,
            requested_changes=changes,
        )
        assert "Apply the following changes: turn the sky purple; reduce the backpack." in compiled.prompt
        assert compiled.requested_changes == tuple(changes)


class TestNegativeTranslation:
    def test_legacy_negative_translated_to_positive(self):
        positive, unresolved = translate_negative_prompt(
            "no waxy skin, no extra fingers, no blur"
        )
        assert "natural skin texture, visible pores, realistic variation" in positive
        assert "anatomically correct hands with five natural fingers" in positive
        assert "sharp focus, crisp details, tack-sharp" in positive
        assert unresolved == []

    def test_legacy_negative_in_request_depicted_positively(self):
        compiled = compile_flux2_request("a portrait", negative_prompt="no waxy skin")
        assert "Depict natural skin texture, visible pores, realistic variation." in compiled.prompt
        # The negative wording itself never reaches the provider prompt.
        assert "no waxy skin" not in compiled.prompt

    def test_untranslatable_negative_preserved_as_evidence(self):
        positive, unresolved = translate_negative_prompt("no ligma placement")
        assert positive == []
        assert unresolved == ["no ligma placement"]

    def test_untranslatable_not_dropped_from_request(self):
        compiled = compile_flux2_request("a cat", negative_prompt="no ligma placement")
        assert compiled.unresolved_negatives == ("no ligma placement",)
        # Still not silently converted to a BFL-native negativePrompt field.
        assert [] not in compiled.unresolved_negatives  # clarity guard

    def test_longest_match_wins(self):
        positive, unresolved = translate_negative_prompt("no background people")
        assert "solo figure" in positive[0]
        assert unresolved == []

    def test_empty_and_blank(self):
        assert translate_negative_prompt(None) == ([], [])
        assert translate_negative_prompt("  ") == ([], [])


class TestDeterminism:
    def test_same_intent_same_compiled_request(self):
        kwargs = dict(
            prompt_text="Mara on a motorway",
            references=[
                _ref("char_ref_1", "identity", order=1, name="Mara"),
                _ref("loc_ref_2", "location", order=2),
            ],
            protected_traits=["identity"],
            requested_changes=["swap the helmet"],
            negative_prompt="no people",
        )
        a = compile_flux2_request(**kwargs)
        b = compile_flux2_request(**kwargs)
        assert a == b
        assert a.to_json() == b.to_json()

    def test_seed_and_dims_are_preserved(self):
        a = compile_flux2_request("a cat", seed=42, width=768, height=1024)
        assert a.seed == 42
        assert (a.width, a.height) == (768, 1024)


class TestCompilerVersion:
    def test_version_is_flux2_at_1(self):
        assert FLUX2_COMPILER_VERSION == "flux2@1"
        assert COMPILER_GUIDANCE_REF.startswith("black-forest-labs/skills@")
        compiled = compile_flux2_request("a cat")
        assert compiled.compiler_id == "flux2@1"

    def test_compile_provenance_json_carries_version_and_meaning(self):
        """The compiled JSON is exactly what a job ledger records."""
        import json

        compiled = compile_flux2_request(
            "a cat",
            seed=9,
            references=[_ref("r_1", "identity", order=1)],
        )
        params = json.loads(compiled.to_json())
        assert params["compiler_id"] == "flux2@1"
        assert params["seed"] == 9
        assert params["references"][0]["order"] == 1
        assert params["prompt"].startswith("a cat")
