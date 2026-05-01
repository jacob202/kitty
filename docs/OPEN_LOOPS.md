# Open Loops

Last updated: 2026-05-01

## Active

- **Unified Command System (Candidate C):** Consolidate slash commands (`/stuck`, `/brief`, `/scrape`, etc.) from `web.py` and `dispatcher.py` into a deep `CommandEngine`. This was attempted but shelved due to subagent failure and time constraints. Must be picked up to complete the architectural deepening roadmap.
- **Gemini architecture trio (indexed):** `docs/plans/gemini-architecture-priorities-2026-04-30.md` — grep tag `GEMINI-ARCH-PRIORITIES` (Tool runtime → Specialist runtime → builder/spec velocity).
- Decide when to execute the physical `kitty-system` split after the dirty tree is clean or intentionally checkpointed.

## Resolved

- "Canadian-first" assistant persona → **Confirmed permanent** (commit `40427e1`)
- `$129/month` target pricing → treated as noisy assistant-authored extraction; ignored unless reintroduced by explicit user business spec (resolved 2026-04-30)
- Bank transaction / budget leak analysis → parked behind privacy boundaries and manual-paste-only constraints (resolved 2026-04-30)
- Review unrelated `src/tools/image_gen.py` diff → reviewed and adopted (resolved 2026-04-30)
- MCP agent bundle lane → reviewed, remains parked; see `docs/MCP_AGENT_BUNDLE_TRIAGE_2026-04-30.md` (resolved 2026-04-30)

## Waiting

- Approved spec for any runtime source changes.
