# Kitty Capability Inventory

Last updated: 2026-04-23

## Stable User-Facing Surface

These are the capabilities Kitty should advertise in primary help/discovery flows:

- Commands: `/brief`, `/stuck`, `/bench`, `/capture`, `/review`, `/remember`, `/deepsearch`, `/screen`, `/repair`, `/image`, `/status`, `/clear`, `/skills`, `/skill`, `/skill-unload`, `/skill-clear`, `/skill-loaded`, `/help`
- APIs: `/api/chat`, `/api/transcribe`, `/api/capabilities`, `/health`
- Repo MCP: `filesystem`, `memory`

Status:
- Keep: `/api/chat`, `/api/transcribe`, `/api/capabilities`, `/health`
- Hide from primary UX but keep available: `/skills`, `/skill`, `/skill-unload`, `/skill-clear`, `/skill-loaded`
- Investigate before broader promotion: memory-backed product surfaces that still behave mostly as plumbing

## Experimental Or Internal

These are real but should not be promoted as stable product surface:

- Commands: `/prep`, `/optic`, `/ocr`, `/scrape`, `/cal`, `/watch`, `/council`
- API: `/api/eval/scorecard`, `/api/health`, `/api/diagnostics`, `/api/resilience/status`
- API: `/api/settings/update`, `/api/settings/profiles`, `/api/settings/profiles/active`
- Repo MCP under evaluation: `sequential-thinking`

Status:
- Hide by default, expose only when `KITTY_ENABLE_INTERNAL_API=1`
- Keep route implementations for developer workflows, not for normal product discovery

## Hidden Or Disabled By Default

These should not be exposed in default web-mode discovery until backed by dependable implementations:

- `/api/swarm/*`
- Any UI/help copy that implies swarm execution is ready for production use
- Any command/help entry for features that do not currently resolve to working routes or handlers

Status:
- Hide/404 by default
- Expose swarm only when `KITTY_ENABLE_EXPERIMENTAL_SWARM=1`

## Environment-Only Capabilities

These may exist in the agent environment, but they are not the same thing as Kitty-native capability and should not be presented as such:

- External MCP servers available to Codex/agents outside Kitty's runtime
- Agent-browser and orchestration tools used for operator testing
- Connector-specific apps that are available in the coding environment but not wired into Kitty itself

## Current Prune Policy

- Keep: `filesystem`, `memory`
- Evaluate: `sequential-thinking`
- Hide by default: swarm routes and other non-production-safe eval surfaces
- Prefer explicit inventory and tiering over broad implicit capability claims

## Phase 1 Outcome

- Public default surface is intentionally smaller than the underlying codebase
- Experimental swarm and internal diagnostics are opt-in instead of always exposed
- Help/palette discovery now favors stable commands over historical or pseudo-available ones
