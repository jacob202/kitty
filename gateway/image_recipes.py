"""Image Studio V1 — Recipe registry and Auto routing.

Replaces keyword-based prompt parsing with typed, capability-aware generation recipes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from gateway import db as kitty_db
from gateway.paths import KITTY_DB_FILE


class RecipeError(RuntimeError):
    """Raised when a recipe operation cannot complete."""


@dataclass
class Recipe:
    recipe_id: str
    display_name: str
    description: str | None
    provider: str
    workflow_template_id: str | None
    model_family: str | None
    operation: str = "txt2img"
    quality_tier: str = "quality"
    expected_speed: str | None = None
    default_width: int = 1024
    default_height: int = 1024
    max_width: int = 2048
    max_height: int = 2048
    supported_aspects: list[str] | None = None
    supports_img2img: bool = False
    supports_characters: bool = False
    max_characters: int = 0
    supports_pose_refs: bool = False
    supports_outfit_refs: bool = False
    supports_object_refs: bool = False
    supports_location_refs: bool = False
    supports_style_refs: bool = False
    supports_inpainting: bool = False
    supports_variation: bool = False
    supports_upscaling: bool = False
    identity_strength: int = 0
    required_models: list[str] | None = None
    required_nodes: list[str] | None = None
    license_notes: str | None = None
    is_available: bool = True
    priority: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "display_name": self.display_name,
            "description": self.description,
            "provider": self.provider,
            "quality_tier": self.quality_tier,
            "operation": self.operation,
            "supports_characters": self.supports_characters,
            "max_characters": self.max_characters,
            "supports_pose_refs": self.supports_pose_refs,
            "supports_outfit_refs": self.supports_outfit_refs,
            "supports_style_refs": self.supports_style_refs,
            "supports_variation": self.supports_variation,
            "identity_strength": self.identity_strength,
            "is_available": self.is_available,
        }


@dataclass
class RoutingDecision:
    recipe_id: str
    recipe: Recipe | None
    reason: str
    fallback: bool = False


# ── Default recipe registry ──────────────────────────────────────────────────

DEFAULT_RECIPES: list[dict[str, Any]] = [
    {
        "recipe_id": "comfyui_sd15_standard",
        "display_name": "SD 1.5 Standard",
        "description": "Fast general-purpose generation on Stable Diffusion 1.5",
        "provider": "comfyui",
        "workflow_template_id": "sd15_basic",
        "model_family": "sd15",
        "quality_tier": "fast",
        "expected_speed": "5-15s",
        "default_width": 512,
        "default_height": 512,
        "max_width": 1024,
        "max_height": 1024,
        "supported_aspects": ["1:1", "3:2", "2:3", "16:9"],
        "supports_img2img": True,
        "supports_variation": True,
        "is_available": False,
        "priority": 10,
    },
    {
        "recipe_id": "comfyui_sdxl_standard",
        "display_name": "SDXL Photonic",
        "description": "High-quality generation on SDXL. Supports characters with IP-Adapter identity preservation.",
        "provider": "comfyui",
        "workflow_template_id": "sdxl_photonic",
        "model_family": "sdxl",
        "quality_tier": "quality",
        "expected_speed": "15-30s",
        "default_width": 1024,
        "default_height": 1024,
        "max_width": 1920,
        "max_height": 1920,
        "supported_aspects": ["1:1", "3:2", "2:3", "16:9", "9:16"],
        "supports_img2img": True,
        "supports_characters": True,
        "max_characters": 1,
        "supports_pose_refs": True,
        "supports_outfit_refs": True,
        "supports_style_refs": True,
        "supports_variation": True,
        "identity_strength": 70,
        "required_models": ["sd_xl_base_1.0.safetensors", "ip-adapter-plus_sdxl_vit-h.safetensors"],
        "required_nodes": ["ComfyUI_IPAdapter_plus"],
        "license_notes": "IP-Adapter model: Apache-2.0. SDXL: CreativeML Open RAIL++-M.",
        "priority": 20,
    },
    {
        "recipe_id": "comfyui_pulid_sdxl",
        "display_name": "PuLID SDXL Identity",
        "description": "Strong identity preservation using PuLID on SDXL. Best for character consistency.",
        "provider": "comfyui",
        "workflow_template_id": "pulid_sdxl",
        "model_family": "sdxl",
        "quality_tier": "maximum",
        "expected_speed": "20-40s",
        "default_width": 1024,
        "default_height": 1024,
        "max_width": 1920,
        "max_height": 1920,
        "supports_img2img": True,
        "supports_characters": True,
        "max_characters": 1,
        "supports_variation": True,
        "identity_strength": 95,
        "required_models": ["sd_xl_base_1.0.safetensors"],
        "required_nodes": ["ComfyUI_PuLID"],
        "license_notes": "PuLID: Apache-2.0. Requires InsightFace (research/non-commercial for some backends — verify model license). SDXL: CreativeML Open RAIL++-M.",
        "is_available": False,
        "priority": 30,
    },
    {
        "recipe_id": "drawthings_standard",
        "display_name": "Draw Things",
        "description": "Local generation via Draw Things (Apple Silicon). A1111-compatible.",
        "provider": "drawthings",
        "quality_tier": "fast",
        "expected_speed": "10-30s",
        "default_width": 512,
        "default_height": 512,
        "supported_aspects": ["1:1", "3:2", "2:3"],
        "supports_img2img": True,
        "supports_variation": True,
        "is_available": False,
        "priority": 5,
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_db() -> None:
    kitty_db.migrate(db_file=KITTY_DB_FILE)


def seed_default_recipes() -> int:
    """Insert default recipes if the table is empty. Returns count inserted."""
    _ensure_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM image_recipes").fetchone()
        if row and row["cnt"] > 0:
            return 0
        now = _now()
        count = 0
        for r in DEFAULT_RECIPES:
            conn.execute(
                """INSERT INTO image_recipes
                   (recipe_id, display_name, description, provider, workflow_template_id,
                    model_family, operation, quality_tier, expected_speed,
                    default_width, default_height, max_width, max_height,
                    supported_aspects_json, supports_img2img, supports_characters,
                    max_characters, supports_pose_refs, supports_outfit_refs,
                    supports_object_refs, supports_location_refs, supports_style_refs,
                    supports_inpainting, supports_variation, supports_upscaling,
                    identity_strength, required_models_json, required_nodes_json,
                    license_notes, is_available, priority, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    r["recipe_id"], r["display_name"], r.get("description"),
                    r["provider"], r.get("workflow_template_id"),
                    r.get("model_family"), r.get("operation", "txt2img"),
                    r["quality_tier"], r.get("expected_speed"),
                    r.get("default_width", 1024), r.get("default_height", 1024),
                    r.get("max_width", 2048), r.get("max_height", 2048),
                    json.dumps(r.get("supported_aspects")),
                    int(r.get("supports_img2img", False)),
                    int(r.get("supports_characters", False)),
                    r.get("max_characters", 0),
                    int(r.get("supports_pose_refs", False)),
                    int(r.get("supports_outfit_refs", False)),
                    int(r.get("supports_object_refs", False)),
                    int(r.get("supports_location_refs", False)),
                    int(r.get("supports_style_refs", False)),
                    int(r.get("supports_inpainting", False)),
                    int(r.get("supports_variation", False)),
                    int(r.get("supports_upscaling", False)),
                    r.get("identity_strength", 0),
                    json.dumps(r.get("required_models")),
                    json.dumps(r.get("required_nodes")),
                    r.get("license_notes"), 1, r.get("priority", 0), now, now,
                ),
            )
            count += 1
        conn.commit()
    return count


