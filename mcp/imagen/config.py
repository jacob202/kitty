"""Settings and constants for the imagen MCP server.

All model names are env-overridable so model-name drift never bricks the server.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_OUTPUT = Path.home() / "Pictures" / "kitty-gen"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, "").strip() or default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


@dataclass
class Settings:
    """Settings snapshot read at import time.

    Env overrides are read once here; runtime code reads from ``os.environ``
    for values that should pick up changes without a restart (API keys).
    """

    # Output
    output_dir: Path = field(default_factory=lambda: _OUTPUT)
    avatar_path: Path = field(default_factory=lambda: _OUTPUT / "_avatar.png")

    # Model names (env-overridable)
    gemini_image_model: str = field(
        default_factory=lambda: _env("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    )
    gemini_vision_model: str = field(
        default_factory=lambda: _env("GEMINI_VISION_MODEL", "gemini-2.5-flash")
    )
    imagen_model: str = field(
        default_factory=lambda: _env("IMAGEN_MODEL", "imagen-4.0-generate-001")
    )

    # Prompt suffix for photorealism
    photoreal_suffix: str = (
        ", photorealistic, shot on a full-frame DSLR, 85mm lens, natural lighting, "
        "shallow depth of field, sharp focus, high detail, true-to-life color"
    )

    # PR 3: cache
    cache_enabled: bool = field(
        default_factory=lambda: _env("IMAGEN_CACHE_ENABLED", "1") not in ("0", "false", "no")
    )
    cache_dir: Path = field(default_factory=lambda: _OUTPUT / ".cache")

    # PR 3: retry
    retry_attempts: int = field(default_factory=lambda: _env_int("IMAGEN_RETRY_ATTEMPTS", 3))

    # PR 3: batch concurrency
    batch_concurrency_limit: int = field(
        default_factory=lambda: _env_int("IMAGEN_BATCH_CONCURRENCY", 10)
    )

    # Default engine for generate()
    default_engine: str = field(
        default_factory=lambda: _env("IMAGEN_DEFAULT_ENGINE", "nano_banana")
    )

    # ComfyUI
    comfy_url: str = field(default_factory=lambda: _env("COMFY_URL", "http://127.0.0.1:8188"))

    # Draw Things / A1111-compatible API
    dt_url: str = field(default_factory=lambda: _env("DT_URL", "http://127.0.0.1:7860"))
    dt_model: str = field(default_factory=lambda: _env("DT_MODEL", "icatcher_realistic"))

    # Verifier settings
    ollama_url: str = field(default_factory=lambda: _env("OLLAMA_URL", "http://127.0.0.1:11434"))
    vision_model: str = field(default_factory=lambda: _env("VISION_MODEL", "qwen2.5-vl:7b"))

    # Face-lock reference directory
    faces_dir: Path = field(default_factory=lambda: Path("config/imagen/faces"))


settings = Settings()
