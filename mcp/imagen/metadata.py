"""Image metadata: sidecar JSON, manifest, and read/regenerate tools.

Every save writes a `<image>.json` sidecar with full provenance, and
appends a one-line record to `manifest.jsonl` for fast query.

Layout in ~/Pictures/kitty-gen/:
  nano_<ts>.png
  nano_<ts>.png.json         <- sidecar
  edit_<ts>.png
  edit_<ts>.png.json
  manifest.jsonl             <- one line per generation, denormalized

Sidecar schema:
  {
    "prompt": "...",
    "engine": "nano_banana",
    "model": "gemini-2.5-flash-image",
    "seed": 12345,            # or null
    "params": {"aspect_ratio": "16:9", "photorealistic": true},
    "ts": 1719331200.0,
    "parent_path": null,       # or path of the source image for edits
    "tags": []
  }

Sidecar write failures are logged at WARNING but do not fail the
generation. The metadata tool returns "no metadata" for missing
sidecars so callers can degrade gracefully.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("kitty.imagen.metadata")

MANIFEST_FILENAME = "manifest.jsonl"

# `OUTPUT_DIR` lives in server.py; we read it lazily to avoid the
# circular import (server.py → metadata.py → server.py).
def _output_dir():
    from mcp.imagen.server import OUTPUT_DIR
    return OUTPUT_DIR


# ---------------------------------------------------------------------------
# Sidecar
# ---------------------------------------------------------------------------


def sidecar_path(image_path: Path) -> Path:
    return image_path.with_suffix(image_path.suffix + ".json")


def write_sidecar(
    image_path: Path,
    *,
    prompt: str,
    engine: str,
    model: str,
    seed: int | None = None,
    params: dict[str, Any] | None = None,
    parent_path: str | None = None,
    tags: list[str] | None = None,
) -> Path:
    """Write the sidecar JSON alongside an image. Best-effort: a failure
    is logged at WARNING but never raised, so the gen still completes.

    Returns the sidecar path (or `image_path` if the write failed).
    """
    sidecar = sidecar_path(image_path)
    record = {
        "prompt": prompt,
        "engine": engine,
        "model": model,
        "seed": seed,
        "params": params or {},
        "ts": time.time(),
        "parent_path": parent_path,
        "tags": tags or [],
    }
    try:
        sidecar.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("sidecar write failed for %s: %s", image_path, exc)
        return image_path  # caller proceeds; image is still valid
    return sidecar


def append_manifest(image_path: Path, sidecar: Path) -> None:
    """Append a denormalized row to manifest.jsonl.

    Best-effort: logged at WARNING on failure. The manifest is a
    cache for fast query; if it fails, callers can still read each
    sidecar individually.
    """
    manifest = _output_dir() / MANIFEST_FILENAME
    try:
        record = json.loads(sidecar.read_text(encoding="utf-8"))
        record["image_path"] = str(image_path)
        record["sidecar_path"] = str(sidecar)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("manifest append failed for %s: %s", image_path, exc)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def read_image_metadata(path: str) -> dict[str, Any] | str:
    """Read the sidecar for an image. Returns the dict, or a string
    message if no sidecar exists (caller can render the string to the
    user)."""
    p = Path(path).expanduser()
    sidecar = sidecar_path(p)
    if not sidecar.exists():
        return f"no metadata for {path}"
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"sidecar at {sidecar} is unreadable: {exc}"


def read_manifest(
    *,
    engine: str | None = None,
    since: float | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query the manifest, newest first, optionally filtered by engine
    and `since` (epoch seconds). Returns up to `limit` matches.

    Malformed lines are skipped with a WARNING (the manifest is a
    cache, not the source of truth — sidecars are).
    """
    manifest = _output_dir() / MANIFEST_FILENAME
    if not manifest.exists():
        return []

    rows: list[dict[str, Any]] = []
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("manifest read failed: %s", exc)
        return []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning("manifest: skipping malformed line (%s): %s", exc, line[:120])
            continue
        if engine is not None and row.get("engine") != engine:
            continue
        if since is not None and row.get("ts", 0) < since:
            continue
        rows.append(row)

    rows.sort(key=lambda r: r.get("ts", 0), reverse=True)
    return rows[:limit]


# ---------------------------------------------------------------------------
# Regenerate
# ---------------------------------------------------------------------------


# Engines that support seed (per PR 4 plan). For others, the call
# proceeds without seed and the user gets a non-reproducible re-roll.
SEED_SUPPORTED: set[str] = {"comfyui"}  # Nano Banana is best-effort, see notes


