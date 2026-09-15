# QoL Packet 01 — Kitty Health Surface

**Status:** Implementation plan for Jacob approval (not self-authorizing)
**Packet:** `docs/quality_of_life_packets.md` PACKET 01 — KITTY HEALTH (P0)
**Branch:** `feat/health-surface-20260823` (worktree `/Users/jacobbrizinnski/Projects/kitty-health-20260823`)
**Base:** origin/main `ad5b4967`

## Objective

One operator-facing surface answering: *Is Kitty working, and if not, exactly what is
wrong?* The user opens one place and understands operational state in under 10 seconds.

## Constraints

- Do **not** create a second health database. Compose existing primitives.
- Do **not** duplicate automation-supervisor state or invent another automation status
  system. The supervisor (`gateway/automation_supervisor.py`) already owns the exact
  vocabulary `available/degraded/stale/unavailable/unknown` and is the authoritative
  lifecycle source for the tasks it tracks.
- "green" must not mean merely "task exists" — a tracked task with a dead underlying
  service must be truthfully `stale`/`unavailable`.
- Must not hide dependency failures (e.g. Image provider down must show under Image Lab,
  not be swallowed).
- Read-only projection. No mutation of supervisor, cron, image, or grant state.
- Preserve existing `doctor.py` and `builder_doctor.py` surfaces; this is a new thin
  projection endpoint + UI view, not a rewrite.

## Existing primitives to compose (do not reinvent)

| Domain | Source | Notes |
|---|---|---|
| Gateway service | `doctor.py` `_check_services` (gateway HTTP `/health`, litellm readiness) | probe live |
| Database | `doctor.py` store:chromadb; sqlite open via `kitty_db.connect` | probe live |
| Memory | `gateway.memory._probe_memory_backend()` | WARN when down but explicit memory still available |
| Automation supervisor | `supervisor.snapshot()` | authoritative; read-only |
| Cron | `supervisor.get_status("cron")` + `cron.list_schedules()` counts | supervisor authoritative for lifecycle |
| Telegram | `supervisor.get_status("telegram")` | authoritative |
| Image Lab | `supervisor.get_status("image-recovery")`, `("image-batch-worker")` | authoritative |
| Image provider readiness | `image_runner` probes: `airforce_images_available()`, `fal_images_available()`, `openrouter_images_available()`, `flux_images_available()`, `flux2_images_available()` | live `(bool, str)` probes |
| Image queue | `image_jobs` counts by non-terminal status | read-only query |
| Ollama/embedding | `_probe_memory_backend()` / embedding capability probe | degraded item |
| Pending approvals/grants | `action_grants.list_grants(include_inactive=False)` pending count | read-only |

## Deliverables

1. **`gateway/health_surface.py`** — pure projection: build a `KittyHealth` snapshot
   (`{generated_at, overall, domains: [...], degraded: [...], still_functional: [...],
   pending_grants: n}`). Each domain: `{name, status, reason, detail}` with status drawn
   from the authoritative source above. `overall` is derived (degraded if any degraded,
   unavailable if gateway unreachable, else healthy).
2. **Route** in `gateway/routes/status.py`: `GET /health/surface` returning the JSON
   projection (and keep `/status/glance` as-is).
3. **UI** — extend the React home view (`HomeView`/`HomeState` + `StatusBadge`) with a
   glanceable health block: primary rows, a Degraded section (e.g. "Ollama unavailable"),
   and a Still functional section. Clicking a degraded row explains what failed, when,
   whether recovered, what remains functional, whether user action required.

## RED tests first

`tests/test_health_surface.py` (or extend existing health tests):

1. All healthy → overall healthy, all domains available.
2. One subsystem degraded (supervisor marked degraded) → overall degraded, degraded list
   contains it, detail explains reason.
3. One unavailable dependency → overall degraded/unavailable, listed.
4. Stale service (heartbeat older than stale_after) → status `stale`.
5. Supervisor failure (snapshot raises) → projection fails loudly, never silently green.
6. Image provider unavailable while Image Lab otherwise functional → degraded lists the
   provider, Image Lab still functional.
7. Ollama unavailable while explicit memory functional → degraded lists Ollama, memory
   still functional (matches existing doctor note).
8. Pending grants count surfaced.

## Acceptance

1. RED tests fail before implementation; GREEN after smallest implementation.
2. Wider tests still pass (narrow run first, then the health-relevant slice).
3. `GET /health/surface` returns truthful JSON; verified live against a running gateway
   and a degraded-injection scenario.
4. Ruff + mypy clean on changed files.

## Deferred / out of scope

- Startup Diagnostics (Packet 07) and Activity Timeline (Packet 08).
- Builder state (`builder_doctor.py`) — separate surface, not part of this projection.
- New dashboards or persistence; this is a projection endpoint + home view block only.
