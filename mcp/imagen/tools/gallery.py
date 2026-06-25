"""Gallery tool — HTML contact sheet of all generated images."""

from __future__ import annotations

import html

from mcp.imagen.config import settings


def make_gallery() -> str:
    """Build an HTML contact sheet of every image in the output dir, newest first.

    Returns:
        Path to the generated gallery.html (open it in a browser).
    """
    if not settings.output_dir.exists():
        return "No images yet — generate something first."

    pngs = sorted(
        (p for p in settings.output_dir.glob("*.png") if p.name != settings.avatar_path.name),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not pngs:
        return "No images yet — generate something first."

    cards = "\n".join(
        f'<figure><img src="{html.escape(p.name)}" loading="lazy">'
        f"<figcaption>{html.escape(p.name)}</figcaption></figure>"
        for p in pngs
    )
    doc = (
        "<!doctype html><meta charset=utf-8><title>kitty-gen gallery</title>"
        "<style>body{background:#111;color:#eee;font-family:system-ui;margin:1rem}"
        "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}"
        "figure{margin:0}img{width:100%;border-radius:8px;display:block}"
        "figcaption{font-size:11px;color:#888;word-break:break-all;margin-top:4px}</style>"
        f"<h1>kitty-gen — {len(pngs)} images</h1><main>{cards}</main>"
    )
    gallery = settings.output_dir / "gallery.html"
    gallery.write_text(doc, encoding="utf-8")
    return f"Gallery written to {gallery} ({len(pngs)} images). Open it in a browser."
