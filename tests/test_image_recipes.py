"""Tests for image_recipes — recipe registry and auto routing."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from gateway import db
from gateway.image_recipes import (
    DEFAULT_RECIPES,
    RecipeError,
    auto_route,
    get_recipe,
    list_recipes,
    seed_default_recipes,
    set_recipe_available,
)


@pytest.fixture(autouse=True)
def override_db(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "test_kitty.db"
    monkeypatch.setattr("gateway.image_recipes.KITTY_DB_FILE", db_path)

    def _test_connect(db_file=db_path):
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    monkeypatch.setattr("gateway.db.connect", _test_connect)

    # Run the REAL migrations. This fixture used to hand-write image_jobs and
    # image_recipes, then mark 023-026 applied so _ensure_db() was a no-op — which
    # left image_characters absent while claiming 024 had run. Any later migration
    # touching that table then failed against a database the fixture said was up
    # to date. Same class of hole as issue #580: a fixture asserting a schema the
    # migrations do not produce.
    db.migrate(db_file=db_path)
    return db_path


class TestRecipeRegistry:
    def test_seed_defaults(self, override_db):
        count = seed_default_recipes()
        assert count == len(DEFAULT_RECIPES)
        # Idempotent
        assert seed_default_recipes() == 0

    def test_list_recipes(self, override_db):
        seed_default_recipes()
        recipes = list_recipes()
        assert len(recipes) >= 2

    def test_seed_reconciles_missing_defaults_in_existing_registry(self, override_db):
        seed_default_recipes()
        with db.connect(override_db) as conn:
            conn.execute("DELETE FROM image_recipes WHERE recipe_id = ?", ("airforce_grok_imagine_2",))
            conn.commit()
        assert seed_default_recipes() == 1
        assert get_recipe("airforce_grok_imagine_2").provider == "airforce"

    def test_hosted_defaults_exist(self, override_db):
        seed_default_recipes()
        assert get_recipe("airforce_grok_imagine_2").provider == "airforce"
        fal = get_recipe("fal_flux_pulid")
        assert fal.provider == "fal"
        assert fal.supports_characters is True


    def test_openai_gpt_image_2_recipe_is_config_gated_and_edit_capable(self, override_db, monkeypatch):
        monkeypatch.setenv("KITTY_IMAGE_OPENAI_ENABLED", "1")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        seed_default_recipes()
        recipe = get_recipe("openai_gpt_image_2")
        assert recipe.provider == "openai"
        assert recipe.model_family == "gpt-image-2"
        assert recipe.supports_img2img is True
        assert recipe.supports_characters is True
        assert recipe.is_available is True

    def test_openai_recipe_stays_unavailable_without_key(self, override_db, monkeypatch):
        monkeypatch.setenv("KITTY_IMAGE_OPENAI_ENABLED", "1")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        seed_default_recipes()
        assert get_recipe("openai_gpt_image_2").is_available is False

    def test_list_available_only(self, override_db):
        seed_default_recipes()
        recipes = list_recipes(available_only=True)
        assert all(r.is_available for r in recipes)

    def test_get_recipe(self, override_db):
        seed_default_recipes()
        r = get_recipe("comfyui_sdxl_standard")
        assert r.display_name == "SDXL Photonic"
        assert r.supports_characters

    def test_get_missing(self, override_db):
        seed_default_recipes()
        with pytest.raises(RecipeError, match="not found"):
            get_recipe("nonexistent")

    def test_set_available(self, override_db):
        seed_default_recipes()
        r = set_recipe_available("comfyui_sdxl_standard", False)
        assert not r.is_available


class TestAutoRouting:
    def test_no_character_default(self, override_db):
        seed_default_recipes()
        decision = auto_route(has_character=False)
        assert decision.recipe_id
        assert decision.recipe is not None

    def test_character_routes_to_identity_recipe(self, override_db):
        seed_default_recipes()
        decision = auto_route(has_character=True, character_count=1)
        assert decision.recipe.supports_characters

    def test_identity_first_mode(self, override_db):
        seed_default_recipes()
        decision = auto_route(
            has_character=True, character_count=1, identity_mode="identity_first"
        )
        assert "likeness" in decision.reason.lower() or "identity" in decision.reason.lower()

    def test_preferred_recipe(self, override_db):
        seed_default_recipes()
        decision = auto_route(preferred_recipe="comfyui_sd15_standard")
        assert decision.recipe_id == "comfyui_sd15_standard"
        assert "user preference" in decision.reason.lower()

    def test_explicit_unavailable_recipe_fails_instead_of_rerouting(self, override_db):
        seed_default_recipes()
        set_recipe_available("openai_gpt_image_2", False)
        with pytest.raises(RecipeError, match="not available"):
            auto_route(preferred_recipe="openai_gpt_image_2")

    def test_fast_tier(self, override_db):
        seed_default_recipes()
        decision = auto_route(has_character=False, quality_tier="fast")
        assert decision.recipe.quality_tier == "fast"

    def test_hosted_recipe_seed_is_config_only_not_network_health(self, override_db, monkeypatch):
        import httpx

        monkeypatch.setenv("KITTY_IMAGE_AIRFORCE_ENABLED", "1")
        monkeypatch.setenv("AIRFORCE_API_KEY", "test-key")
        monkeypatch.setenv("KITTY_IMAGE_FAL_ENABLED", "1")
        monkeypatch.setenv("FAL_KEY", "test-key-id:test-secret")
        monkeypatch.setattr(
            httpx,
            "post",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("startup must not probe Airforce")),
        )
        monkeypatch.setattr(
            httpx,
            "get",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("startup must not probe fal")),
        )

        seed_default_recipes()

        assert get_recipe("airforce_grok_imagine_2").is_available is True
        assert get_recipe("fal_flux_pulid").is_available is True

    def test_enabled_airforce_wins_default_quality_route(self, override_db, monkeypatch):
        monkeypatch.setenv("KITTY_IMAGE_AIRFORCE_ENABLED", "1")
        monkeypatch.setenv("AIRFORCE_API_KEY", "test-key")
        seed_default_recipes()
        decision = auto_route(has_character=False, quality_tier="quality")
        assert decision.recipe_id == "airforce_grok_imagine_2"

    def test_enabled_fal_wins_character_route(self, override_db, monkeypatch):
        monkeypatch.setenv("KITTY_IMAGE_FAL_ENABLED", "1")
        monkeypatch.setenv("FAL_KEY", "test-key")
        seed_default_recipes()
        decision = auto_route(
            has_character=True,
            character_count=1,
            quality_tier="quality",
            identity_mode="identity_first",
        )
        assert decision.recipe_id == "fal_flux_pulid"



    def test_flux2_recipes_follow_runtime_paid_provider_readiness(self, override_db, monkeypatch):
        monkeypatch.delenv("KITTY_IMAGE_PAID_ENABLED", raising=False)
        monkeypatch.delenv("BFL_API_KEY", raising=False)
        seed_default_recipes()
        assert get_recipe("bfl_flux2_draft").is_available is False
        assert get_recipe("bfl_flux2_pro").is_available is False

        monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "1")
        monkeypatch.setenv("BFL_API_KEY", "test-key")
        seed_default_recipes()
        assert get_recipe("bfl_flux2_draft").is_available is True
        assert get_recipe("bfl_flux2_pro").is_available is True

    def test_flux2_defaults_advertise_bounded_two_character_capability(self, override_db):
        seed_default_recipes()
        draft = get_recipe("bfl_flux2_draft")
        pro = get_recipe("bfl_flux2_pro")
        for recipe in (draft, pro):
            assert recipe.supports_characters is True
            assert recipe.max_characters == 2

    def test_flux2_capability_reconciles_existing_seeded_rows(self, override_db):
        seed_default_recipes()
        with db.connect(override_db) as conn:
            conn.execute(
                "UPDATE image_recipes SET supports_characters = 0, max_characters = 0 "
                "WHERE recipe_id IN ('bfl_flux2_draft', 'bfl_flux2_pro')"
            )
            conn.commit()

        assert seed_default_recipes() == 0
        assert get_recipe("bfl_flux2_draft").max_characters == 2
        assert get_recipe("bfl_flux2_pro").supports_characters is True

    def test_preferred_single_character_recipe_rejected_for_two_characters(self, override_db):
        seed_default_recipes()
        with pytest.raises(RecipeError, match="supports 1 character.*requested 2"):
            auto_route(
                has_character=True,
                character_count=2,
                preferred_recipe="comfyui_sdxl_standard",
            )

    def test_identity_first_respects_max_characters(self, override_db, monkeypatch):
        monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "1")
        monkeypatch.setenv("BFL_API_KEY", "test-key")
        seed_default_recipes()
        decision = auto_route(
            has_character=True,
            character_count=2,
            identity_mode="identity_first",
        )
        assert decision.recipe is not None
        assert decision.recipe.supports_characters is True
        assert decision.recipe.max_characters >= 2
        assert decision.recipe.provider == "flux2"

    def test_auto_route_respects_live_provider_allowlist(self, override_db):
        seed_default_recipes()
        decision = auto_route(available_providers={"drawthings"})
        assert decision.recipe is not None
        assert decision.recipe.provider == "drawthings"

        with pytest.raises(RecipeError, match="provider.*not currently available"):
            auto_route(
                preferred_recipe="comfyui_sdxl_standard",
                available_providers={"drawthings"},
            )

    def test_no_available_recipes_raises(self, override_db):
        seed_default_recipes()
        recipes = list_recipes()
        for r in recipes:
            set_recipe_available(r.recipe_id, False)
        with pytest.raises(RecipeError, match="no image recipes"):
            auto_route()

    def test_no_character_recipe_raises(self, override_db):
        seed_default_recipes()
        # Disable character-supporting recipes
        for r in list_recipes():
            if r.supports_characters:
                set_recipe_available(r.recipe_id, False)
        with pytest.raises(RecipeError, match="no available recipe supports"):
            auto_route(has_character=True, character_count=1)
