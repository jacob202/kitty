"""Provider catalogue discovery for Kitty model roles.

Discovery answers "what changed?" It never answers "switch production now." New
models are stored as candidates with provider metadata and suggested role tags;
`config/model_roles.json` remains unchanged until representative evaluations
meet the promotion policy.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import httpx

from gateway.operating_policy import load_model_policy
from gateway.paths import DATA_DIR

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
DISCOVERY_DIR = DATA_DIR / "model-discovery"
OPENROUTER_SNAPSHOT = DISCOVERY_DIR / "openrouter.json"


class ModelDiscoveryError(RuntimeError):
    """The provider catalogue or local snapshot cannot be trusted."""


@dataclass(frozen=True)
class DiscoveryResult:
    provider: str
    checked_at: str
    total_models: int
    new_models: tuple[dict[str, Any], ...]
    removed_model_ids: tuple[str, ...]
    snapshot_path: str
    promotion_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "checked_at": self.checked_at,
            "total_models": self.total_models,
            "new_models": list(self.new_models),
            "removed_model_ids": list(self.removed_model_ids),
            "snapshot_path": self.snapshot_path,
            "promotion_performed": self.promotion_performed,
        }


def discovery_due(
    *,
    snapshot_path: Path = OPENROUTER_SNAPSHOT,
    now: datetime | None = None,
    policy: Mapping[str, Any] | None = None,
) -> bool:
    """Return true when no valid snapshot exists or its cadence has elapsed."""
    current = now or datetime.now(timezone.utc)
    model_policy = dict(policy or load_model_policy())
    cadence = timedelta(days=int(model_policy["discovery"]["cadence_days"]))
    snapshot = load_snapshot(snapshot_path, allow_missing=True)
    if snapshot is None:
        return True
    try:
        checked_at = datetime.fromisoformat(str(snapshot["checked_at"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ModelDiscoveryError(
            f"snapshot has invalid checked_at: {snapshot_path}"
        ) from exc
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    return current >= checked_at + cadence


def discover_openrouter(
    *,
    snapshot_path: Path = OPENROUTER_SNAPSHOT,
    now: datetime | None = None,
    fetcher: Callable[[], Mapping[str, Any]] | None = None,
) -> DiscoveryResult:
    """Fetch, normalize, diff, and atomically save the OpenRouter catalogue."""
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    checked_at_text = checked_at.isoformat()
    previous = load_snapshot(snapshot_path, allow_missing=True)
    payload = dict(fetcher() if fetcher is not None else _fetch_openrouter())
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise ModelDiscoveryError("OpenRouter catalogue is missing a data array")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ModelDiscoveryError("OpenRouter catalogue contains a non-object row")
        model = _normalize_model(raw)
        model_id = model["id"]
        if model_id in seen:
            raise ModelDiscoveryError(
                f"OpenRouter catalogue repeats model id {model_id!r}"
            )
        seen.add(model_id)
        normalized.append(model)
    normalized.sort(key=lambda item: item["id"])

    previous_models = {
        item["id"]: item
        for item in (previous or {}).get("models", [])
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    current_models = {item["id"]: item for item in normalized}
    new_ids = sorted(set(current_models) - set(previous_models))
    removed_ids = tuple(sorted(set(previous_models) - set(current_models)))
    new_models = tuple(current_models[model_id] for model_id in new_ids)

    snapshot = {
        "schema_version": 1,
        "provider": "openrouter",
        "checked_at": checked_at_text,
        "source": OPENROUTER_MODELS_URL,
        "models": normalized,
        "new_model_ids": new_ids,
        "removed_model_ids": list(removed_ids),
        "promotion_performed": False,
    }
    _atomic_json(snapshot_path, snapshot)
    return DiscoveryResult(
        provider="openrouter",
        checked_at=checked_at_text,
        total_models=len(normalized),
        new_models=new_models,
        removed_model_ids=removed_ids,
        snapshot_path=str(snapshot_path),
    )


def load_snapshot(
    path: Path = OPENROUTER_SNAPSHOT,
    *,
    allow_missing: bool = False,
) -> dict[str, Any] | None:
    if not path.exists():
        if allow_missing:
            return None
        raise ModelDiscoveryError(f"model discovery snapshot does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelDiscoveryError(
            f"model discovery snapshot is unreadable: {exc}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ModelDiscoveryError(f"unsupported model discovery snapshot: {path}")
    if payload.get("promotion_performed") is not False:
        raise ModelDiscoveryError(
            "discovery snapshots may not claim or perform model promotion"
        )
    models = payload.get("models")
    if not isinstance(models, list):
        raise ModelDiscoveryError("model discovery snapshot models must be an array")
    return payload


def _fetch_openrouter() -> Mapping[str, Any]:
    headers = {"Accept": "application/json"}
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        response = httpx.get(
            OPENROUTER_MODELS_URL,
            headers=headers,
            timeout=30,
            follow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ModelDiscoveryError(f"OpenRouter model discovery failed: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ModelDiscoveryError("OpenRouter model discovery returned non-object JSON")
    return payload


def _normalize_model(raw: Mapping[str, Any]) -> dict[str, Any]:
    model_id = raw.get("id")
    if not isinstance(model_id, str) or not model_id.strip():
        raise ModelDiscoveryError("OpenRouter model row has no id")
    architecture = raw.get("architecture")
    if not isinstance(architecture, Mapping):
        architecture = {}
    pricing = raw.get("pricing")
    if not isinstance(pricing, Mapping):
        pricing = {}
    supported = raw.get("supported_parameters")
    if not isinstance(supported, list):
        supported = []
    input_modalities = _string_values(
        architecture.get("input_modalities") or architecture.get("modality")
    )
    output_modalities = _string_values(architecture.get("output_modalities"))
    name = str(raw.get("name") or model_id)
    description = str(raw.get("description") or "")
    searchable = f"{model_id} {name} {description}".casefold()

    suggested_roles: list[str] = []
    if "image" in input_modalities or "vision" in searchable:
        suggested_roles.append("vision")
    if any(term in searchable for term in ("coder", "coding", "code")):
        suggested_roles.append("code")
    if any(
        term in searchable
        for term in ("reasoning", "thinking", "r1", "reasoner")
    ):
        suggested_roles.append("think")
    if not suggested_roles:
        suggested_roles.append("fast")

    return {
        "id": model_id.strip(),
        "name": name,
        "created": raw.get("created"),
        "context_length": raw.get("context_length"),
        "input_modalities": input_modalities,
        "output_modalities": output_modalities,
        "supported_parameters": sorted(
            {str(item) for item in supported if isinstance(item, str)}
        ),
        "pricing": {
            key: pricing.get(key)
            for key in ("prompt", "completion", "image", "request")
            if pricing.get(key) is not None
        },
        "suggested_roles": sorted(set(suggested_roles)),
        "evaluation_status": "not_evaluated",
    }


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [
            part.strip().casefold()
            for part in value.split("+")
            if part.strip()
        ]
    if isinstance(value, list):
        return sorted(
            {
                str(item).strip().casefold()
                for item in value
                if isinstance(item, str) and item.strip()
            }
        )
    return []


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        temporary.chmod(0o600)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


__all__ = [
    "DISCOVERY_DIR",
    "OPENROUTER_SNAPSHOT",
    "DiscoveryResult",
    "ModelDiscoveryError",
    "discovery_due",
    "discover_openrouter",
    "load_snapshot",
]
