"""Image reference quality checks — local validation without external models."""
from __future__ import annotations

import io
from dataclasses import dataclass, field

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None  # type: ignore


@dataclass
class QualityCheck:
    passed: bool
    severity: str  # "ok" | "warning" | "blocker"
    message: str


@dataclass
class QualityResult:
    checks: list[QualityCheck] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    file_size: int | None = None
    format: str | None = None

    @property
    def has_blockers(self) -> bool:
        return any(c.severity == "blocker" for c in self.checks)

    @property
    def has_warnings(self) -> bool:
        return any(c.severity == "warning" for c in self.checks)

    @property
    def is_perfect(self) -> bool:
        return all(c.passed for c in self.checks)

    def summary(self) -> str:
        if not self.checks:
            return "no checks performed"
        if self.has_blockers:
            blockers = [c for c in self.checks if c.severity == "blocker"]
            return "; ".join(c.message for c in blockers)
        if self.has_warnings:
            warnings = [c for c in self.checks if c.severity == "warning"]
            return "; ".join(c.message for c in warnings[:2])
        return "reference looks good"

    def advice(self) -> list[str]:
        return [c.message for c in self.checks if c.severity in ("warning", "blocker")]


MIN_WIDTH = 256
MIN_HEIGHT = 256
IDEAL_WIDTH = 512
IDEAL_HEIGHT = 512
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
BLUR_THRESHOLD = 50  # Laplacian variance below this = blurry


def check_reference_image(data: bytes) -> QualityResult:
    """Validate a reference image for character use. Never raises on malformed data."""
    result = QualityResult(file_size=len(data))
    if not HAS_PIL:
        result.checks.append(
            QualityCheck(False, "warning", "cannot check image quality — Pillow not installed")
        )
        return result

    try:
        img = Image.open(io.BytesIO(data))
        result.format = img.format
        result.width, result.height = img.size
    except Exception:
        result.checks.append(
            QualityCheck(False, "blocker", "could not open image — file may be corrupted")
        )
        return result

    result.checks.extend(_check_dimensions(img.size))
    result.checks.extend(_check_format(img.format))
    result.checks.append(_check_filesize(len(data)))
    result.checks.append(_check_blur(data))

    return result


def _check_dimensions(size: tuple[int, int]) -> list[QualityCheck]:
    w, h = size
    checks: list[QualityCheck] = []

    if w < MIN_WIDTH or h < MIN_HEIGHT:
        checks.append(
            QualityCheck(False, "blocker",
                         f"image is too small ({w}×{h}). minimum is {MIN_WIDTH}×{MIN_HEIGHT}.")
        )
        return checks

    if w < IDEAL_WIDTH or h < IDEAL_HEIGHT:
        checks.append(
            QualityCheck(True, "warning",
                         f"image is below the recommended {IDEAL_WIDTH}×{IDEAL_HEIGHT}. "
                         "likeness may be weaker.")
        )

    # Check for extreme crops (face too small relative to image)
    aspect = max(w, h) / max(min(w, h), 1)
    if aspect > 3:
        checks.append(
            QualityCheck(True, "warning",
                         "image is very wide or tall. a more centered portrait works better.")
        )

    return checks


def _check_format(fmt: str | None) -> list[QualityCheck]:
    if not fmt:
        return [QualityCheck(False, "blocker", "could not determine image format")]
    supported = {"PNG", "JPEG", "WEBP", "BMP", "TIFF"}
    if fmt.upper() not in supported:
        return [QualityCheck(False, "blocker",
                             f"unsupported format {fmt!r}. use PNG, JPEG, or WEBP")]
    if fmt.upper() == "BMP":
        return [QualityCheck(True, "warning", "BMP format works but uses more storage. PNG is preferred")]
    return [QualityCheck(True, "ok", "format supported")]


def _check_filesize(size: int) -> QualityCheck:
    if size > MAX_FILE_SIZE:
        return QualityCheck(False, "blocker",
                            f"file too large ({size // (1024*1024)} MB). max is 20 MB")
    if size > 5 * 1024 * 1024:
        return QualityCheck(True, "warning",
                            "file is over 5 MB. consider a smaller image for faster uploads")
    return QualityCheck(True, "ok", "file size acceptable")


def _check_blur(data: bytes) -> QualityCheck:
    """Laplacian variance blur detection. Higher variance = sharper image."""
    try:
        import io as _io

        import numpy as np
        from PIL import Image as PILImg
        from PIL import ImageFilter as PILFilter

        img = PILImg.open(_io.BytesIO(data)).convert("L")
        laplacian = np.array(
            img.filter(PILFilter.Kernel(
                (3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=0
            )),
            dtype=np.float64,
        )
        variance = float(np.var(laplacian))
        if variance < 30:
            return QualityCheck(True, "warning",
                                "image appears very blurry. use a sharper photo.")
        if variance < BLUR_THRESHOLD:
            return QualityCheck(True, "warning",
                                "image is somewhat soft. a sharper photo would improve likeness.")
        return QualityCheck(True, "ok", f"sharpness good (variance: {variance:.0f})")
    except ImportError:
        return QualityCheck(True, "ok", "blur check skipped — numpy not installed")
    except Exception:
        return QualityCheck(True, "ok", "blur check unavailable")
