"""``generate_until`` tool — criteria-verified generation loop.

Wraps the verification loop in ``mcp/imagen/verify.py`` as an MCP tool so
Claude sessions can run: generate → score → keep best → stop early.
"""

from __future__ import annotations

from mcp.imagen.logger import log
from mcp.imagen.verify import generate_until as _generate_until
from mcp.server.fastmcp import Image


def generate_until(
    prompt: str,
    criteria_name: str = "default",
    engine: str = "",
    max_attempts: int = 8,
    keep: int = 3,
    private: bool = False,
) -> list:
    """Generate an image, score it against criteria, and iterate until one passes.

    Each attempt is scored on mechanical checks (resolution, blank detection),
    face-match against a reference set, and a vision-model rubric. When a
    candidate passes all hard criteria the loop stops early. The best ``keep``
    candidates across all attempts are returned.

    Every attempt is logged to ``~/Pictures/kitty-gen/runs/<run-id>/`` with
    scores and seeds so good results are reproducible.

    Args:
        prompt: What to generate. Be specific about subject, setting, lighting.
        criteria_name: Name of a criteria file in ``config/imagen/criteria/``.
                       Defaults to "default" (soft rubric only).
        engine: Generation engine. Default from settings (nano_banana).
                Use "drawthings" for local generation.
        max_attempts: Maximum generation rounds (1-20). Default 8.
        keep: Number of best candidates to return (1-5). Default 3.
        private: When True, refuses cloud engines (nano_banana, imagen4, dalle).
                 Use this for personal creative prompts — forces a local engine.

    Returns:
        Images (inline) plus a summary of scores and paths.
    """
    max_attempts = max(1, min(max_attempts, 20))
    keep = max(1, min(keep, 5))

    try:
        results = _generate_until(
            prompt=prompt,
            criteria_name=criteria_name,
            engine=engine,
            max_attempts=max_attempts,
            keep=keep,
            private=private,
        )
    except ValueError as e:
        log.warning("generate_until rejected: %s", str(e)[:200])
        return [str(e)]

    if not results:
        return ["No images were generated in the allotted attempts."]

    out: list = []
    for i, r in enumerate(results):
        scores = r["scores"]
        score_str = ", ".join(f"{k}={v:.2f}" for k, v in scores.items())
        img = Image(data=r["image_data"], format="png")
        out.append(img)
        out.append(
            f"Result {i + 1}: attempt {r['attempt']}, passed={r['passed']}, "
            f"scores: {{{score_str}}}\nSaved to: {r['saved_path']}"
        )

    return out
