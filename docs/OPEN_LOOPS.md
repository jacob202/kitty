# Open Loops

Last updated: 2026-05-06

## Active

- ~~**Phase `2C` tool runtime alignment:** align interfaces and wrappers after `2A.1` memory foundation is stable.~~ ✅ COMPLETED 2026-05-06
  - execution packet: `docs/superpowers/plans/2026-05-phase2-low-capability-execution.md` (Task Cards `2C-1..2C-4`)
  - **2C-1 COMPLETE**: Inventory done, report at `docs/audits/tool-runtime-alignment-inventory-2026-05-06.md`
  - **2C-2 COMPLETE**: ToolRuntime implemented, 15 tests passing
  - **2C-3 COMPLETE**: Permission bridge integrated (ToolRegistry → ToolRuntime), test added
  - **2C-4 IN PROGRESS**: Integration and regression gate (strict gate passed, updating tracking docs)
- **Strict pytest gate blocker cleanup:** resolve unrelated metadata guard files (`tests/memory/Icon*`) so strict gates can run without fallback.
- **Unified Command System (Candidate C):** Consolidate slash commands (`/stuck`, `/brief`, `/scrape`, etc.) from `web.py` and `dispatcher.py` into a deep `CommandEngine`. This was attempted but shelved due to subagent failure and time constraints. Must be picked up to complete the architectural deepening roadmap.
- **Gemini architecture trio (indexed):** `docs/plans/gemini-architecture-priorities-2026-04-30.md` — grep tag `GEMINI-ARCH-PRIORITIES` (Tool runtime → Specialist runtime → builder/spec velocity).

## Resolved

- **Phase `2A.1` Wave 3 (retrieval adapter contract):** completed with `retrieval_adapter.py`, adapter-aware router path, and contract tests (`20 passed` focused with `--noconftest`) on 2026-05-06.
- **Phase `2A.1` Wave 2 (`StorageRouter` + retrieval regression):** completed with router contract + context-service fallback + focused tests (`16 passed` with `--noconftest`) on 2026-05-06.
- **Phase `2B` token instrumentation:** completed with per-call token JSONL telemetry in `scripts/kitty_builder.py`, `/tokens` summary command, and analytics helper `scripts/report_builder_token_usage.py` (`106 passed` focused `test_kitty_builder.py`) on 2026-05-06.
- Physical `kitty-system` split → **Retired after consolidation** — single canonical checkout is `/Users/jacobbrizinski/Projects/kitty`; see `docs/DECISIONS.md` D-0014 and `docs/PARKED_FEATURES.md` (Physical `kitty-system` Split).
- "Canadian-first" assistant persona → **Confirmed permanent** (commit `40427e1`)
- `$129/month` target pricing → treated as noisy assistant-authored extraction; ignored unless reintroduced by explicit user business spec (resolved 2026-04-30)
- Bank transaction / budget leak analysis → parked behind privacy boundaries and manual-paste-only constraints (resolved 2026-04-30)
- Review unrelated `src/tools/image_gen.py` diff → reviewed and adopted (resolved 2026-04-30)
- MCP agent bundle lane → reviewed, remains parked; see `docs/MCP_AGENT_BUNDLE_TRIAGE_2026-04-30.md` (resolved 2026-04-30)

## Waiting

- Approved spec for any runtime source changes outside the active Phase 2 plan.