def list_recipes(available_only: bool = False) -> list[Recipe]:
    _ensure_db()
    query = "SELECT * FROM image_recipes"
    if available_only:
        query += " WHERE is_available = 1"
    query += " ORDER BY priority DESC"
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        rows = conn.execute(query).fetchall()
    return [_row_to_recipe(r) for r in rows]


def get_recipe(recipe_id: str) -> Recipe:
    _ensure_db()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        row = conn.execute(
            "SELECT * FROM image_recipes WHERE recipe_id = ?", (recipe_id,)
        ).fetchone()
    if row is None:
        raise RecipeError(f"recipe {recipe_id!r} not found")
    return _row_to_recipe(row)


def set_recipe_available(recipe_id: str, available: bool) -> Recipe:
    _ensure_db()
    now = _now()
    with kitty_db.connect(KITTY_DB_FILE) as conn:
        conn.execute(
            "UPDATE image_recipes SET is_available = ?, updated_at = ? WHERE recipe_id = ?",
            (int(available), now, recipe_id),
        )
        conn.commit()
    return get_recipe(recipe_id)


def auto_route(
    *,
    has_character: bool = False,
    character_count: int = 0,
    reference_kinds: set[str] | None = None,
    quality_tier: str = "quality",
    identity_mode: str = "balanced",
    operation: str = "txt2img",
    preferred_recipe: str | None = None,
) -> RoutingDecision:
    """Select the best recipe for a generation request.

    Deterministic for the same input and database state.
    """
    recipes = list_recipes(available_only=True)
    if not recipes:
        raise RecipeError("no image recipes are available")

    # If user prefers a specific recipe and it's available
    if preferred_recipe:
        try:
            r = get_recipe(preferred_recipe)
            if r.is_available:
                return RoutingDecision(r.recipe_id, r, "Selected by user preference")
        except RecipeError:
            pass

    # Identity-first: choose the highest-identity-strength recipe that supports characters
    if identity_mode == "identity_first" and has_character:
        char_recipes = [r for r in recipes if r.supports_characters]
        if char_recipes:
            best = max(char_recipes, key=lambda r: (r.identity_strength, r.priority))
            return RoutingDecision(best.recipe_id, best,
                f"Selected for strongest character likeness (identity strength: {best.identity_strength}%)")

    # Character generation: must have a character-supporting recipe
    if has_character:
        char_recipes = [r for r in recipes if r.supports_characters and r.max_characters >= character_count]
        if not char_recipes:
            raise RecipeError(
                f"no available recipe supports {character_count} character(s). "
                f"Available character recipes: "
                f"{[r.recipe_id for r in recipes if r.supports_characters]}"
            )
        # Filter by quality tier
        tier_recipes = [r for r in char_recipes if r.quality_tier == quality_tier]
        if tier_recipes:
            recipes_subset = tier_recipes
        else:
            # Fall back to next best tier
            fallback_tiers = {"maximum": ["quality", "fast"], "quality": ["fast"], "fast": ["quality"]}
            for ft in fallback_tiers.get(quality_tier, []):
                tier_recipes = [r for r in char_recipes if r.quality_tier == ft]
                if tier_recipes:
                    return RoutingDecision(tier_recipes[0].recipe_id, tier_recipes[0],
                        f"Selected {ft} tier recipe because {quality_tier} tier is unavailable for characters",
                        fallback=True)
            recipes_subset = char_recipes
        best = max(recipes_subset, key=lambda r: (r.identity_strength, r.priority))
        return RoutingDecision(best.recipe_id, best,
            f"Selected for character generation ({best.quality_tier} tier, {best.display_name})")

    # No character: pick by quality tier and priority
    if quality_tier == "fast":
        tier_recipes = [r for r in recipes if r.quality_tier == "fast"]
        if tier_recipes:
            return RoutingDecision(tier_recipes[0].recipe_id, tier_recipes[0],
                f"Selected fastest available recipe: {tier_recipes[0].display_name}")
    if quality_tier == "maximum":
        tier_recipes = [r for r in recipes if r.quality_tier == "maximum"]
        if tier_recipes:
            return RoutingDecision(tier_recipes[0].recipe_id, tier_recipes[0],
                f"Selected highest-quality recipe: {tier_recipes[0].display_name}")

    # Default: highest priority available
    best = max(recipes, key=lambda r: r.priority)
    return RoutingDecision(best.recipe_id, best, f"Default recipe: {best.display_name}")


