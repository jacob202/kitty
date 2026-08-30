# ADR 0029: Capability Manifest Is the Single Source of Runtime Truth

**Date:** 2026-08-05
**Status:** Accepted

## Context

The Product Architecture document (2026-07-10), architecture honesty audit
(2026-07-24), and multiple runtime observations revealed that Kitty has no
single owner of runtime truth. Application identity, project context, model
availability, tool availability, connection health, and Builder state are
discovered through unrelated endpoints, local constants, prompt assumptions,
and fallbacks. Kitty cannot reliably distinguish `available`, `unavailable`,
`degraded`, `stale`, and `unknown`.

Specific failures:
- The chat UI defines model identities independently of runtime providers.
- Some runtime lookups convert failures into `unknown` or empty capability
  lists, making absence indistinguishable from failure.
- `runtime_manifest.json` was a hand-written file (deleted 2026-08-05,
  superseded by `runtime_manifest.py`), not live state.
- Builder state was reported through multiple uncoordinated status endpoints.
- The capability gap was identified as Root Cause 1 in the Product Architecture.

## Decision

Kitty exposes exactly one source of runtime truth: the **Capability Manifest**.
It is composed from records reported by the subsystem that owns each fact; it is
not scraped from UI state or invented by the model.

Every dynamic item in the manifest carries:
- `state`: `available | unavailable | degraded | stale | unknown`
- `observed_at` and `valid_until`
- `source`: the owning subsystem
- `evidence_ref`: the probe, record, or receipt supporting the claim
- A safe user-facing reason when it is not available.

`unknown` means the truth could not be established. It must never be rendered as
`unavailable`, treated as success, or silently replaced with a default.

The manifest supports:
- A full snapshot query for startup and diagnostics.
- Revisioned patches over server-sent events for live clients.
- A compact prompt projection containing only facts relevant to the current
  request.
- Immutable snapshot references attached to turns and execution receipts.

## Alternatives considered

**Each subsystem exposes its own status:** Rejected. This is the current state
and is the root cause of confusion, stale claims, and silent failures.

**The model infers capability from prompt description:** Rejected. The model
cannot distinguish a failed probe from an unavailable capability. The Product
Architecture adversarial review explicitly identified this as the weakest
assumption ("If runtime facts are wrong: Kitty becomes confidently wrong at a
larger scale").

**Single static configuration file:** Rejected. Configuration cannot reflect
live provider health, active project scope, or Builder execution state.

## Evidence

- Product Architecture §4 (2026-07-10): Defined CapabilityManifest schema and
  ownership/freshness rules.
- Architecture honesty audit (2026-07-24): Verified that model identity is
  defined in the chat UI independently of runtime providers.
- Adversarial review (Product Architecture §17): Identified stale truth as the
  largest single risk.
- `runtime_manifest.json` deleted 2026-08-05: The hand-written artifact
  was superseded by `runtime_manifest.py`, which itself will be superseded
  by the live Capability Manifest.

## Consequences

- **Positive:** One surface for all truth. Tool availability enforced by the
  executor, not merely described in prompts. Model/location displayed honestly.
  Failed probes are unmistakably failures.
- **Negative:** Every subsystem must report its state to the composer. This
  requires per-owner probe endpoints and TTL contracts. Implementation effort
  (Phase 1 of Product Architecture).
- **Open question:** Whether the Open WebUI shell consumes the manifest directly
  or Kitty Gateway proxies relevant fields.

## Risks

- Manifest reports stale truth: Field TTLs, per-owner probes, and explicit
  `stale` state mitigate this. An expired field becomes `stale`; the composer
  does not extend its life because a probe failed.
- Prompt bloat from loading full manifest: The compact prompt projection
  contains only facts relevant to the current request.

## Follow-up work

- KPA-01: Runtime Truth v1 + Honest Chat Identity (Product Architecture §18).
  Define CapabilityManifest v1, owner/freshness rules, snapshot API, compact
  prompt projection, and bind chat attempts to manifest revisions.
- Replace hardcoded model/connection identity in Chat with live truth.
- Ensure Open WebUI receives accurate model availability from the manifest.

## Related ADRs

- ADR 0003: Gateway is the product
- ADR 0015: Resume loop is the product; Builder boundary
- ADR 0017: Kitty → Mission → KittyBuilder control plane
