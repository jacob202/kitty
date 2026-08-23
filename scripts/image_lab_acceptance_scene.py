#!/usr/bin/env python3
"""Two-character acceptance-scene builder for the FLUX.2 Image Lab benchmark gate.

ADR 0040 lists "two recurring identities stay correctly assigned in a
one-pass scene" as an unproven evidence gate, and says to run that benchmark
"as soon as the compiler, one hosted FLUX.2 adapter, and the minimum
typed-reference/cast path ... exist." All three now exist on ``main``
(flux2_compiler, the BFL Direct transport, and typed cast/reference dispatch
in ``gateway/routes/extended.py``) — what was missing was a way to actually
build the two-character ``ImagePlan`` that exercises that path.

This script persists exactly that plan through the real, already-approved
trust boundary (``gateway.image_plans.persist_plan`` -> the same
``/studio/generate`` dispatch every other approved plan goes through). It
adds no new architecture, no new engine, and performs no network call
itself — real generation only happens when ``--dispatch`` is passed, and
that reaches the existing hosted FLUX.2 transport (gateway/flux2_transport.py),
which spends real money against ``BFL_API_KEY``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any


def build_two_character_plan(
    session_id: str,
    *,
    prompt: str,
    character_a_id: str,
    character_a_ref: Path | str,
    character_b_id: str,
    character_b_ref: Path | str,
    character_a_name: str | None = None,
    character_b_name: str | None = None,
    quality: str = "fast",
) -> Any:
    """Persist an approved two-character txt2img ``ImagePlan`` and return it.

    ``character_a``/``character_b`` need no pre-existing ``Character`` row —
    the typed cast/reference dispatch path in ``extended.py`` resolves
    references from the plan's own durable provenance, not from
    ``gateway.image_characters``. Positions are fixed left/right so the
    identity-assignment scorer (``gateway.image_scorers.make_assignment_scorer``)
    has a stable cast_slot -> position mapping to check the render against.
    """
    from gateway.image_plans import persist_plan

    character_a_ref = Path(character_a_ref)
    character_b_ref = Path(character_b_ref)
    for label, path in (("character_a_ref", character_a_ref), ("character_b_ref", character_b_ref)):
        if not path.is_file():
            raise FileNotFoundError(f"{label} does not exist: {path}")
    if character_a_id == character_b_id:
        raise ValueError("character_a_id and character_b_id must be distinct")
    if character_a_ref.resolve() == character_b_ref.resolve():
        raise ValueError(
            "character_a_ref and character_b_ref point at the same file — a "
            "two-character identity-assignment test against one photo would "
            "silently prove nothing"
        )

    plan_dict = {
        "original_prompt": prompt,
        "refined_prompt": prompt,
        "content_lane": "safe",
        "consent_basis": None,
        "adult_confirmed": False,
        "references": [
            {
                "reference_id": "acceptance-ref-a",
                "character_id": character_a_id,
                "path": str(character_a_ref),
                "name": character_a_name or character_a_id,
            },
            {
                "reference_id": "acceptance-ref-b",
                "character_id": character_b_id,
                "path": str(character_b_ref),
                "name": character_b_name or character_b_id,
            },
        ],
        "intent": {
            "intent_version": 1,
            "operation": "txt2img",
            "scene": {},
            "target": {},
            "quality_request": {"tier": quality},
            "budget_request": {},
            "requested_changes": [],
            "protected_traits": [],
            "cast": [
                {
                    "slot_id": "left_slot",
                    "character_id": character_a_id,
                    "display_name": character_a_name,
                    "position": "left",
                    "depth_order": 1,
                },
                {
                    "slot_id": "right_slot",
                    "character_id": character_b_id,
                    "display_name": character_b_name,
                    "position": "right",
                    "depth_order": 2,
                },
            ],
            "references": [
                {
                    "reference_id": "acceptance-ref-a",
                    "role": "identity",
                    "cast_slot": "left_slot",
                    "weight": 1.0,
                },
                {
                    "reference_id": "acceptance-ref-b",
                    "role": "identity",
                    "cast_slot": "right_slot",
                    "weight": 1.0,
                },
            ],
            "content_lane": "safe",
            "consent_basis": None,
            "adult_confirmed": False,
            "privacy_required": False,
        },
    }
    return persist_plan(session_id, plan_dict, operation="txt2img")


async def _dispatch(plan_id: str, session_id: str, *, quality: str) -> Any:
    from gateway.routes.extended import StudioGenerateRequest, studio_generate

    return await studio_generate(
        StudioGenerateRequest(prompt="", quality=quality, plan_id=plan_id, session_id=session_id)
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--character-a-id", required=True)
    parser.add_argument("--character-a-ref", required=True, type=Path)
    parser.add_argument("--character-a-name")
    parser.add_argument("--character-b-id", required=True)
    parser.add_argument("--character-b-ref", required=True, type=Path)
    parser.add_argument("--character-b-name")
    parser.add_argument("--quality", choices=["fast", "quality", "maximum"], default="fast")
    parser.add_argument("--session-title", default="Image Lab acceptance benchmark")
    parser.add_argument(
        "--dispatch",
        action="store_true",
        help=(
            "Actually generate through the hosted FLUX.2 transport (real spend "
            "against BFL_API_KEY). Without this flag the plan is only built and "
            "persisted so you can inspect it first."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    from gateway.image_sessions import create_session

    session = create_session(title=args.session_title)
    plan = build_two_character_plan(
        session.session_id,
        prompt=args.prompt,
        character_a_id=args.character_a_id,
        character_a_ref=args.character_a_ref,
        character_a_name=args.character_a_name,
        character_b_id=args.character_b_id,
        character_b_ref=args.character_b_ref,
        character_b_name=args.character_b_name,
        quality=args.quality,
    )
    print(f"session_id={session.session_id}")
    print(f"plan_id={plan.plan_id}")

    if not args.dispatch:
        print("Plan persisted, not dispatched (pass --dispatch to actually generate).")
        return 0

    import os

    if not os.environ.get("BFL_API_KEY"):
        print("BFL_API_KEY is not set; cannot dispatch.", file=sys.stderr)
        return 1

    result = asyncio.run(_dispatch(plan.plan_id, session.session_id, quality=args.quality))
    print(result if isinstance(result, (str, dict)) else vars(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
