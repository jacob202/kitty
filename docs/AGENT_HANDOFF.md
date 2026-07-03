# Agent Handoff

**Date: 2026-07-02**
**Branch:** `main`
**Canonical repo:** `/Users/jacobbrizinski/Projects/kitty`

---

## Where Things Stand

The 2026-07-02 swarm landed everything it set out to do. PRs #70–#77 are all
merged. **Caveat:** #70 merged with red checks _after_ #75/#77, overwriting
`routes/dream.py`, `routes/loops.py`, and the `SignalsAdapter` contract and
breaking main (gateway startup ImportError + red CI). The reconcile fix
restored #75's cron-backed loops, rewired `/insights` to
`gateway/dream_insights.py`, removed the duplicate `gateway/loops.py` (which
re-seeded the fake `daily-brief` rows #75 deleted), and updated the signals
tests to the new `Item` adapter contract.

| PR  | What landed                                                        | Packet        |
| --- | ------------------------------------------------------------------ | ------------- |
| #70 | Gateway deepening — storage seam, LLM dispatcher, read path        | —             |
| #71 | `./kitty resume` subcommand                                        | 006           |
| #72 | Privacy boundary (D10) enforced in `llm_client`                    | 012           |
| #73 | `/knowledge/{ingest,sources,search}` routes                        | 008 (partial) |
| #74 | `POST /capture/file` + UI drop zone                                | 010           |
| #75 | Loops + insights routes de-faked (real sources, no hardcoded data) | 009           |
| #76 | Daily brief scheduler                                              | 011           |
| #77 | web_monitor + nudges wired to signal store                         | 013           |

PR #78 was closed unmerged on 2026-07-02: it was cut from a stale
`insights.py` and would have removed imports that are now load-bearing.

**No open PRs.** The packet queue's unblocked work: 004 (state home surface,
spec-complete), 007 (delegation packet generator), 008 remainder (expert
retrieval). 005 (mail connector) still blocked on Jacob's §16.2 decision.

## Known Issues (do not hide, do not "fix" without reading first)

| Issue                               | Where                                                                                                                                                              | Status                                                                                                                                                                                                     |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Broken untracked test file          | `tests/test_llm_client_alt_ua.py`                                                                                                                                  | Imports `_agentrouter_post_processor` which doesn't exist; fails collection. Untracked — delete or fix.                                                                                                    |
| Local-only test failures (CI green) | `tests/test_action_queue.py::test_t0_executes_from_proposed_and_records_result`, `tests/test_state_composer.py::test_real_sources_compose_against_isolated_stores` | Tests leak real local `data/` state (todo store, signal stores) instead of isolating. Pass on CI where data/ is empty. Test-isolation bug, not a code bug.                                                 |
| macOS `Icon\r` Finder artifacts     | every directory in the repo                                                                                                                                        | Broke pytest collection inside `venv/` (cleaned 2026-07-02). Repo-level ones left in place — may be intentional folder icons. If pytest breaks with `NotADirectoryError … Icon`, delete them from `venv/`. |
| Untracked workflow configs          | `.pre-commit-config.yaml`, `.prettierrc`, `.prettierignore`, `.github/dependabot.yml`, `gateway/kitty-chat/eslint.config.mjs`                                      | From the workflow-optimization session — never committed. Commit or discard.                                                                                                                               |
| Nested foreign repo                 | `hermes-webui/`                                                                                                                                                    | Separate project with its own `.git` sitting inside kitty. Move out of the repo.                                                                                                                           |
| Stale worktrees + branches          | `.claude/worktrees/feat-*` (7), `.worktrees/gateway-deepening`                                                                                                     | All correspond to merged PRs. Safe to `git worktree remove` + delete branches.                                                                                                                             |
| Stale swarm state                   | `.kitty/swarm-status.json`                                                                                                                                         | References phase-2/3/4 worktrees that no longer exist. Delete.                                                                                                                                             |
| Local-only branches                 | `codex/raycast-quick-capture`, `backup-local-main-0628`                                                                                                            | Raycast capture merged as #69; backup branch still holds unlanded history.                                                                                                                                 |

## Services

| Service           | Port | Start command |
| ----------------- | ---- | ------------- |
| Gateway (FastAPI) | 8000 | `./kitty up`  |
| LiteLLM proxy     | 8001 | `./kitty up`  |

`./kitty doctor --json` is the health oracle. Run it before claiming anything
is broken or working.

## Packet Queue

Work is organised into numbered packets in `docs/packets/`. Read
`docs/packets/README.md` for the queue state. As of 2026-07-02: 001–003, 006,
009–013 shipped; 004/007/008-remainder unblocked; 005 blocked on Jacob.

## Decisions in Force

See `docs/DECISIONS.md`. Most relevant to new work:

- **D3**: All context reads go through `memory_graph.py`. Do not bypass.
- **D7**: `storage_router.py` is a thin write seam only. Do not expand it.
- **D8**: Ruff enforces E/F/W/I but not E501.
- **D10**: Privacy boundary in the router — private-tagged content must not
  route to cloud models (shipped in #72).

## Verification

Run these before calling anything done:

```bash
python3.12 -m pytest tests/ -q --tb=short --ignore=tests/test_llm_client_alt_ua.py
cd gateway/kitty-chat && npm test && npm run build
python3.12 -m mypy gateway/ --ignore-missing-imports --no-error-summary 2>&1 | tail -1
```

Expected local: ~1010 passed, 2 failed (the two data-leak tests above — they
pass on CI). Before merging any PR, check **check_runs**, not the combined
status — #70 merged red and broke main; that's the failure mode this rule
exists for.
