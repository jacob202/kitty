# Open Loops

Last updated: 2026-04-29

## Active

- Confirm whether "Canadian-first" sourcing and budget-conscious recommendations should become a permanent Kitty preference. **Needs user confirmation** (confidence: low)
- Review unrelated `src/tools/image_gen.py` diff separately; it changes Draw Things endpoint/payload behavior and should not ride along with workspace separation.
- Decide when to execute the physical `kitty-system` split after the dirty tree is clean or intentionally checkpointed.

## Resolved

- `$129/month` target pricing claim is treated as irrelevant/noisy assistant-authored extraction for this project state. Ignore unless reintroduced by explicit user business spec. (resolved 2026-04-30)
- Bank transaction / budget leak analysis is parked behind privacy boundaries and manual-paste-only constraints. It is no longer an open loop. (resolved 2026-04-30)
- MCP agent bundle lane reviewed and remains parked (no adoption into `main`); see `docs/MCP_AGENT_BUNDLE_TRIAGE_2026-04-30.md`. (resolved 2026-04-30)

## Waiting

- Approved spec for any runtime source changes.