def _row_to_recipe(row: Any) -> Recipe:
    aspects = row["supported_aspects_json"]
    return Recipe(
        recipe_id=row["recipe_id"],
        display_name=row["display_name"],
        description=row["description"],
        provider=row["provider"],
        workflow_template_id=row["workflow_template_id"],
        model_family=row["model_family"],
        operation=row["operation"],
        quality_tier=row["quality_tier"],
        expected_speed=row["expected_speed"],
        default_width=row["default_width"],
        default_height=row["default_height"],
        max_width=row["max_width"],
        max_height=row["max_height"],
        supported_aspects=json.loads(aspects) if aspects else None,
        supports_img2img=bool(row["supports_img2img"]),
        supports_characters=bool(row["supports_characters"]),
        max_characters=row["max_characters"],
        supports_pose_refs=bool(row["supports_pose_refs"]),
        supports_outfit_refs=bool(row["supports_outfit_refs"]),
        supports_object_refs=bool(row["supports_object_refs"]),
        supports_location_refs=bool(row["supports_location_refs"]),
        supports_style_refs=bool(row["supports_style_refs"]),
        supports_inpainting=bool(row["supports_inpainting"]),
        supports_variation=bool(row["supports_variation"]),
        supports_upscaling=bool(row["supports_upscaling"]),
        identity_strength=row["identity_strength"],
        required_models=json.loads(row["required_models_json"]) if row["required_models_json"] else None,
        required_nodes=json.loads(row["required_nodes_json"]) if row["required_nodes_json"] else None,
        license_notes=row["license_notes"],
        is_available=bool(row["is_available"]),
        priority=row["priority"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
