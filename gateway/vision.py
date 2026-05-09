"""Claude Sonnet vision — describes schematics and technical images."""
from __future__ import annotations
import base64
import logging
import os

import anthropic

logger = logging.getLogger("kitty.vision")

_VISION_MODEL = "claude-sonnet-4-5"
_VISION_PROMPT = (
    "Describe this technical image in detail. "
    "List all visible components, labels, connections, values, and specifications. "
    "If it is a schematic or circuit board, identify each component and its role."
)


def describe_schematic(image_bytes: bytes, media_type: str = "image/png") -> str:
    """Return a detailed description of a technical image using Claude Sonnet vision.

    Returns empty string (with a warning) when ANTHROPIC_API_KEY is not set or API fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping vision description")
        return ""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        b64 = base64.standard_b64encode(image_bytes).decode()
        response = client.messages.create(
            model=_VISION_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": _VISION_PROMPT},
                    ],
                }
            ],
        )
        return response.content[0].text
    except Exception as exc:
        logger.warning("Vision description failed: %s", exc)
        return ""
