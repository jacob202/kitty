"""Which provider Kitty tries first, and which ones it skips entirely.

The fallback chain used to be a hardcoded tuple, so changing it meant editing
Python. This stores Jacob's preference in ``config/providers.json`` and merges
it against the live provider table on every read — a provider that disappears
from the table drops out of the saved order rather than breaking the chain, and
a newly added one lands at the end instead of vanishing.

Public API:
  load_preferences() -> dict
  save_preferences(order, disabled, *, known, active="auto") -> dict
  resolve_order(known, default_order) -> list[str]
  active_provider() -> str | None
  is_disabled(name) -> bool
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Sequence

from gateway.paths import CONFIG_DIR

logger = logging.getLogger("kitty.provider_prefs")

PROVIDER_PREFS_FILE = CONFIG_DIR / "providers.json"


def load_preferences() -> dict[str, Any]:
    """Read the saved preference. A missing or corrupt file means 'no preference'.

    Corruption is logged rather than raised: a bad preference file must not be
    able to take the whole LLM chain down.
    """
    if not PROVIDER_PREFS_FILE.exists():
        return {"order": [], "disabled": [], "active": "auto"}
    try:
        blob = json.loads(PROVIDER_PREFS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("provider preferences unreadable (%s) — falling back to defaults", exc)
        return {"order": [], "disabled": [], "active": "auto"}
    if not isinstance(blob, dict):
        logger.warning("provider preferences is not an object — falling back to defaults")
        return {"order": [], "disabled": [], "active": "auto"}
    order = blob.get("order")
    disabled = blob.get("disabled")
    active = blob.get("active", "auto")
    return {
        "order": [str(n) for n in order] if isinstance(order, list) else [],
        "disabled": [str(n) for n in disabled] if isinstance(disabled, list) else [],
        "active": str(active) if isinstance(active, str) and active else "auto",
    }


def save_preferences(
    order: Iterable[str],
    disabled: Iterable[str],
    *,
    known: Iterable[str],
    active: str = "auto",
) -> dict[str, Any]:
    """Persist a preference, rejecting provider names that don't exist.

    Silently dropping an unknown name would let a typo disable routing with no
    signal, so this raises instead.
    """
    known_set = set(known)
    order_list = [str(n) for n in order]
    disabled_list = [str(n) for n in disabled]

    unknown = sorted({n for n in [*order_list, *disabled_list] if n not in known_set})
    if unknown:
        raise ValueError(f"unknown provider(s): {', '.join(unknown)}")

    if len(set(order_list)) != len(order_list):
        raise ValueError("provider order contains duplicates")

    if set(disabled_list) >= known_set and known_set:
        raise ValueError("cannot disable every provider — Kitty would have nothing to call")

    active = str(active or "auto")
    if active != "auto" and active not in known_set:
        raise ValueError(f"unknown active provider: {active}")
    if active in set(disabled_list):
        raise ValueError(f"active provider {active!r} cannot also be disabled")

    payload = {"order": order_list, "disabled": sorted(set(disabled_list)), "active": active}
    PROVIDER_PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROVIDER_PREFS_FILE.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def resolve_order(known: Sequence[str], default_order: Sequence[str]) -> list[str]:
    """Effective try-order: saved preference first, then anything it didn't mention.

    Disabled providers are excluded. Names in the saved order that are no longer
    in the table are dropped.
    """
    prefs = load_preferences()
    disabled = set(prefs["disabled"])
    known_set = set(known)

    ordered = [n for n in prefs["order"] if n in known_set and n not in disabled]
    seen = set(ordered)

    for name in default_order:
        if name in known_set and name not in seen and name not in disabled:
            ordered.append(name)
            seen.add(name)

    # A provider present in the table but named by neither the preference nor the
    # default order still belongs in the chain — last, but reachable.
    for name in known:
        if name not in seen and name not in disabled:
            ordered.append(name)
            seen.add(name)

    return ordered


def active_provider() -> str | None:
    """Exact provider selected by Jacob, or None for normal LiteLLM + fallback routing."""
    active = load_preferences().get("active", "auto")
    return None if active == "auto" else str(active)


def is_disabled(name: str) -> bool:
    return name in set(load_preferences()["disabled"])
