# Cleanup Candidates

Last updated: 2026-04-28

This file records cleanup candidates only. It is not permission to delete, move, archive, or rewrite files.

## Rules

- Never clean `src/`, `web.py`, `data/`, `config/specialists/`, or canonical control docs without an approved spec.
- Prefer dry-run inspection before removal.
- Preserve agent histories, eval artifacts, and benchmark history until reviewed.
- Run the validation command before and after any cleanup.

## Highest-Confidence Safe Lane

These are generated artifacts and can be cleaned after their validation command passes.

| Path | Type | Validation before cleanup |
| --- | --- | --- |
| `.DS_Store` | macOS Finder metadata | `git status --short --ignored .DS_Store` |
| `__pycache__/` | Python bytecode cache | `find __pycache__ -maxdepth 1 -type f -print` |
| `scripts/__pycache__/` | Python bytecode cache | `find scripts/__pycache__ -maxdepth 1 -type f -print` |
| `tests/__pycache__/` | Python bytecode cache | `find tests/__pycache__ -maxdepth 1 -type f -print` |
| `.pytest_cache/` | pytest cache | `/opt/homebrew/bin/python3.12 -m pytest tests/test_builder_intake.py tests/test_file_governance.py tests/test_context_pack_generator.py tests/test_kitty_builder.py -q --tb=short` |
| `garage-ui/.pytest_cache/` | pytest cache | `find garage-ui/.pytest_cache -maxdepth 2 -type f -print` |
| `garage-ui/.next/` | Next.js build cache | `cd garage-ui && npm run build` |
| `.aider.tags.cache.v4/` | Aider index cache | `git check-ignore -v .aider.tags.cache.v4` |

## Safe Only After Staleness Check

| Path | Type | Validation before cleanup |
| --- | --- | --- |
| `.kitty.pid` | runtime PID file | `test -f .kitty.pid && ps -p "$(cat .kitty.pid)"` |
| `.kitty.log` | runtime log | `tail -100 .kitty.log` |
| `logs/` | runtime logs | `find logs -maxdepth 2 -type f -print -exec tail -20 {} \;` |
| `venv/` | Python virtualenv | `/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short` |
| `garage-ui/node_modules/` | npm dependencies | `cd garage-ui && npm ci && npm run build` |

## Review Before Cleanup

| Path | Type | Why review is required |
| --- | --- | --- |
| `.aider.chat.history.md` | agent history | May contain recovery context. Archive or extract useful context before deletion. |
| `.aider.input.history` | agent history | May contain command/input recovery context. |
| `.crush/` | agent/tool state | Contains local state/log database and is not clearly rebuildable. |
| `benchmarks/results/` | benchmark results | May preserve useful model comparison evidence. |
| `benchmark_log.txt` | benchmark artifact | Tracked historical log. |
| `model_test_results_20260427_111507.txt` | model test artifact | Tracked dated model result. |
| `eval_snapshots/` | eval snapshots | May help regression review. |
| `evals/artifacts/*.json` | eval artifacts | Append-only eval storage; keep unless a retention policy exists. |
| `refactor_reports/` | report directory | Empty-looking, but validate before removal. |
| `.worktrees/` | worktree holder | Check `git worktree list` before cleanup. |
| `consolidated-skills/` | skill material candidate | May be intentional local tooling. |
| `skills/` | skill material | May be intentional local tooling. |
| `.claude/` | agent config | May drive hooks/settings. |
| `.firecrawl/` | tool config/state | Validate contents before cleanup. |

## Mac Icon Metadata In Protected Source

`Icon\r` files were detected under protected trees, including `src/`, `data/`, and `src/tools/superpowers/skills/orchestration/`.

Do not remove these under the current protected-file rule. If cleanup is desired, create a temporary non-code-artifact waiver spec that explicitly allows deleting only `Icon\r` metadata files under protected trees, then run:

```bash
find src/tools/superpowers/skills/orchestration -name 'Icon?' -type f -print
bash scripts/run_gates.sh
```

## Next Safe Cleanup Spec

Completed under `specs/tiny-generated-cache-cleanup.spec.md`:

- root `.DS_Store`
- root `__pycache__/`
- `scripts/__pycache__/`
- `tests/__pycache__/`
- `.pytest_cache/`
- `.aider.tags.cache.v4/`

Validation:

```bash
bash scripts/run_gates.sh
git status --short
```

Next cleanup should remain read-only/spec-first. Do not include `Icon\r`, `venv/`, `garage-ui/.next/`, `garage-ui/node_modules/`, `eval_snapshots/`, `refactor_reports/`, `skills/`, or tracked `src/space_kitty` deletions in a generated-cache cleanup.
