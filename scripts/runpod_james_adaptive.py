#!/usr/bin/env python3
"""Run a larger James portrait search with capacity-aware RunPod fallback."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.runpod_control import (  # noqa: E402
    RunPodAmbiguousCreateError,
    RunPodApiError,
    RunPodBudgetError,
)
from gateway.runpod_control import (
    RunPodControlClient as BaseRunPodControlClient,
)
from scripts import runpod_james_batch as batch  # noqa: E402

GPU_CANDIDATES = (
    "NVIDIA L4",
    "NVIDIA RTX A5000",
    "NVIDIA GeForce RTX 3090",
    "NVIDIA GeForce RTX 3090 Ti",
    "NVIDIA RTX A4500",
    "NVIDIA RTX A4000",
    "NVIDIA GeForce RTX 4080 SUPER",
    "NVIDIA GeForce RTX 4080",
    "NVIDIA GeForce RTX 4070 Ti",
    "NVIDIA GeForce RTX 4090",
    "NVIDIA RTX A6000",
    "NVIDIA RTX 4000 Ada Generation",
    "NVIDIA RTX 5000 Ada Generation",
)

IDENTITY = (
    "Photorealistic candid phone photo of the same adult man: short dense salt-and-pepper "
    "hair brushed slightly forward, dark strong eyebrows, green-grey eyes, light olive skin, "
    "broad oval face, medium straight nose, short dark stubble with a little grey, softly rounded "
    "jaw, stocky natural build, broad chest and shoulders, realistic body hair, ordinary human "
    "asymmetry, recognizable consistent facial identity."
)

SCENES = (
    "Tight head-and-shoulders portrait outdoors near leafy trees, relaxed half-smile, direct eye contact.",
    "Chest-up portrait beside a bright window in an ordinary home, neutral expression turning into a small smile.",
    "Candid kitchen snapshot while holding a coffee mug, looking toward the camera, warm practical lighting.",
    "Half-body portrait at a lakeshore in daylight wearing a simple dark fitted T-shirt, relaxed posture.",
    "Casual seated portrait on a patio, slight three-quarter angle, calm confident expression.",
    "Full-body park snapshot in jeans and a charcoal T-shirt, stocky proportions preserved, natural stance.",
)

CAMERA_VARIANTS = (
    "Recent iPhone main camera, 35mm-equivalent view, realistic pores, mild computational sharpening, no retouching.",
    "Natural overcast daylight, 50mm-equivalent framing, shallow but believable depth of field, true skin texture.",
    "Soft morning sunlight, documentary photography, ordinary color science, subtle sensor noise, unposed.",
    "Golden-hour side light, realistic exposure and facial detail, no glamour styling, no synthetic skin.",
    "Open shade with soft catchlights, crisp eyes, natural facial proportions, believable phone-camera rendering.",
    "Indoor mixed window and lamp light, realistic white balance, slight lens softness, intimate candid photo.",
)

PROMPTS = tuple(
    f"{IDENTITY} {scene} {camera}"
    for scene in SCENES
    for camera in CAMERA_VARIANTS
)


class AdaptiveRunPodControlClient(BaseRunPodControlClient):
    """Expand GPU choices and retry only definite capacity rejections."""

    async def create_image_pod(self, *args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
        rounds = max(1, int(os.environ.get("RUNPOD_CAPACITY_RETRY_ROUNDS", "8")))
        delay = max(1.0, float(os.environ.get("RUNPOD_CAPACITY_RETRY_SECONDS", "30")))
        clouds = tuple(
            value.strip().upper()
            for value in os.environ.get("RUNPOD_CLOUD_TYPES", "COMMUNITY,SECURE").split(",")
            if value.strip()
        )
        if not clouds:
            clouds = ("COMMUNITY", "SECURE")

        last_errors: list[str] = []
        for round_index in range(1, rounds + 1):
            for cloud in clouds:
                attempt_kwargs = dict(kwargs)
                attempt_kwargs["gpu_type_ids"] = GPU_CANDIDATES
                attempt_kwargs["cloud_type"] = cloud
                try:
                    return await super().create_image_pod(*args, **attempt_kwargs)
                except RunPodAmbiguousCreateError:
                    raise
                except RunPodBudgetError:
                    raise
                except RunPodApiError as exc:
                    message = str(exc)
                    if "rejected every requested GPU candidate" not in message:
                        raise
                    last_errors.append(f"round {round_index} {cloud}: {message}")
            if round_index < rounds:
                await asyncio.sleep(delay)

        detail = " | ".join(last_errors[-4:])
        raise RunPodApiError(
            f"RunPod capacity remained unavailable after {rounds} rounds across {clouds}: {detail}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, default=36)
    parser.add_argument("--output-dir", default="runtime-data/runpod-james")
    parser.add_argument("--accept-charges", action="store_true")
    args = parser.parse_args()
    if not args.accept_charges:
        parser.error("--accept-charges is required for the live batch")
    if args.attempts < 1 or args.attempts > len(PROMPTS):
        parser.error(f"--attempts must be between 1 and {len(PROMPTS)}")
    return args


async def run(args: argparse.Namespace) -> Path:
    batch.DEFAULT_PROMPTS = PROMPTS
    batch.RunPodControlClient = AdaptiveRunPodControlClient
    inner_args = argparse.Namespace(
        attempts=args.attempts,
        output_dir=args.output_dir,
        accept_charges=True,
    )
    return await batch.run(inner_args)


def main() -> int:
    try:
        path = asyncio.run(run(parse_args()))
    except Exception as exc:
        print(f"Adaptive James batch failed: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
