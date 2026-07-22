#!/usr/bin/env python3
"""Generate an image via the gateway's ComfyUI-backed endpoint.

Used by the /image-gen skill. Model/style selection from keywords
("portrait", "sdxl", "explicit", etc.) happens server-side in
gateway/image_gen.py — this script just checks availability, submits
the prompt, and reports the result.
"""

from __future__ import annotations

import os
import sys

import requests

GATEWAY_BASE = os.environ.get("KITTY_GATEWAY_URL", "http://127.0.0.1:8000")
AUTH_HEADERS = {"Authorization": f"Bearer {os.environ.get('GATEWAY_SECRET', 'kitty')}"}


def main(argv: list[str]) -> int:
    prompt = " ".join(argv).strip()
    if not prompt:
        print("Nothing to generate: give me a prompt.", file=sys.stderr)
        return 2

    status = requests.get(f"{GATEWAY_BASE}/image/status", headers=AUTH_HEADERS, timeout=5.0)
    status.raise_for_status()
    if not status.json().get("available"):
        print("ComfyUI isn't running — start it before generating.", file=sys.stderr)
        return 1

    print("Generating (2-5 min on M1, this will block until done)...")
    resp = requests.post(
        f"{GATEWAY_BASE}/image/generate",
        headers=AUTH_HEADERS,
        json={"prompt": prompt, "engine": "comfyui"},
        timeout=600.0,
    )
    resp.raise_for_status()
    result = resp.json()
    print(f"Done: {result['filename']} (job {result['job_id']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
