---
type: constitution
title: "Kitty Engineering Constitution"
status: canonical
owner: jacob
primary_purpose: Immutable engineering doctrine — permanent principles that govern every technical decision
derives_from:
  - docs/VISION.md
implements: []
referenced_by:
  - docs/engineering/ARCHITECTURE.md
  - docs/adr/*
review_cycle: annual (changes require an ADR)
---

# Kitty Engineering Constitution

This document defines the permanent engineering principles that govern every technical decision in the Kitty repository. These principles are derived from the Vision and are not subject to casual change. Major constitutional changes require an ADR.

## 1. Fail Loud, Never Mask

Raise errors with clear causes. Do not swallow exceptions, return fake defaults, or add silent fallbacks. External calls may retry with a visible warning, then must raise the real error with useful context.

## 2. Truthfulness

Every claim Kitty makes — "completed", "saved", "connected", "available" — must be backed by evidence. `unknown` is never rendered as `unavailable` or treated as success. Stale state is labeled stale. Missing data produces an honest incomplete result, not a plausible default.

## 3. Evidence Before Trust

Do not accept a claim without verification. Test counts come from commands actually run. "Done" claims are verified against the current tree, not propagated from stale handoffs. Browser verification is a release gate for UI work.

## 4. Research Before Invention

Before building something new, check whether it already exists in the repo, in the ADRs, or in the established patterns. Borrow patterns, not random complexity. Do not add a new database, queue, cloud service, or framework without an ADR.

## 5. Judgment Before Execution

Think before acting. Read the handoff, the architecture, and the decisions before touching code. When unsure whether something helps Jacob's life or just polishes the machine — it's the machine. Pick the other thing.

## 6. Reflection Before Closure

Every session ends with an honest account of what was done, what remains, and what was learned. Handoffs are written before stopping. Learnings are recorded. Stale handoffs are worse than no handoff.

## 7. Reduce Activation Energy

Make the right thing easy. One command to start. One command to capture. One tap to continue. The front door answers before you ask. Small diffs. One packet per session. Bounded scope.

## 8. Compound Organizational Judgment

Every decision is recorded. Every lesson is promoted or archived. Documentation has owners, metadata, and traceability. The repository's knowledge grows structurally, not accidentally.

## 9. Bounded Execution

Every action has a scope, a stop condition, and a verification command. Workers do not self-select broad work. Approval tiers are enforced in code. T3 actions (payments, deletions, secrets) have no executor — they are structurally absent, not "ask first."

## 10. Gateway Is The Product

The FastAPI gateway owns all product logic. Clients (web, Raycast, Siri, Telegram) are thin views over gateway APIs. No product logic in clients. No duplicate state. No independent truth paths.

## 11. Local-First By Default

Triage, persona, and private-material summarization run local. If the local model is down, those tasks fail loud rather than silently escalating to cloud. Cloud reasoning is for content explicitly approved to leave.

## 12. Small Diffs, One Packet Per Session

Keep diffs focused. Do not reformat unrelated code. One packet = one branch = one PR. Do not broaden scope because the product feels exciting.

## Amendment Process

Changes to this Constitution require:

1. An ADR documenting the proposed change, rationale, and impact.
2. Jacob's explicit approval.
3. Update to this document with the ADR reference.

The Constitution is not frozen — it evolves as the organization learns — but it evolves intentionally, not accidentally.
