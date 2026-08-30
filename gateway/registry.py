from __future__ import annotations

import os

SPECIALIST_REGISTRY = {
    "electronics": "4dd4a44d-6ec1-4378-8126-06cae382d0c2",
    "audio_repair": "ac05f7c1-f341-449c-b520-80882fda3a8e",
    "sask_watchdog": os.environ.get("KITTY_SASK_WATCHDOG_COLLECTION_ID", "").strip(),
}


def get_collection_id(name: str) -> str:
    normalized = (name or "").strip()
    if normalized not in SPECIALIST_REGISTRY:
        raise KeyError(f"Unknown specialist: {name}")

    collection_id = SPECIALIST_REGISTRY[normalized]
    if not collection_id:
        raise KeyError(f"Specialist collection ID is not configured: {name}")
    return collection_id


def list_specialists() -> list[str]:
    return list(SPECIALIST_REGISTRY.keys())
