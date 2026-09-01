# Kitty - Codex Guide

Start with `START_HERE.md` and follow its canonical reading order before making changes.

## How To Work Here

- Anchor every action in `/Users/jacobbrizinnski/Projects/kitty`.
- Treat `/Users/jacobbrizinski/Documents/Kitty` as stale unless proven otherwise.
- Check `git status --short --branch` before editing.
- Preserve unrelated dirty work. Stash only with a descriptive message when needed to isolate branches.
- Use `apply_patch` for manual file edits.
- Never print `.env` values or runtime data contents unless Jacob explicitly asks.

## Current Priority

Execute the approved KTF-001 mission in `docs/ACTIVE_MISSION.md` according to the sole active sequence in `docs/ROADMAP.md`. Finish the trustworthy delivery and resume-loop proof before expanding feature scope.

## Reviewer Routing

Do not let a required independent review stall on free-provider roulette. Outside
an explicit `--free` Builder lane, make one clean free attempt at most, then use
`openrouter/deepseek/deepseek-v4-flash` for review if the free provider errors,
overloads, or stays silent through the normal startup window. Jacob explicitly
approved the small paid spend. In paired worker/reviewer flows, keep reviewer
and implementer model families independent; explicit `--free` never falls back
to paid.
OpenRouter is the preferred router for reviewer routing. AgentRouter is dead; do not recommend it. Freebuff and 9Router are optional only and must never be dependencies. Do not prefer `openrouter/deepseek/deepseek-v4-flash-0731` merely because it is newer; repeated runs observed it stalling.


## Completion Standard

Before saying work is complete, run the smallest command that proves the claim and include the result. If verification is blocked, say what blocked it and what remains unproven.

Before merging a PR, read the Actions check runs and confirm each required job passed — not just the combined commit status (they are different surfaces; a green status can hide failing check runs). After any non-trivial merge, compile/import the touched files before declaring done. See `docs/LEARNINGS.md` L-CAND-6/7/8.
