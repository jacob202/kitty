#!/usr/bin/env python3
"""One-shot OpenViking shadow retrieval through Kitty's real context seam."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway import openviking_shadow as ovs  # noqa: E402


def _safe_hit(hit: ovs.Hit) -> dict[str, Any]:
    return {"uri": hit.uri, "score": hit.score, "content_length": len(hit.content)}


async def run_shadow_canary(query: str) -> dict[str, Any]:
    """Call context_block once in shadow mode and capture its real retrieval receipt."""
    original_mode = os.environ.get("KITTY_OPENVIKING_MODE")
    original_retrieve = ovs.retrieve
    captured: dict[str, ovs.RetrievalResult] = {}

    async def capturing_retrieve(*args: Any, **kwargs: Any) -> ovs.RetrievalResult:
        result = await original_retrieve(*args, **kwargs)
        captured["result"] = result
        return result

    os.environ["KITTY_OPENVIKING_MODE"] = "shadow"
    ovs.retrieve = capturing_retrieve
    started = time.perf_counter()
    try:
        block = await ovs.context_block(query)
    finally:
        ovs.retrieve = original_retrieve
        if original_mode is None:
            os.environ.pop("KITTY_OPENVIKING_MODE", None)
        else:
            os.environ["KITTY_OPENVIKING_MODE"] = original_mode

    result = captured.get("result")
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if block is not None:
        return {"ok": False, "mode": "shadow", "injected": True, "error": "shadow context was injected"}
    if result is None:
        return {"ok": False, "mode": "shadow", "injected": False, "error": "retrieval did not complete"}
    return {
        "ok": True,
        "mode": "shadow",
        "injected": False,
        "retrievals": 1,
        "hits": len(result.hits),
        "latency_ms": round(result.latency_ms, 1),
        "wall_ms": round(elapsed_ms, 1),
        "hit_details": [_safe_hit(hit) for hit in result.hits],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default="KittyBuilder ownership collision")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    result = asyncio.run(run_shadow_canary(args.query))
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
