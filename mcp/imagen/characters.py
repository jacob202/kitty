"""Private character reference discovery and deterministic curation."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from mcp.imagen.config import settings

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_AI_NAME_PREFIXES = (
    "gemini_generated_image",
    "veniceai_",
    "generate_an_image",
)


def _slug(name: str) -> str:
    value = re.sub(r"[^a-z0-9_-]+", "-", name.strip().lower()).strip("-")
    if not value:
        raise ValueError("character name must contain letters or numbers")
    return value


def character_source_dir(name: str) -> Path:
    """Return the private source directory, falling back to legacy repo-local refs."""
    slug = _slug(name)
    private_root = Path(
        os.environ.get("KITTY_FACES_DIR", str(Path.home() / "kitty-services" / "faces"))
    ).expanduser()
    private = private_root / slug
    if private.exists():
        return private
    return settings.faces_dir / slug


def _image_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES and not p.name.startswith(".")
    )


def reference_images(name: str, *, prefer_curated: bool = True) -> list[Path]:
    """Return usable refs, preferring curated data when it exists."""
    source = character_source_dir(name)
    if prefer_curated:
        curated = _image_files(source / "curated")
        if curated:
            return curated
    return _image_files(source)


def _clear_previous_derivatives(output: Path) -> None:
    manifest = output / "manifest.json"
    if not manifest.exists():
        return
    try:
        prior = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return
    for row in prior.get("files", []):
        name = row.get("curated_file") if isinstance(row, dict) else None
        if name:
            candidate = output / Path(name).name
            if candidate.is_file():
                candidate.unlink()


def curate_references(
    source: Path,
    output: Path,
    *,
    min_dimension: int = 256,
    max_dimension: int = 1536,
) -> dict[str, Any]:
    """Create a non-destructive, normalized set with an auditable manifest."""
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"reference source does not exist: {source}")
    output.mkdir(parents=True, exist_ok=True)
    _clear_previous_derivatives(output)

    candidates = _image_files(source)
    candidates.sort(key=lambda p: (p.stat().st_mtime_ns, p.name.lower()))
    seen_hashes: set[str] = set()
    rows: list[dict[str, Any]] = []
    included = 0

    for path in candidates:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        row: dict[str, Any] = {
            "source": path.name,
            "sha256": digest,
            "decision": "excluded",
            "reason": "",
        }
        lower = path.name.lower()
        if lower.startswith(_AI_NAME_PREFIXES):
            row["reason"] = "ai_generated_filename"
            rows.append(row)
            continue
        if digest in seen_hashes:
            row["reason"] = "duplicate_exact_file"
            rows.append(row)
            continue
        seen_hashes.add(digest)

        try:
            with Image.open(path) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                width, height = image.size
                row["source_dimensions"] = [width, height]
                if min(width, height) < min_dimension:
                    row["reason"] = "below_min_dimension"
                    rows.append(row)
                    continue
                if max(width, height) > max_dimension:
                    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

                included += 1
                safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", path.stem).strip("_") or "ref"
                filename = f"{included:02d}_{safe_stem}.jpg"
                destination = output / filename
                image.save(destination, format="JPEG", quality=95, optimize=True)
                row.update({
                    "decision": "included",
                    "reason": "accepted",
                    "curated_file": filename,
                    "curated_dimensions": list(image.size),
                })
        except Exception as exc:
            row["reason"] = "invalid_image"
            row["error"] = type(exc).__name__
        rows.append(row)

    report = {
        "source_dir": str(source),
        "output_dir": str(output),
        "included_count": sum(r["decision"] == "included" for r in rows),
        "excluded_count": sum(r["decision"] != "included" for r in rows),
        "min_dimension": min_dimension,
        "max_dimension": max_dimension,
        "files": rows,
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
