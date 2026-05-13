from __future__ import annotations
import base64
import logging
import os
from pathlib import Path

logger = logging.getLogger("kitty.vision")

from gateway.llm_client import call_llm


def analyze_file(path: Path) -> str:
    """Wrapper for backward compatibility in clerk.py."""
    with open(path, "rb") as f:
        return describe_schematic(f.read())

_VISION_MODEL = "kitty-smart"
_VISION_PROMPT = (
    "Describe this technical image in detail. "
    "List all visible components, labels, connections, values, and specifications. "
    "If it is a schematic or circuit board, identify each component and its role."
)


def describe_schematic(image_bytes: bytes, media_type: str = "image/png") -> str:
    """Return a detailed description of a technical image using unified LLM client.
    """
    try:
        b64 = base64.standard_b64encode(image_bytes).decode()

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 1024,
            "temperature": 0.1,
            "timeout": 60,
        }

        return call_llm(model=_VISION_MODEL, **payload)
    except Exception as exc:
        logger.warning("Vision description failed: %s", exc)
        return ""
