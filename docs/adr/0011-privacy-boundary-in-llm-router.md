---
type: adr
title: "Privacy Boundary In The LLM Router"
status: accepted
owner: jacob
primary_purpose: Local triage must fail loud rather than silently escalating to cloud models
derives_from:
  - docs/CONSTITUTION.md
review_cycle: as needed (superseded by replacement ADR)
---

# ADR-0011: Privacy Boundary In The LLM Router

**Status:** Accepted
**Date:** 2026-07-02 (from `docs/OPERATOR_STRATEGY.md` §17.3, via packet 012)

## Context

Local-first is the product thesis. That is not enforceable by convention
once cloud models do drafting — it has to be enforced in code at the call
site where journal, mail, health/admin, and uploaded document content
enters the LLM pipeline.

## Decision

`gateway/llm_client.call_llm(..., privacy_tier, content_class)` is the only
sanctioned entry point for **remote** LLM calls that may carry private
content. If `content_class` is in `PRIVACY_LOCAL_ONLY` and
`privacy_tier == "cloud_ok"`, raise `PrivacyBoundaryError` with a reason.
The route layer translates that to HTTP 400.

**Data classes:**

| Class                | Default privacy | Examples                                           |
| -------------------- | --------------- | -------------------------------------------------- |
| `journal`            | local-only      | journal entries, interview turns, dream synthesis  |
| `mail_body`          | local-only      | full email body, replies, attachments              |
| `health_admin`       | local-only      | SAID/CDB/DTC docs, benefits letters, medical forms |
| `knowledge_document` | local-only      | uploaded source excerpts used by expert retrieval  |
| `calendar`           | cloud-permitted | event titles, times, locations                     |
| `todo`               | cloud-permitted | todo text, action queue payloads                   |
| `chat`               | cloud-permitted | persona chat, triage classification                |

**Enforcement in `gateway/llm_client.py`:**

- `call_llm(..., privacy_tier: Literal["local","cloud_ok"] = "local", content_class: str | None = None)`
- If `content_class` is in `PRIVACY_LOCAL_ONLY` and `privacy_tier == "cloud_ok"`, raise `PrivacyBoundaryError` with a reason. The route layer translates that to HTTP 400.
- Journal route tags `content_class="journal"` and defaults `privacy_tier="local"`.
- Any future route carrying private content MUST tag both fields. Routes that pass `content_class=None` keep the previous permissive behavior (any cloud model is acceptable) so existing call sites don't break, but new private-data call sites must opt in explicitly.
- `POST /knowledge/expert` has no cloud option. It sends retrieved excerpts only to the fixed MLX loopback endpoint at `127.0.0.1:8010`; an unavailable local model is a visible error, not permission to fall back to cloud.

## Consequences

What this rules out:

- Mail and journal routes silently using cloud models.
- Bypassing the boundary by calling remote providers directly instead of through `call_llm`. The loopback-only MLX expert path is the narrow exception because `call_llm` currently has cloud fallbacks.

What this commits to:

- `gateway/llm_client.call_llm` is the only sanctioned entry point for remote LLM calls that may carry private content. New routes for mail, journal, and health/admin MUST go through it.
- `tests/test_llm_privacy_boundary.py` exists and asserts the journal case raises on cloud, uploaded document content raises on cloud, and the chat case does not.
