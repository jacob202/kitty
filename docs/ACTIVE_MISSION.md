# Active Mission — Trustworthy Daily Driver

**Mission ID:** KTRUST-001  
**Status:** Running  
**Approved by:** Jacob on 2026-08-04  
**Roadmap stage:** 1 — Trust baseline

<!-- kitty-mission
{
  "schema_version": 1,
  "mission_id": "KTRUST-001",
  "status": "running",
  "approved_at": "2026-08-04T21:47:00Z",
  "approved_by": "Jacob",
  "base_sha": "c266b13c0c694929c728a3f3861187f56229dbac",
  "authority": "docs/ACTIVE_MISSION.md"
}
-->

## Objective

Leave Kitty with one trustworthy operating picture and one proven daily-driver path. Someone returning tomorrow must be able to tell what is authoritative, start Kitty, use the approved Open WebUI shell, recognize failures honestly, and know the next bounded task without reconstructing chat history.

## Scope

1. Keep repository truth, architecture, roadmap, status, and active mission consistent.
2. Maintain a green deterministic CI baseline and repair security/reliability defects before expansion.
3. Land the isolated `pydantic-settings` security update.
4. Prove the Open WebUI daily-driver path from clean start through real chat, persistence, restart, model/tool attribution, and understandable failure recovery.
5. Complete one real #270 capture → return → respond loop on the phone/PWA with restart and deduplication evidence.
6. Inventory active workflows and prepare enforceable default-branch protection through #399, retiring only conclusively obsolete automation.
7. Preserve unique historical work and keep image Git history unchanged.

## Acceptance

- `README.md`, Architecture, Decisions, Roadmap, Project Status, and this mission agree.
- Main passes pytest, lint, typecheck, hygiene, Kitty Chat tests/build, and browser smoke.
- The vulnerable `pydantic-settings` pin is removed through an isolated green PR.
- A clean local Open WebUI start produces a real streamed response, preserves the conversation across restart, and reports the actual model/provider or a useful failure.
- One real #270 insight returns once at the intended time and records Act, Snooze, or Archive without duplication after restart.
- The 51-workflow ledger exists and proposed required checks map to real CI contexts.
- No image history is rewritten, purged, enumerated, or otherwise altered.

## Stop rules

Do not begin broad frontend redesign, Image Agent expansion, PAA refactoring, agent-pattern experiments, or new orchestration while this mission remains incomplete. Do not enable paid providers, GPU execution, or paid workflow behavior without explicit charge authorization.

## Publication authorization

Jacob authorized the repository maintenance, security corrections, documentation replacement, superseded-item closures, safe branch/workflow cleanup, and merges required for this mission. Destructive image-history changes are explicitly excluded.
