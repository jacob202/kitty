# Kitty Context

Last updated: 2026-04-28

This top-level file is a concise runtime/control pointer. The fuller historical context remains in `docs/KITTY_CONTEXT.md`.

## Current Authority

Follow this order when files conflict:

1. `CURRENT_FOCUS.md`
2. active spec in `specs/`
3. this file
4. `docs/DECISIONS.md`
5. `docs/FILE_GOVERNANCE.md`
6. `docs/PARKED_FEATURES.md`
7. `SESSION_SUMMARY.md`
8. older docs, chat logs, and raw exports

## Current Rule

Raw ideas do not become code. They go through:

raw request -> `kittyintake` -> decision / clarification / parked feature / spec -> `kittybuilder` -> tests -> gates -> completion report -> canonical docs update

## Runtime Boundary

The active migration runtime checkout is:

`/Users/jacobbrizinski/Projects/kitty-system/kitty-app`

Legacy rollback checkout:

`/Users/jacobbrizinski/Projects/kitty`

Do not treat `/Users/jacobbrizinski/Documents/Kitty` as the runnable repo for this pass.

## Interaction Rules

- Be direct.
- Avoid padding.
- Do not claim work is complete without fresh verification.
- Prefer one concrete next action over broad plans.
- Do not build parked features without an approved spec.
