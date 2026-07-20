"""Tests for image_recipes — recipe registry and auto routing."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

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

    conn = _test_connect()
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS image_jobs (
            job_id TEXT PRIMARY KEY, provider TEXT NOT NULL, provider_job_id TEXT,
            operation TEXT NOT NULL, status TEXT NOT NULL, prompt TEXT, negative_prompt TEXT,
            seed INTEGER, model_id TEXT, preset_id TEXT, width INTEGER, height INTEGER,
            steps INTEGER, guidance REAL, sampler TEXT, scheduler TEXT,
            provider_params_json TEXT, workflow_template_id TEXT, workflow_hash TEXT,
            artifact_id TEXT, output_path TEXT, normalized_error TEXT,
            provider_diagnostics_json TEXT, parent_id TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, started_at TEXT, finished_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS image_recipes (
            recipe_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, description TEXT,
            provider TEXT NOT NULL, workflow_template_id TEXT, model_family TEXT,
            operation TEXT NOT NULL DEFAULT 'txt2img', quality_tier TEXT NOT NULL,
            expected_speed TEXT, default_width INTEGER DEFAULT 1024, default_height INTEGER DEFAULT 1024,
            max_width INTEGER DEFAULT 2048, max_height INTEGER DEFAULT 2048,
            supported_aspects_json TEXT, supports_img2img INTEGER NOT NULL DEFAULT 0,
            supports_characters INTEGER NOT NULL DEFAULT 0, max_characters INTEGER NOT NULL DEFAULT 0,
            supports_pose_refs INTEGER NOT NULL DEFAULT 0, supports_outfit_refs INTEGER NOT NULL DEFAULT 0,
            supports_object_refs INTEGER NOT NULL DEFAULT 0, supports_location_refs INTEGER NOT NULL DEFAULT 0,
            supports_style_refs INTEGER NOT NULL DEFAULT 0, supports_inpainting INTEGER NOT NULL DEFAULT 0,
            supports_variation INTEGER NOT NULL DEFAULT 0, supports_upscaling INTEGER NOT NULL DEFAULT 0,
            identity_strength INTEGER NOT NULL DEFAULT 0, required_models_json TEXT,
            required_nodes_json TEXT, license_notes TEXT, is_available INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
    """)
    # Mark all migrations as applied so _ensure_db is a no-op
    for name in ["023_image_jobs.sql", "024_image_characters.sql", "025_image_references.sql", "026_image_recipes.sql"]:
        conn.execute("INSERT OR IGNORE INTO schema_migrations (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
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

    def test_fast_tier(self, override_db):
        seed_default_recipes()
        decision = auto_route(has_character=False, quality_tier="fast")
        assert decision.recipe.quality_tier == "fast"

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
