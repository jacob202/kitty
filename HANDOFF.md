# Kitty — Handoff

**Rule: this is the only handoff file.** Update it in place at the end of a session;
move superseded versions to `docs/archive/` (see `docs/LESSONS.md` #9). Every number
below must come from a command actually run.

**Last updated:** 2026-06-12

## Current state

- **Stack:** Gateway (FastAPI `:5001`) + LiteLLM proxy (`:8001`) + kitty-chat UI
  (Next.js `:3000`). Start with `bash gateway/start_all.sh`; check with
  `bash gateway/status_all.sh`; stop with `bash gateway/stop_all.sh`.
- **The abandoned Open WebUI path was removed** (2026-06-12): council graph,
  MCP council server, OWUI filters/library tools/actions, doctor, OWUI shell
  scripts, OWUI-coupled curation scripts, and the accidentally committed
  `$HOME/` directory (which contained `webui.db` and a `.webui_secret` —
  **rotate that secret if Open WebUI is ever used again**).
- **Ports are reconciled:** the gateway is `:5001` everywhere (scripts, config,
  docs). `GATEWAY_PORT` env var overrides.
- **Tests:** run `python3.11 -m pytest tests/ -q --tb=short` — no `--ignore`
  flags. CI runs the same bare command.

## Open items

- **Pre-existing frontend test failures** (verified present before the 2026-06-12
  cleanup, not caused by it): `cd gateway/kitty-chat && npm test` → 66 passed,
  **6 failed** (TerminalStrip ×3, gatewayIntegration RightPanel ×2,
  DashboardHome ×1). TASKS.md's "36 passed" is stale — the suite has 72 tests now.

- `scripts/curation/` retains the file-level book tooling (OCR, dedupe,
  mapping); the OWUI-KB-coupled scripts were deleted. If book ingestion comes
  back, it should target the gateway's ChromaDB knowledge store.
- Current priority per `docs/DECISIONS_AND_ROADMAP.md`: reliability and
  consolidation, not new features.
