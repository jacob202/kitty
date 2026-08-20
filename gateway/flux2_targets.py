"""Flux2HostedTarget — the explicit execution-target representation for hosted FLUX.2.

ADR 0040 decision 1 (FLUX.2 primary family) plus IL-04's "estimate target ==
availability target == dispatch target == observed cost target" invariant.

This is deliberately small: it is NOT a general provider framework. It carries
enough truth that a dispatched FLUX.2 job can answer — exactly which model,
which semantic tier, how many references are allowed, and how much the selected
model costs for the requested dimensions:

    quality tier (draft/final)
        ↓  Flux2HostedTarget
        ↓  model_id (BFL path), endpoint, reference limit, cost contract
        ↓  actual dispatch + cost reconciliation

Costs are the current official BFL FLUX.2 pricing (vendored at
gateway/vendored/flux2-guidance, updated 2026-08-19). Credit pricing:
1 credit = $0.01 USD. Formula (cents): (firstMP + (outputMP-1)*mpPrice) +
(inputMP*mpPrice).

Estimates must never silently default to zero for an unknown target: unknown
targets fail loud (``Flux2TargetError``).
"""

from __future__ import annotations

from dataclasses import dataclass

from gateway.flux2_compiler import OPERATION_IMG2IMG

# 1 credit = $0.01 USD (official BFL credit pricing).
CREDITS_PER_USD = 100.0


class Flux2TargetError(ValueError):
    """Raised when a FLUX.2 execution target is unknown or mis-specified."""


@dataclass(frozen=True)
class Flux2HostedTarget:
    """Exact hosted FLUX.2 execution target and its cost contract.

    Fields:
        target_id       small stable identifier ("flux2-klein-4b-h")
        model_id        BFL API path segment, e.g. "flux-2-klein-4b"
        quality_tier    semantic tier served: "draft" | "final"
        hosted          classification used by the IL-02 policy gate (always True)
        reference_limit max ordered references the API accepts
        endpoint        absolute BFL endpoint path (may be overridden by env)
        first_mp_cents  price of the first output megapixel, in credits-cents
        add_mp_cents    price of each additional output megapixel, in cents
        input_mp_cents  price per input/reference megapixel, in cents
    """

    target_id: str
    model_id: str
    quality_tier: str
    hosted: bool
    reference_limit: int
    endpoint: str
    first_mp_cents: float
    add_mp_cents: float
    input_mp_cents: float

    def estimate_cost_usd(self, width: int, height: int, operation: str) -> float:
        """Deterministic honest estimate for THIS target and dimensions.

        Mirrors the official formula in cents:
            (firstMP + (outputMP-1)*mpPrice) + (inputMP*mpPrice)
        converted to USD at 100 credits/dollar. The input term is charged for
        img2img (reference conditioning); an input megapixel is estimated at
        the output resolution since the anchor's own dimensions are not known
        at estimate time. The provider-reported actual cost reconciles the
        reservation afterward.
        """
        output_mp = max(width * height / 1_000_000.0, 1.0)
        cents = self.first_mp_cents + (output_mp - 1.0) * self.add_mp_cents
        if operation == OPERATION_IMG2IMG:
            cents += output_mp * self.input_mp_cents
        return round(cents / CREDITS_PER_USD, 6)


# 1 MP T2I = $0.014, 1 MP I2I = $0.015. 1st MP 1.4c, +MP 0.1c, input MP 0.1c.
FLUX2_KLEIN_4B_H = Flux2HostedTarget(
    target_id="flux2-klein-4b-h",
    model_id="flux-2-klein-4b",
    quality_tier="draft",
    hosted=True,
    reference_limit=4,
    endpoint="https://api.bfl.ai/v1/flux-2-klein-4b",
    first_mp_cents=1.4,
    add_mp_cents=0.1,
    input_mp_cents=0.1,
)

# 1 MP T2I = $0.03, 1 MP I2I = $0.045. 1st MP 3.0c, +MP 1.5c, input MP 1.5c.
FLUX2_PRO_H = Flux2HostedTarget(
    target_id="flux2-pro-h",
    model_id="flux-2-pro",
    quality_tier="final",
    hosted=True,
    reference_limit=8,
    endpoint="https://api.bfl.ai/v1/flux-2-pro",
    first_mp_cents=3.0,
    add_mp_cents=1.5,
    input_mp_cents=1.5,
)

# The only two shipped hosted semantic tiers: DRAFT (Klein 4B) and FINAL (Pro).
FLUX2_HOSTED_TARGETS: dict[str, Flux2HostedTarget] = {
    FLUX2_KLEIN_4B_H.target_id: FLUX2_KLEIN_4B_H,
    FLUX2_PRO_H.target_id: FLUX2_PRO_H,
    # model_id aliases let recipe/routing resolve by model name too.
    FLUX2_KLEIN_4B_H.model_id: FLUX2_KLEIN_4B_H,
    FLUX2_PRO_H.model_id: FLUX2_PRO_H,
}

# recipe quality_tier → semantic tier mapping (the one obvious mapping the
# packet requires: quality tier → execution target → exact model).
_QUALITY_TIER_MAP: dict[str, str] = {
    "fast": FLUX2_KLEIN_4B_H.target_id,
    "quality": FLUX2_PRO_H.target_id,
    "maximum": FLUX2_PRO_H.target_id,
}

VALID_QUALITY_TIERS = frozenset(_QUALITY_TIER_MAP)


def resolve_flux2_target(target: str | None) -> Flux2HostedTarget:
    """Resolve a target id/model id; fail loud instead of defaulting to zero."""
    if not target or not target.strip():
        raise Flux2TargetError("flux2 target is required and was empty")
    key = target.strip().lower()
    resolved = FLUX2_HOSTED_TARGETS.get(key)
    if resolved is None:
        raise Flux2TargetError(
            f"unknown flux2 hosted target {target!r}; known targets: "
            f"{sorted({t.target_id for t in FLUX2_HOSTED_TARGETS.values()})}"
        )
    return resolved


def flux2_target_for_quality_tier(quality_tier: str) -> Flux2HostedTarget:
    """Map a recipe quality tier to its exact FLUX.2 execution target."""
    target_id = _QUALITY_TIER_MAP.get(quality_tier)
    if target_id is None:
        raise Flux2TargetError(
            f"recipe quality_tier {quality_tier!r} has no flux2 hosted target; "
            f"expected one of {sorted(VALID_QUALITY_TIERS)}"
        )
    return resolve_flux2_target(target_id)
