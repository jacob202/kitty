# Kitty documentation

Last updated: 2026-05-02

## Read first (authority)

When instructions conflict, follow the order in `docs/LAYER0_CONTROL_PLANE.md` (summarized here):

1. Jacob’s latest message  
2. `AGENTS.md`  
3. `CLAUDE.md`  
4. `docs/LAYER0_CONTROL_PLANE.md`  
5. `CURRENT_FOCUS.md`  
6. `TASKS.md`  
7. `docs/DECISIONS.md`  
8. Approved spec for the current task  
9. `docs/AGENT_COORDINATION.md` (coordination only; long file)

## Canonical repo

**Runnable git checkout:** `/Users/jacobbrizinski/Projects/kitty`

Older docs may mention `kitty-system/kitty-app` or a “migrated” workspace. That migration was **closed** in favor of this single tree (2026-05-01). Treat those mentions as **history** unless a new decision explicitly reopens migration work.

## What lives where

| Area | Purpose |
|------|---------|
| Repo root (`CURRENT_FOCUS.md`, `TASKS.md`, `KITTY_CONTEXT.md`) | Session focus and quick pointers |
| `docs/DECISIONS.md` | Durable decisions |
| `docs/CONTINUITY_STANDARD.md` | Required run-end checkpoint protocol for takeover safety |
| `docs/PARKED_FEATURES.md` | Intentionally deferred work |
| `docs/archive/` | Historical handoffs, merge-gate runs, retired audits |
| `docs/audits/` | Reports and inventories |
| `docs/plans/`, `docs/superpowers/plans/` | Planning drafts (verify against decisions before implementing) |
| `docs/plans/phase2-build-plan-meta-analysis-2026-05-06.md` | Phase 2 quality/token analysis and hardening rationale |
| `docs/plans/kittybuilder-effectiveness-meta-analysis-2026-05-06.md` | Approved KittyBuilder effectiveness/context-engineering meta-analysis |
| `docs/plans/kittybuilder-effectiveness-research-sources-2026-05-06.md` | Source links and takeaways for KittyBuilder agent/orchestration research |
| `docs/superpowers/plans/2026-05-06-kittybuilder-intent-compiler.md` | Implementation plan for Intent Compiler, Context Compiler, health preflight, and Evidence Ledger |
| `docs/superpowers/plans/2026-05-phase2-low-capability-execution.md` | Deterministic low-capability execution packet for `2C` |
| `specs/` | Approved work specs |

## Stale-doc rule of thumb

If a doc says the active runtime is outside `/Users/jacobbrizinski/Projects/kitty`, assume it is **out of date** unless `docs/DECISIONS.md` has a newer entry saying otherwise. Prefer editing canonical files above instead of duplicating a second “truth.”

## Local troubleshooting

If Python fails importing Chroma / `jsonschema` with `JSONDecodeError` on empty content, macOS may have dropped **`Icon\r`** files inside `venv/` (folder metadata). Remove them, for example:  
`find venv/lib/python3.12/site-packages/jsonschema_specifications -name 'Icon*' -delete`  
then retry imports. If problems persist, reinstall the affected package in the venv.
