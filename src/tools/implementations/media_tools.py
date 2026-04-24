"""BaseTool wrapper for image generation (Draw Things)."""

from __future__ import annotations

from typing import Any

from src.tools.base import BaseTool, ToolResult
from src.tools.image_gen import DrawThingsGenerator

__all__ = ["ImageGenTool"]


class ImageGenTool(BaseTool):
    """Wrapper around DrawThingsGenerator for AI image generation."""

    @property
    def name(self) -> str:
        return "image_gen"

    @property
    def command(self) -> str:
        return "/imagine"

    @property
    def description(self) -> str:
        return "Generate an image using Draw Things (local Stable Diffusion)."

    def execute(self, **kwargs: Any) -> ToolResult:
        prompt = kwargs.get("prompt") or kwargs.get("text") or ""
        if not prompt:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error="No prompt provided for image generation")
        try:
            gen = DrawThingsGenerator()
            result = gen.generate(
                prompt=prompt,
                trigger_word=kwargs.get("trigger_word", ""),
                negative_prompt=kwargs.get("negative_prompt", "bad anatomy, blurry"),
            )
            return ToolResult(ok=True, tool=self.name, args=kwargs, result={"output": result})
        except Exception as e:
            return ToolResult(ok=False, tool=self.name, args=kwargs, error=str(e))
