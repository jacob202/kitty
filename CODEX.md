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

Phase B prep: one storage story, one canonical documentation path, and a reliable agent handoff loop. Do not expand TELOS, PAI, agents, mobile, or cloud sync during this phase.

## Completion Standard

Before saying work is complete, run the smallest command that proves the claim and include the result. If verification is blocked, say what blocked it and what remains unproven.

Before merging a PR, read the Actions check runs and confirm each required job passed — not just the combined commit status (they are different surfaces; a green status can hide failing check runs). After any non-trivial merge, compile/import the touched files before declaring done. See `docs/LEARNINGS.md` L-CAND-6/7/8.
