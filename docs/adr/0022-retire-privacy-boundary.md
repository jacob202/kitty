# ADR 0022: Retire The D10 Local-Only Privacy Boundary

- **Status:** Accepted
- **Date:** 2026-07-27
- **Decision owner:** Jacob
- **Supersedes:** ADR 0011 (Privacy Boundary In The LLM Router)

## Context

ADR 0011 declared four content classes local-only — `journal`, `mail_body`,
`health_admin`, `knowledge_document` — and stated under Consequences that it
ruled out "mail and journal routes silently using cloud models."

Only half of that was ever built. `enforce_privacy_boundary` raised **only**
when a caller explicitly passed `privacy_tier="cloud_ok"`. Nothing in
`call_llm` branched on `privacy_tier`, so the default `"local"` fell through to
`{LITELLM_BASE}/v1/chat/completions`. `LITELLM_BASE` is `localhost:8001` —
locally *hosted*, but every entry in `gateway/litellm_config.yaml` is an
OpenRouter cloud model. The tier name appears to have been conflated with "the
local proxy."

The practical effect, from the boundary's introduction until this ADR: journal
entries, benefits and medical-admin documents, Magic Kitty's cross-project
synthesis, and every non-`code` project's next step were sent to DeepSeek via
OpenRouter, while the ADR, the module docstrings, and the test suite all said
they stayed on the Mac.
`tests/test_llm_privacy_boundary.py::test_call_llm_passes_through_when_local`
asserted the cloud provider *was* contacted for journal content, so the suite
encoded the inverted contract instead of catching it.

The only genuinely local path was `POST /knowledge/expert`, which bypasses
`call_llm` entirely and calls the MLX loopback server directly.

Two coherent repairs existed: build the missing local route, or drop the claim.

## Decision

Drop the boundary. There is no local-only content class.

Jacob's operating preference, stated 2026-07-27, is that Kitty should use
available resources efficiently but **not accept quality handicaps imposed by
8 GB of hardware** — work that a small local model would do worse belongs in the
cloud. The four protected classes include the most judgment-heavy paths in the
product (journal reflection, next-step advice). Serving them from a local 4B to
honour a guarantee that was never actually in force trades real output quality
for a property the system did not have.

Accordingly:

1. `PRIVACY_LOCAL_ONLY`, `PrivacyBoundaryError`, and `enforce_privacy_boundary`
   are removed from `gateway/llm_client.py`.
2. The `privacy_tier` and `content_class` parameters are removed from
   `call_llm` and `chat_completions_non_stream`, and from every call site and
   injected-callable seam (`deadline_extractor`, `next_step`, `magic_kitty`,
   `routes/journal`, `routes/completions`, `expert_proactive`).
3. `next_step._PRIVACY_BY_KIND` is removed. Project kind no longer selects a
   routing tier — notably, non-`code` projects are no longer classified as
   `health_admin` by default.
4. Docstrings claiming local-only execution are corrected rather than left to
   assert something untrue.
5. `POST /knowledge/expert` keeps its MLX loopback path unchanged. It is now an
   explicitly chosen local feature, not a privacy mandate. Whether it should
   also be allowed a cloud option is a separate, open decision.

## Consequences

What this commits to, plainly:

- Journal entries, mail bodies, benefits and medical-admin documents, and
  cross-project synthesis are sent to a cloud provider (currently DeepSeek via
  OpenRouter). This is now the documented, intended behaviour.
- Kitty makes **no** local-only data guarantee. Nothing in the codebase should
  claim one. Any future re-introduction must ship the route and a test that
  proves the cloud provider is not contacted — not a label.
- Removing the boundary removes an input-validation path in
  `routes/completions.py`: an explicit non-`kitty-*` model override is no longer
  gated by content class. `content_class` remains filtered out of the upstream
  payload so an old client cannot leak it to a provider.

What this rules out:

- Re-adding a `privacy_tier`-style flag that only raises on an opt-in string.
  Enforcement that depends on the caller already knowing the answer is not
  enforcement.

## Revisiting

This decision is about the boundary as designed, not about privacy as a goal.
If Jacob later wants specific content kept off the network, the correct shape is
a real local route with a failing-loud error when the local model is
unavailable, verified by a test that asserts no provider contact — the pattern
`POST /knowledge/expert` already demonstrates.
