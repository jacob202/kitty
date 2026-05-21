"""Open WebUI tool — browse and manage files in Kitty's data directories."""
import json
import os
import time
from pathlib import Path
from typing import Optional

ALLOWED_ROOTS = [
    Path(os.path.expanduser("~/Projects/kitty/data")),
    Path(os.path.expanduser("~/Projects/kitty/outputs")),
    Path(os.path.expanduser("~/Downloads")),
]

MAX_LIST_ITEMS = 50
MAX_READ_BYTES = 100_000
MAX_FILENAME_LEN = 200


def _resolve_path(user_path: str) -> Optional[Path]:
    p = Path(os.path.expanduser(user_path)).resolve()
    for root in ALLOWED_ROOTS:
        root_resolved = root.resolve()
        if root_resolved in p.parents or p == root_resolved:
            return p
    return None


def _safe_path(user_path: str) -> Path:
    resolved = _resolve_path(user_path)
    if not resolved:
        raise PermissionError(
            f"Path '{user_path}' is outside allowed directories: {[str(r) for r in ALLOWED_ROOTS]}"
        )
    return resolved


class Tools:
    def list_directory(self, path: str = "~/Projects/kitty/data") -> str:
        """List files and directories at the given path (limited to allowed directories)."""
        try:
            resolved = _safe_path(path)
            if not resolved.is_dir():
                return f"Not a directory: {resolved}"
            entries = list(resolved.iterdir())[:MAX_LIST_ITEMS]
            lines = [f"Contents of {resolved}/"]
            for entry in sorted(entries):
                kind = "d" if entry.is_dir() else "f"
                size = entry.stat().st_size if entry.is_file() else 0
                mtime = time.strftime(
                    "%Y-%m-%d %H:%M",
                    time.localtime(entry.stat().st_mtime),
                )
                label = entry.name
                if len(label) > MAX_FILENAME_LEN:
                    label = label[:MAX_FILENAME_LEN] + "..."
                if kind == "d":
                    lines.append(f"  {kind}  {label}/")
                else:
                    lines.append(f"  {kind}  {size:>8}  {mtime}  {label}")
            if len(list(resolved.iterdir())) > MAX_LIST_ITEMS:
                lines.append(f"  ... ({len(list(resolved.iterdir())) - MAX_LIST_ITEMS} more)")
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing directory: {e}"

    def read_file(self, path: str) -> str:
        """Read the contents of a text file (limited to allowed directories, max 100KB)."""
        try:
            resolved = _safe_path(path)
            if not resolved.is_file():
                return f"Not a file: {resolved}"
            if resolved.stat().st_size > MAX_READ_BYTES:
                return f"File too large ({resolved.stat().st_size} bytes, max {MAX_READ_BYTES})"
            text = resolved.read_text(encoding="utf-8", errors="replace")
            return text
        except Exception as e:
            return f"Error reading file: {e}"

    def file_metadata(self, path: str) -> str:
        """Get metadata for a file: size, modification time, type, and EXIF if it's an image."""
        try:
            resolved = _safe_path(path)
            if not resolved.exists():
                return f"Not found: {resolved}"
            stat = resolved.stat()
            info = {
                "name": resolved.name,
                "size": stat.st_size,
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                "type": "directory" if resolved.is_dir() else "file",
            }
            if resolved.is_file():
                ext = resolved.suffix.lower()
                info["extension"] = ext
                info["human_size"] = _human_size(stat.st_size)
                if ext in (".jpg", ".jpeg", ".png", ".tiff", ".webp"):
                    try:
                        from PIL import Image
                        from PIL.ExifTags import TAGS

                        img = Image.open(resolved)
                        info["image"] = {
                            "width": img.width,
                            "height": img.height,
                            "format": img.format,
                            "mode": img.mode,
                        }
                        exif = img._getexif()
                        if exif:
                            exif_info = {}
                            for tag_id, value in exif.items():
                                tag_name = TAGS.get(tag_id, tag_id)
                                if isinstance(value, bytes):
                                    value = value.decode("utf-8", errors="replace")[:200]
                                exif_info[tag_name] = str(value)[:200]
                            if exif_info:
                                info["exif"] = exif_info
                        img.close()
                    except ImportError:
                        info["image"] = "Pillow not available"
                    except Exception as e:
                        info["image_error"] = str(e)
                elif ext == ".json":
                    try:
                        data = json.loads(resolved.read_text(encoding="utf-8", errors="replace"))
                        info["json_keys"] = list(data.keys()) if isinstance(data, dict) else f"list[{len(data)} items]"
                    except Exception:
                        pass
            return json.dumps(info, indent=2, default=str)
        except Exception as e:
            return f"Error getting metadata: {e}"

    def batch_rename(self, directory: str, pattern: str, replacement: str, dry_run: bool = True) -> str:
        """Rename files matching a pattern in a directory. Dry run by default."""
        try:
            resolved = _safe_path(directory)
            if not resolved.is_dir():
                return f"Not a directory: {resolved}"
            renamed = []
            import re
            for entry in sorted(resolved.iterdir()):
                if entry.is_file() and re.search(pattern, entry.name):
                    new_name = re.sub(pattern, replacement, entry.name)
                    if new_name == entry.name:
                        continue
                    new_path = entry.parent / new_name
                    if not dry_run:
                        entry.rename(new_path)
                    renamed.append(f"  {entry.name}  ->  {new_name}")
            if not renamed:
                return f"No files matched pattern '{pattern}' in {resolved}"
            lines = [f"{'Would rename' if dry_run else 'Renamed'} {len(renamed)} file(s):"]
            lines.extend(renamed)
            return "\n".join(lines)
        except Exception as e:
            return f"Error renaming files: {e}"


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
