"""BFL Direct FLUX.2 transport — the hosted adapter for the flux2@1 compiler.

IL-04: BFL Direct is the first real hosted FLUX.2 transport. All BFL-specific
wire details live here and nowhere else (ADR 0040 decision 4: the difference
between BFL / Runware / the private worker lives in the adapters). The compiler
output (gateway/flux2_compiler.py) stays provider-neutral; this module maps a
CompiledFlux2Request onto BFL request fields.

Contract with the IL-02 policy gate: BFL Direct is HOSTED. The runner must
never route private_adult content to this transport, regardless of
availability, price, recipe preference, or retry. The policy validation lives
at the runner boundary (gateway/image_runner.py) which calls this module only
for safe-lane, already-validated work.

Wire facts (from vendored bfl-api skill, pinned commit a6f74cc):
- endpoints are /v1/flux-2-klein-4b and /v1/flux-2-pro
- auth header: x-key: <BFL_API_KEY>
- references: input_image, input_image_2 .. input_image_8 (klein: max 4,
  pro: max 8); URL or base64 both accepted — base64 is used here so local byte
  references never need a public URL.
- flow: POST endpoint -> {polling_url}; GET polling_url -> status Pending/Ready/
  Error (legacy also saw Queued/Processing); when Ready, result.sample is a URL
  that EXPIRES in 10 minutes -> download immediately.
- pricing: 1 credit = $0.01; formula (firstMP + (outputMP-1)*mpPrice) +
  (inputMP*mpPrice) cents.
"""

from __future__ import annotations

import base64
from typing import Any, Sequence

from gateway.flux2_compiler import CompiledFlux2Request, CompiledReference
from gateway.flux2_targets import Flux2HostedTarget

try:
    from gateway.image_jobs import ImageJobStatus
except ImportError:  # pragma: no cover - test-only standalone import guard
    ImageJobStatus = None  # type: ignore[assignment, misc]


def endpoint_for(target: Flux2HostedTarget) -> str:
    """Absolute BFL endpoint for an execution target."""
    return target.endpoint


def serialize_references(
    target: Flux2HostedTarget,
    references: Sequence[CompiledReference],
    reference_bytes: Sequence[bytes],
) -> dict[str, str]:
    """Map ordered compiled references onto BFL input_image wire fields.

    Deterministic slot/order contract: the compiled reference's ``order``
    numbers it and drives the wire field — slot 1 -> ``input_image``,
    slot N -> ``input_image_{N}``. Bytes are base64-encoded so local references
    never require a public URL. Enforces the target's reference limit loudly.
    """
    if len(references) != len(reference_bytes):
        raise ValueError(
            "flux2 transport: reference count mismatch "
            f"({len(references)} compiled vs {len(reference_bytes)} byte blobs)"
        )
    if len(references) > target.reference_limit:
        raise ValueError(
            f"flux2 transport: target {target.target_id} accepts at most "
            f"{target.reference_limit} references, got {len(references)}"
        )
    ordered = sorted(zip(references, reference_bytes), key=lambda rb: rb[0].order)
    return {
        "input_image" if idx == 0 else f"input_image_{idx + 1}": base64.b64encode(
            blob
        ).decode("ascii")
        for idx, (_ref, blob) in enumerate(ordered)
    }


def serialize_payload(
    target: Flux2HostedTarget,
    compiled: CompiledFlux2Request,
    reference_bytes: Sequence[bytes] = (),
    *,
    seed: int | None = None,
) -> dict[str, Any]:
    """Serialize a compiled FLUX.2 request onto BFL wire fields.

    The canonical compiled object (prompt prose, ordered semantic references,
    protected traits, requested changes, unresolved negatives) is NOT
    transmitted verbatim; only the fields BFL understands leave this module.
    """
    payload: dict[str, Any] = {
        "prompt": compiled.prompt,
        "width": compiled.width,
        "height": compiled.height,
    }
    if seed is not None:
        payload["seed"] = seed
    if compiled.references:
        payload.update(
            serialize_references(target, compiled.references, reference_bytes)
        )
    return payload


def submit_headers() -> dict[str, str]:
    """BFL authentication headers (x-key). Credential lives in env."""
    import os

    key = os.environ.get("BFL_API_KEY", "")
    if not key:
        raise RuntimeError("BFL_API_KEY is not set; cannot reach BFL Direct")
    return {"x-key": key, "Content-Type": "application/json"}


def is_running_status(status: str | None) -> bool:
    """True while BFL reports the job still in flight."""
    return (status or "").lower() in {"pending", "queued", "processing"}


def sample_url_from_result(result: Any) -> str | None:
    """Extract the (10-minute-expiring) download URL from a Ready result."""
    if isinstance(result, dict):
        sample = result.get("sample")
        if isinstance(sample, str) and sample.strip():
            return sample.strip()
    return None


def seed_from_result(result: Any) -> int | None:
    if isinstance(result, dict):
        seed = result.get("seed")
        if isinstance(seed, int):
            return seed
    return None


def parse_cost_usd(response: dict[str, Any], fallback: float | None = None) -> float | None:
    """Convert provider-reported cost credits to USD; None if not reported."""
    raw = response.get("cost")
    if raw is None:
        return fallback
    try:
        credits = float(raw)
    except (TypeError, ValueError):
        return fallback
    if credits < 0 or credits != credits:  # reject negative / NaN
        return fallback
    return credits / 100.0


def validate_reference_limit(
    target: Flux2HostedTarget, references: Sequence[CompiledReference]
) -> None:
    """Fail loud BEFORE any request leaves for BFL if references exceed limit."""
    if len(references) > target.reference_limit:
        raise ValueError(
            f"target {target.target_id} allows at most {target.reference_limit} "
            f"references, compiled {len(references)}"
        )


def credits_to_usd(credits: float) -> float:
    """Convert BFL credits to USD (1 credit = $0.01)."""
    return credits / 100.0
