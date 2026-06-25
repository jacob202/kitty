"""Tests for mcp.imagen.aspects — alias resolution per engine."""

from __future__ import annotations

import pytest

from mcp.imagen.aspects import ALIASES, resolve

# --- Engine-native raw pass-through ---


def test_raw_string_passes_through_nano_banana():
    assert resolve("21:9", "nano_banana") == "21:9"


def test_raw_string_passes_through_imagen4():
    assert resolve("16:9", "imagen4") == "16:9"


def test_raw_string_passes_through_dalle():
    assert resolve("1024x1024", "dalle") == "1024x1024"


# --- Alias resolution per engine ---


def test_cinemascope_nano_banana_is_21_9():
    assert resolve("cinemascope", "nano_banana") == "21:9"


def test_cinemascope_imagen4_falls_back_to_16_9():
    # Imagen 4 doesn't support 21:9; the alias resolution falls back.
    assert resolve("cinemascope", "imagen4") == "16:9"


def test_cinemascope_dalle_is_explicit_pixels():
    assert resolve("cinemascope", "dalle") == "1792x768"


def test_cinemascope_comfyui_is_tuple():
    val = resolve("cinemascope", "comfyui")
    assert val == (1536, 640)
    assert isinstance(val, tuple)


def test_portrait_phone_routes_correctly():
    assert resolve("portrait_phone", "nano_banana") == "9:16"
    assert resolve("portrait_phone", "imagen4") == "9:16"
    assert resolve("portrait_phone", "dalle") == "1024x1792"
    assert resolve("portrait_phone", "comfyui") == (576, 1024)


def test_instagram_square_is_1_1_everywhere():
    for engine, expected in [
        ("nano_banana", "1:1"),
        ("imagen4", "1:1"),
        ("dalle", "1024x1024"),
        ("comfyui", (1024, 1024)),
    ]:
        assert resolve("instagram_square", engine) == expected


# --- Engine rejection (alias maps to None) ---


def test_photo_35mm_dalle_raises_with_helpful_message():
    """photo_35mm has no dalle preset — should raise ValueError listing
    dalle's supported sizes."""
    with pytest.raises(ValueError) as exc_info:
        resolve("photo_35mm", "dalle")
    msg = str(exc_info.value)
    assert "dalle" in msg
    assert "1024x1024" in msg  # supported sizes listed
    assert "1024x1792" in msg


# --- Aliases are well-formed ---


def test_every_alias_has_all_4_engines():
    for alias, per_engine in ALIASES.items():
        for engine in ("nano_banana", "imagen4", "dalle", "comfyui"):
            assert engine in per_engine, f"{alias!r} missing engine {engine!r}"


def test_alias_string_values_are_nonempty_or_none():
    """Either the engine supports the alias (string non-empty or tuple) or
    it's explicitly None. No garbage values."""
    for alias, per_engine in ALIASES.items():
        for engine, value in per_engine.items():
            if value is None:
                continue
            if isinstance(value, str):
                assert value.strip(), f"{alias!r} {engine!r} has empty string"
            elif isinstance(value, tuple):
                assert len(value) == 2 and all(isinstance(v, int) and v > 0 for v in value), (
                    f"{alias!r} {engine!r} has bad tuple {value!r}"
                )
            else:
                pytest.fail(f"{alias!r} {engine!r} has unexpected value type {type(value)}")