def regenerate(
    path: str,
    *,
    prompt_override: str | None = None,
    engine_override: str | None = None,
    **engine_kwargs: Any,
) -> list:
    """Re-run a generation from a saved image's metadata.

    Reads the sidecar, then calls the appropriate engine with the
    saved prompt + params. `prompt_override` replaces the prompt;
    `engine_override` switches engines (risky — same prompt may
    produce very different results). Other kwargs are forwarded to
    the engine. For engines that don't support seed, the seed is
    silently dropped and a new random seed is used (logged).
    """
    meta = read_image_metadata(path)
    if isinstance(meta, str):
        return [meta]

    prompt = prompt_override or meta.get("prompt", "")
    engine = engine_override or meta.get("engine", "")
    seed = meta.get("seed")
    params = dict(meta.get("params") or {})

    if not prompt or not engine:
        return [f"sidecar for {path} is missing prompt/engine"]

    if engine not in SEED_SUPPORTED and seed is not None:
        logger.warning("regenerate: engine %r doesn't support seed; dropping", engine)
        seed = None

    # Dispatch by engine. Mirrors the routing in server.py.
    if engine == "nano_banana":
        return _regen_nano(prompt, params, seed, **engine_kwargs)
    if engine == "imagen4":
        return _regen_imagen4(prompt, params, **engine_kwargs)
    if engine == "dalle":
        return _regen_dalle(prompt, params, **engine_kwargs)
    if engine == "comfyui":
        return _regen_comfy(prompt, params, seed, **engine_kwargs)
    return [f"regenerate: unknown engine {engine!r}"]


def _regen_nano(prompt: str, params: dict, seed: int | None, **kwargs: Any) -> list:
    from google.genai import types

    from mcp.imagen.server import (
        PHOTOREAL_SUFFIX,
        _first_image_bytes,
        _gemini_client,
        _save,
    )

    photoreal = params.get("photorealistic", True)
    full_prompt = prompt + (PHOTOREAL_SUFFIX if photoreal else "")
    aspect = params.get("aspect_ratio", "1:1")

    client = _gemini_client()
    response = client.models.generate_content(
        model=kwargs.get("model", "gemini-2.5-flash-image"),
        contents=full_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect),
        ),
    )
    data = _first_image_bytes(response)
    if data is None:
        return ["regenerate: nano_banana returned no image"]
    path = _save(data, "regen-nano")
    sidecar = write_sidecar(
        path,
        prompt=full_prompt,
        engine="nano_banana",
        model=kwargs.get("model", "gemini-2.5-flash-image"),
        seed=seed,
        params={"aspect_ratio": aspect, "photorealistic": photoreal},
    )
    append_manifest(path, sidecar)
    return [{"image_path": str(path), "sidecar": str(sidecar)}]


def _regen_imagen4(prompt: str, params: dict, **kwargs: Any) -> list:
    from google.genai import types

    from mcp.imagen.server import _gemini_client, _save

    client = _gemini_client()
    response = client.models.generate_images(
        model="imagen-4.0-generate-001",
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=kwargs.get("count", 1),
            aspect_ratio=params.get("aspect_ratio", "1:1"),
            person_generation="ALLOW_ADULT",
        ),
    )
    if not response.generated_images:
        return ["regenerate: imagen4 returned no images"]
    paths: list[Any] = []
    for img in response.generated_images:
        data = img.image.image_bytes
        path = _save(data, "regen-imagen")
        sidecar = write_sidecar(
            path,
            prompt=prompt,
            engine="imagen4",
            model="imagen-4.0-generate-001",
            params={"aspect_ratio": params.get("aspect_ratio", "1:1")},
        )
        append_manifest(path, sidecar)
        paths.append(str(path))
    return paths


def _regen_dalle(prompt: str, params: dict, **kwargs: Any) -> list:
    import httpx

    from mcp.imagen.server import _openai_client, _save

    client = _openai_client()
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=params.get("size", "1024x1024"),
        quality=params.get("quality", "hd"),
        n=1,
    )
    url = response.data[0].url
    if not url:
        return ["regenerate: dalle returned no URL"]
    data = httpx.get(url, timeout=60).content
    path = _save(data, "regen-dalle")
    sidecar = write_sidecar(
        path,
        prompt=prompt,
        engine="dalle",
        model="dall-e-3",
        params={
            "size": params.get("size", "1024x1024"),
            "quality": params.get("quality", "hd"),
        },
    )
    append_manifest(path, sidecar)
    return [str(path)]


def _regen_comfy(prompt: str, params: dict, seed: int | None, **kwargs: Any) -> list:
    # ComfyUI regen is async (uses websockets/HTTP polling). Punt to
    # server.py's existing async path by returning a marker; the
    # caller (or a thin wrapper) can invoke the async path.
    return [
        f"regenerate: comfyui re-roll needs the live workflow (seed={seed}); "
        f"call generate_image_comfy(prompt={prompt!r}) with the seed forwarded."
    ]


# ---------------------------------------------------------------------------
# open_in_viewer
# ---------------------------------------------------------------------------


def open_in_viewer(path: str) -> str:
    """Open an image in the system viewer (macOS: Preview.app via
    `open`). Other platforms return a message saying so."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"file not found: {path}"
    if sys.platform != "darwin":
        return f"open_in_viewer is macOS-only (you're on {sys.platform}); open {p} manually"
    try:
        subprocess.Popen(["open", str(p)])  # non-blocking
    except OSError as exc:
        return f"open failed: {exc}"
    return f"Opened {p} in system viewer."
