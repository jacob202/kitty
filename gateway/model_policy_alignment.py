"""Keep the model-role contract aligned with the routes Kitty actually serves."""

from __future__ import annotations

from typing import Any, Mapping

from gateway.model_routing import describe_routing
from gateway.operating_policy import OperatingPolicyError, load_model_policy


def validate_model_role_alignment(
    *,
    policy: Mapping[str, Any] | None = None,
    routing: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail when a branded role and its configured upstream silently diverge."""

    resolved_policy = dict(policy or load_model_policy())
    resolved_routing = dict(routing or describe_routing())
    if not resolved_routing.get("readable"):
        raise OperatingPolicyError(
            f"LiteLLM routing is unreadable: {resolved_routing.get('error')}"
        )

    route_rows = {
        str(row.get("alias")): row
        for row in resolved_routing.get("routes", [])
        if isinstance(row, Mapping) and row.get("alias")
    }
    failures: list[str] = []
    checked: list[dict[str, str]] = []

    for role_name, role in resolved_policy["roles"].items():
        route = str(role["route"])
        row = route_rows.get(route)
        if row is None:
            failures.append(f"{role_name}: route {route!r} is absent from LiteLLM")
            continue

        incumbent = role.get("incumbent")
        if incumbent is None:
            checked.append(
                {
                    "role": role_name,
                    "route": route,
                    "provider": str(row.get("provider") or ""),
                    "model": str(row.get("upstream_model") or ""),
                }
            )
            continue

        expected_provider = str(incumbent["provider"])
        expected_model = str(incumbent["model"])
        actual_provider = str(row.get("provider") or "")
        actual_model = str(row.get("upstream_model") or "")
        if actual_provider != expected_provider or actual_model != expected_model:
            failures.append(
                f"{role_name}: policy expects {expected_provider}/{expected_model}, "
                f"LiteLLM serves {actual_provider}/{actual_model}"
            )
            continue
        checked.append(
            {
                "role": role_name,
                "route": route,
                "provider": actual_provider,
                "model": actual_model,
            }
        )

    if failures:
        raise OperatingPolicyError("model role alignment failed: " + "; ".join(failures))
    return {"status": "aligned", "roles": checked}


__all__ = ["validate_model_role_alignment"]
