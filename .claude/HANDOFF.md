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
KB-S5 is implemented and audited locally on `feat/kb-s5-run-loop` (not pushed):
```
./kitty builder initiative run <id> --worker-command '["opencode","run"]' [--publish] [--max-attempts N] [--max-runtime S]
./kitty builder initiative pause <id> [--reason ...]
./kitty builder initiative resume <id>
```
Loop drives next eligible packet (S2/S3) then optional KB-S4b publish; repeats until no packet eligible or budget/pause halts. Restart reconciles stale leases/runs; PR-merge `reconcile-merges` advances dependency packets to DONE. Publish and queue reconciliation now strip ambient GitHub tokens, scope `gh` to the task worktree/base, gate on final shadow reports, and fail on non-success check rollups.

Verification: focused Builder suites 340 passed; full Ruff and touched-file mypy pass. The lint job is now blocking in `.github/workflows/tests.yml`.

## Do not
- Reverse-split #143
- Let workers push/PR (publish is operator-gated; `gh` runs token-stripped)
- Push or open the PR without Jacob's explicit approval.
- Resume without reading this + STATE
