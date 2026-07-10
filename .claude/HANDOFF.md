# Handoff — 2026-07-10

## Context
Jacob authorized merge of mega PR #143 (after CI fix), then dealer's-choice follow-ups. Agent stood down after S4 complete.

## On main
1. Builder initiative/queue/runner/loop (S1–S3) + chat lifecycle/artifacts/runtime (bundled in #143)
2. Merge detection + PR sync (#144)
3. Operator publish: `./kitty builder queue publish <task_id>` (#145)

## Operator surface (S4)
```
./kitty builder queue publish <id> [--remote origin] [--base main] [--title ...] [--dry-run]
./kitty builder queue sync-pr
./kitty builder queue reconcile-merges
```
Never auto-merges. Workers do not get GitHub tokens.

## Resume here
Implement **KB-S5** only — continuation loop above ok packets; small PR, full builder pytest + ruff/mypy.

## Do not
- Reverse-split #143
- Let workers push/PR
- Resume without reading this + STATE
