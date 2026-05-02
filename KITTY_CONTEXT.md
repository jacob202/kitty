# Kitty Context

Last updated: 2026-05-01

This top-level file is a concise runtime/control pointer. `docs/LAYER0_CONTROL_PLANE.md` is the current authority map for Layer 0 cleanup.

## Current Authority

Follow this order when files conflict:

1. Jacob's latest live instruction
2. `AGENTS.md`
3. `CLAUDE.md`
4. `docs/LAYER0_CONTROL_PLANE.md`
5. `CURRENT_FOCUS.md`
6. active spec in `specs/`
7. `docs/DECISIONS.md`
8. older docs, chat logs, and raw exports

## Current Rule

Raw ideas do not become code. They go through:

raw request -> `kittyintake` -> decision / clarification / parked feature / spec -> `kittybuilder` -> tests -> gates -> completion report -> canonical docs update

## Runtime Boundary

The canonical runnable checkout is:

`/Users/jacobbrizinski/Projects/kitty`

Retired/stale unless Jacob explicitly reopens migration work:

`/Users/jacobbrizinski/Projects/kitty-system/kitty-app`

Do not treat `/Users/jacobbrizinski/Documents/Kitty` as the runnable repo for this pass.

## Interaction Rules

- Be direct.
- Avoid padding.
- Do not claim work is complete without fresh verification.
- Prefer one concrete next action over broad plans.
- Do not build parked features without an approved spec.
