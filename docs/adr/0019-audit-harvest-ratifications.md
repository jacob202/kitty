# ADR 0019: Audit-harvest ratifications (11 parked decisions resolved)

**Date:** 2026-07-24
**Status:** Accepted (Jacob delegated judgment; ratified with evidence)
**Source:** 8 archived audit docs (`docs/archive/audits-2026-07/`), consolidated in `~/kb/wiki/2026-07-24-unconsumed-audit-recommendations.md`.

## Context

The 2026-07-14→23 audit cycle produced 11 decisions "requiring Jacob's judgment" that were never ratified. Resolution rule applied: **prefer what already exists and works; defer speculative hardening until a real failure or a real product surface demands it; ratify standing rules that match ADR-0007 (borrow patterns, not complexity).**

## Decisions

### DeepTutor harvest (3)

1. **Type-specific spaced repetition for tutor — DEFER.** Tutor is not a daily surface (vision-gap P0s are frontend/personality/life-awareness). The simple 1/3-day system suffices until tutor usage data exists. Revisit with data.
2. **Document validation on knowledge upload — DEFER.** The upload pipeline exists and works (ingest_books, archivist, PDF pipeline). Harden on the first real failure, not speculatively.
3. **Skill sharing/hub — DEFER entirely.** No product requirement. DeepTutor's import-security patterns remain reference material.

### Feature-adjacent harvest (8)

4. **"Approve FAR-01 before autonomous-execution expansion" — RESOLVED BY EXISTING PRACTICE.** Builder's durable initiative/packet/attempt/lease/run stores (ADR-0017) ARE the durable-runs story. No new work. Revisit only if `agent_runner` gains autonomous execution.
5. **Kitty-native minimal event envelope, never AG-UI wholesale — RATIFIED.** ADR-0007 corollary: borrow patterns, never adopt frameworks wholesale.
6. **SQLite + temporal/provenance semantics, no graph database — ALREADY TRUE.** `memory_weave.py` (temporal KG in SQLite, confidence decay) shipped. Ratified retroactively.
7. **Khoj, Open WebUI, Screenpipe = study-only — RATIFIED.** License/product-boundary concerns stand.
8. **Ambient screen/audio capture stays deferred behind a dedicated ADR + threat model — RATIFIED** as standing rule.
9. **Unified work surface = read-only projection only, no second task queue — ALREADY TRUE.** `builder_status.py` is exactly that projection. Ratified retroactively.
10. **Evaluate model+harness+strategy combos with trace-linked quality/cost evidence — RATIFIED** as principle; partially live via `/perf/stats` per-tier + `token_log.jsonl`. No new work now.
11. **Never auto-implement from an audit — RATIFIED** as standing rule. Audits land as documents; packets are created explicitly. (The 2026-07-24 rescue pass that produced this ADR is the counterexample that proves the rule.)

## Consequences

- Zero new work items. Three defers, eight ratifications (three of which describe already-shipped reality).
- The 14-item companion-layer adapt register remains available in the kb entry; each item must be re-verified against current code (KX-05 lanes moved 07-23/24) before proposal.
