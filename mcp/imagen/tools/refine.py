"""Refine tool — autonomous generate → critique → edit loop.

Generates an image, then a vision model checks it against the target and
either approves it or hands back one concrete edit, which is applied before
the next check.
"""

from __future__ import annotations

import os

from mcp.imagen.config import settings
from mcp.imagen.engines.base import RefusalError
from mcp.imagen.engines.nano_banana import NanoBananaEngine
from mcp.imagen.io import refusal_text, save_image
from mcp.server.fastmcp import Image


def _gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY (or GOOGLE_API_KEY) in your environment")
    from google import genai

    return genai.Client(api_key=api_key)


def refine_image(prompt: str, target: str = "", max_rounds: int = 3) -> list:
    """Generate an image, then automatically critique and re-edit it until it matches.

    Args:
        prompt: What to generate initially.
        target: The success criteria to judge against. Defaults to ``prompt``.
        max_rounds: Max critique/edit rounds (1-5). Default 3.

    Returns:
        The final image (inline), the saved path, and the round-by-round critique trail.
    """
    from google.genai import types

    goal = target.strip() or prompt
    engine = NanoBananaEngine()
    client = _gemini_client()

    try:
        data = engine.generate(prompt + settings.photoreal_suffix)
    except RefusalError as e:
        return [f"Initial generation failed. Model said: {e}"]

    trail: list[str] = []
    rounds = max(1, min(max_rounds, 5))

    for i in range(rounds):
        critique = client.models.generate_content(
            model=settings.gemini_vision_model,
            contents=[
                types.Part.from_bytes(data=data, mime_type="image/png"),
                types.Part.from_text(
                    text=(
                        f"Target: {goal}\n\n"
                        "Judge whether this image matches the target. If it is a good match, "
                        "reply with exactly the word DONE. Otherwise reply with ONE specific, "
                        "actionable edit instruction (and nothing else) to bring it closer."
                    )
                ),
            ],
        )
        verdict = (refusal_text(critique) or "").strip()

        if verdict.upper().startswith("DONE") or not verdict:
            trail.append(f"Round {i + 1}: approved.")
            break

        trail.append(f"Round {i + 1}: {verdict}")
        try:
            data = engine.edit_inline(data, verdict)
        except RefusalError as e:
            trail.append(f"Round {i + 1}: edit failed ({e}); keeping previous.")
            break

    path = save_image(data, prefix="refined")
    return [
        Image(data=data, format="png"),
        f"Saved to: {path}\n\nCritique trail:\n" + "\n".join(trail),
    ]
