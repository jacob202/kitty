# Open Loops

Last updated: 2026-04-29

## Active

- Confirm whether "Canadian-first" sourcing and budget-conscious recommendations should become a permanent Kitty preference. **Needs user confirmation** (confidence: low)
- Review the dirty KnowledgeGetter / MCP lane and decide whether to reject it, park it, or create a new approved Phase 6+ spec after current stabilization gates.
- Review the wider dirty MCP agent bundle: KnowledgeGetter, Librarian, VisionGuide, CodeReviewer, Overnighter, requirement additions, generated `librarian_db/`, and local agent skill installs.
- Review unrelated `src/tools/image_gen.py` diff separately; it changes Draw Things endpoint/payload behavior and should not ride along with workspace separation.
- Decide when to execute the physical `kitty-system` split after the dirty tree is clean or intentionally checkpointed.

## Resolved

- `$129/month` target pricing claim is treated as irrelevant/noisy assistant-authored extraction for this project state. Ignore unless reintroduced by explicit user business spec. (resolved 2026-04-30)
- Bank transaction / budget leak analysis is parked behind privacy boundaries and manual-paste-only constraints. It is no longer an open loop. (resolved 2026-04-30)

## Waiting

- Approved spec for any runtime source changes.
