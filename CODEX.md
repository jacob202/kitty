# Kitty - Codex Guide

Start with `START_HERE.md`, then read `docs/PROJECT_STATUS.md` before making changes.

## How To Work Here

- Anchor every action in `/Users/jacobbrizinski/Projects/kitty`.
- Treat `/Users/jacobbrizinski/Documents/Kitty` as stale unless proven otherwise.
- Check `git status --short --branch` before editing.
- Preserve unrelated dirty work. Stash only with a descriptive message when needed to isolate branches.
- Use `apply_patch` for manual file edits.
- Never print `.env` values or runtime data contents unless Jacob explicitly asks.

## Current Priority

Workflow polish and source-of-truth cleanup. Use `docs/PROJECT_STATUS.md` for live branch status, and treat Phase B/Phase C plan docs as reference material rather than default first reads. Do not add cloud auth, push notifications, new agent dashboards, or new storage systems while local workflow still has rough edges.

## Completion Standard

Before saying work is complete, run the smallest command that proves the claim and include the result. If verification is blocked, say what blocked it and what remains unproven.
