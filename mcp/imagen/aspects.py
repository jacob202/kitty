"""Aspect-ratio aliases that resolve to engine-native strings.

Different engines use different aspect representations:
  - nano_banana (Gemini): "1:1", "3:2", "9:16", "21:9" (string ratio)
  - imagen4: same as nano_banana
  - dalle: "1024x1024", "1024x1792", "1792x1024" (explicit pixel dims)
  - comfyui: (width, height) tuple

`ALIASES` normalizes this so the LLM can use a stable vocabulary
("cinemascope", "portrait_phone") regardless of engine. Aliases that
an engine doesn't support are `None` — `resolve()` raises a helpful
error pointing at the supported sizes for that engine.
"""

from __future__ import annotations

# Per-engine resolution. Values are the engine-native shape.
# None means the engine doesn't support that aspect.
ALIASES: dict[str, dict[str, str | tuple[int, int] | None]] = {
    "cinemascope": {
        "nano_banana": "21:9",
        "imagen4": "16:9",
        "dalle": "1792x768",
        "comfyui": (1536, 640),
    },
    "widescreen": {
        "nano_banana": "16:9",
        "imagen4": "16:9",
        "dalle": "1792x1024",
        "comfyui": (1280, 720),
    },
    "portrait_phone": {
        "nano_banana": "9:16",
        "imagen4": "9:16",
        "dalle": "1024x1792",
        "comfyui": (576, 1024),
    },
    "portrait_classic": {
        "nano_banana": "2:3",
        "imagen4": "3:4",
        "dalle": "1024x1792",
        "comfyui": (832, 1216),
    },
    "landscape_classic": {
        "nano_banana": "3:2",
        "imagen4": "4:3",
        "dalle": "1792x1024",
        "comfyui": (1216, 832),
    },
    "instagram_square": {
        "nano_banana": "1:1",
        "imagen4": "1:1",
        "dalle": "1024x1024",
        "comfyui": (1024, 1024),
    },
    "photo_35mm": {
        "nano_banana": "3:2",
        "imagen4": "3:2",
        # DALL-E 3 has no 3:2 preset.
        "dalle": None,
        "comfyui": (1500, 1000),
    },
}

# Supported sizes per engine, used for the error message when an
# alias is requested that the engine doesn't support.
SUPPORTED: dict[str, list[str]] = {
    "nano_banana": ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
    "imagen4": ["1:1", "3:4", "4:3", "9:16", "16:9"],
    "dalle": ["1024x1024", "1792x1024", "1024x1792"],
    "comfyui": ["(w, h) tuple, e.g. (1024, 1024) — any size"],
}


def resolve(aspect: str | tuple[int, int], engine: str) -> str | tuple[int, int]:
    """Resolve an aspect alias to the engine-native shape.

    If `aspect` is a known alias (key in ALIASES), return the per-engine
    value. If the engine doesn't support that alias (value is None),
    raise ValueError with a helpful message listing the engine's
    supported sizes.

    If `aspect` is NOT a known alias, return it as-is. This lets power
    users pass engine-native values directly (e.g. "21:9" for nano_banana)
    without needing to know which is an alias and which is raw.

    Returns either a string (ratio or pixel-dim) or a (w, h) tuple for
    comfyui.
    """
    if aspect in ALIASES:
        per_engine = ALIASES[aspect]
        if engine not in per_engine:
            raise ValueError(
                f"Aspect alias {aspect!r} is not defined for engine {engine!r}. "
                f"Known engines for this alias: {sorted(per_engine)}"
            )
        value = per_engine[engine]
        if value is None:
            supported = ", ".join(SUPPORTED.get(engine, []))
            raise ValueError(
                f"Engine {engine!r} doesn't support aspect {aspect!r}. "
                f"Supported: {supported}"
            )
        return value

    # Raw passthrough: caller used the engine-native form directly.
    return aspect
