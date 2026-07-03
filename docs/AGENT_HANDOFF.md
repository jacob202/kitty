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
spec-complete — active phase, see
`docs/superpowers/specs/2026-07-02-console-home-phase-design.md`), 005 (mail
connector — §16.2 decided 2026-07-02: Gmail API read-only, D11), 007
(delegation packet generator), 008 remainder (expert retrieval).

## Known Issues (do not hide, do not "fix" without reading first)

| Issue                               | Where                                                                                                                                                              | Status                                                                                                                                                                                                  |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run` broken on Jacob's Mac     | `gateway/kitty-chat` (repo-wide)                                                                                                                                   | Exits 194 silently (node 26.4/npm 11.17, repo-specific, un-root-caused). Use `./node_modules/.bin/vitest run` and `node node_modules/next/dist/bin/next build` directly.                                |
| 6 UI test failures on main          | `tests/SessionSidebar.test.tsx` (×5), `tests/gatewayIntegration.test.tsx` (×1)                                                                                     | Invisible until 2026-07-02: kitty-chat tests run in no CI job and `npm run` was broken. Console-home phase step 0 fixes tests + adds the CI job.                                                        |
| Local-only test failures (CI green) | `tests/test_action_queue.py::test_t0_executes_from_proposed_and_records_result`, `tests/test_state_composer.py::test_real_sources_compose_against_isolated_stores` | Tests leak real local `data/` state (todo store, signal stores) instead of isolating. Pass on CI where data/ is empty. Test-isolation bug, not a code bug.                                              |
| macOS `Icon\r` Finder artifacts     | every directory in the repo                                                                                                                                        | Broke pytest collection in `venv/` and `git fetch` (`.git/refs/Icon` read as a corrupt ref). Cleaned from `venv/` + `.git/` 2026-07-02; they may regenerate. Fix: `find <dir> -name $'Icon\r' -delete`. |

Resolved 2026-07-02 (hygiene batch, Jacob signed off): broken
`tests/test_llm_client_alt_ua.py` deleted · empty `tests/fakes/` deleted ·
stale `.kitty/swarm-status.json` deleted · orphaned `data/loops.db` deleted ·
workflow configs committed · `hermes-webui/` moved to `~/Projects/hermes-webui`
· 8 merged worktrees + local/remote branches pruned · `backup-local-main-0628`
confirmed already on origin.

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
009–013 shipped; 004 (active phase), 005 (D11: Gmail API read-only), 007, and
008-remainder all unblocked.

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
python3.12 -m pytest tests/ -q --tb=short
# npm run is broken on this machine (exit 194) — use the direct binaries:
cd gateway/kitty-chat && ./node_modules/.bin/vitest run && node node_modules/next/dist/bin/next build
python3.12 -m mypy gateway/ --ignore-missing-imports --no-error-summary 2>&1 | tail -1
```

Expected local: ~1010 passed, 2 failed (the two data-leak tests above — they
pass on CI). Before merging any PR, check **check_runs**, not the combined
status — #70 merged red and broke main; that's the failure mode this rule
exists for.
