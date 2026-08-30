# ADR 0032: Evidence-Backed Claims — No Fabricated Success

**Date:** 2026-08-05
**Status:** Accepted

## Context

The BLUEPRINT.md (2026-07-11) honesty ledger documented multiple claims that
were "fake, broken, or unproven — must not be presented as working":

- Memory consolidation on session close was a no-op.
- Insights/dream store was "effectively empty no-op."
- agent_runner/task_runner completion states could report false `completed`.
- ChromaDB had zero collections.
- Image generation status was fabricated when ComfyUI was not running.

The BLUEPRINT's Card C (fail-loud sweep), the architecture honesty audit
(2026-07-24), and the feature reality audit (2026-07-28) all found the same
pattern: Kitty had infrastructure that sometimes manufactured success when the
underlying system failed.

The VERIFIER.md and verifier.py were built to address this, and the architecture
correction (2026-07-28) codified: "Failures stay failures. Never return
`[]`/`null`/`completed` to hide an error."

However, no ADR formally established the principle as a binding architectural
rule.

## Decision

Kitty may claim an operation succeeded only when a verified execution receipt
exists with the evidence required for that action kind. Failure, stale state,
and unavailable capability are distinct states and must never be conflated.

Specific evidence requirements:

| Claim | Minimum evidence |
|---|---|
| file saved | durable path, hash, and successful atomic write |
| image generated | ready image artifact plus media validation |
| message sent | connector/provider delivery acknowledgement |
| code fixed | change bundle plus declared validation receipts |
| Builder packet complete | runner success, deterministic checks, independent review outcome |
| connection available | unexpired successful owner probe |
| model used | provider response metadata for the actual attempt |
| cost | usage record plus current pricing source, or provider-reported charge |

Negative rules:

- Never render `unknown` as `unavailable` or `false`.
- Never fabricate a default where evidence is absent (e.g., `$0` cost when
  pricing is unavailable, `available: true` when a probe failed).
- Never silently convert a failure into success through exception swallowing,
  empty defaults, or fallback chains that hide the original error.
- Never present a backend module without a tested, browser-verified UI path as
  "shipped."

## Alternatives considered

**Allow "best effort" claims without evidence:** Rejected. The BLUEPRINT's
honesty ledger demonstrated that this breeds false confidence. Users make
decisions based on Kitty's claims (is a message sent? was code fixed?). False
claims damage trust irrecoverably.

**Only verify critical paths:** Rejected. The distinction between critical
and non-critical is subjective and tends to grow. A uniform evidence standard
is simpler and more reliable.

## Evidence

- BLUEPRINT.md §5 honesty ledger (2026-07-11): Catalogued all fabricated claims.
- Architecture honesty audit (2026-07-24): Verified backend capability versus
  end-to-end product reality.
- Feature reality audit (2026-07-28): Established three states: Working,
  Partial, Planned. Forbade calling a feature shipped because backend code
  exists.
- KittyBuilder core runtime audit (2026-08-01): Verified that crash recovery
  never fabricates `completed`; interrupted runs remain `interrupted`; budget
  exhaustion produces explicit `blocked`, not silent failure.
- VERIFIER.md: "Failures stay failures. Never return `[]`/`null`/`completed`
  to hide an error."
- The fail-loud sweep documented in BLUEPRINT's trust lane (Cards A-H).

## Consequences

- **Positive:** Trustworthy product. Every claim has a verifiable source.
  Diagnostics can trace from claim to evidence.
- **Negative:** More implementation discipline required. Every action must
  produce a receipt. Not all existing actions do this yet.
- **Open question:** How to surface evidence to users without overwhelming
  the UI. Advanced diagnostics should reveal raw receipts; normal mode should
  show concise status.

## Risks

- The evidence requirement becomes a blocker for shipping features: Mitigated
  by the Partial/Working/Planned taxonomy (FEATURE_REALITY_2026-07-28). A
  feature can ship as Partial with honest labeling.

## Follow-up work

- Audit all existing actions for receipt compliance.
- Implement the execution receipt schema from Product Architecture §11.
- Wire image generation, chat streaming, and Builder results through the
  receipt pipeline.
- Add evidence requirements to the packet contract format.

## Related ADRs

- ADR 0029: Capability Manifest is the single source of runtime truth
- ADR 0017: Kitty → Mission → KittyBuilder control plane (receipt boundary)
- ADR 0027: Open WebUI shell boundary (shell must not fabricate claims)
