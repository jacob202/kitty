# STATE — Kitty

> Live packet coordination. Read before picking up work. Update when claiming or finishing.

## Branch

claude/packet-017-benefits-rails

## Sessions (2026-07-05)

- Fable overnight/day session — shipped 015 (#103), 021 (#106), 016
  (#107), hardened both (#109); walked Jacob through going fully live
  (see "Done today"). Authored 017 + 025; fixed the 021/022 numbering
  collision (#101/#102 files → 023/024).
- Codex — 008-remainder, in `.worktrees/packet-008-expert-retrieval`
  (unchanged since 2026-07-04 — verify it's still alive before assuming).

## Packet claims

| Packet        | Claimed by          | Status                                               |
| ------------- | ------------------- | ---------------------------------------------------- |
| 008-remainder | Codex 2026-07-04    | 🚧 in `.worktrees/packet-008-expert-retrieval`       |
| 017           | —                   | available — **next build priority** (Wave 4 = move-in day) |
| 025           | —                   | available — Jacob-requested side track; needs his installs half |
## Sessions (2026-07-06)

- opencode — cleaned stale worktrees, shipped packet 008 (#111), applied Track C C1/C5/C6.
- opencode (close-out, ~13:30–13:55) — committed pre-commit cleanup (1abfcef).
- opencode (close-out, ~20:00) — fixed lint, check-description, pytest failures on PR #112; restored prefetcher.py; renamed migration 013→014. PR still CONFLICTING with main — needs merge resolution.

## Packet claims

| Packet        | Claimed by          | Status                                                             |
| ------------- | ------------------- | ------------------------------------------------------------------ |
| 005           | opencode 2026-07-04 | ✅ shipped (#99)                                                   |
| 007           | Jacob (eb3afad)     | ✅ done                                                            |
| 008-remainder | Codex / opencode    | ✅ shipped (#111) — claim released                                 |
| 015           | —                   | ✅ shipped (#103) — Jacob live-verified                          |
| 016           | —                   | ✅ merged (#107) — awaiting Jacob's review of real Bs            |
| 017           | opencode 2026-07-06 | 🔎 PR #112 open — benefits/admin rails + urgent-thing sweep      |

**Rule for other agents:** if the status above is anything other than
`available`, the packet is taken. Pick another. If you need to release a
claim, edit this row to `available` and commit to `main`.

## Done today (2026-07-05)

- 016 shipped (#107) + wave-3 hardening (#109): refresh degrades on model
  failure, PATCH /projects, `./kitty project` subcommand, doctor
  `env:parse`, cold-start timeout.
- **Kitty went fully live on Jacob's Air:** doctor `pass=11 warn=1 fail=0`.
  LiteLLM fixed (venv was missing proxy extras — `pip install
  'litellm[proxy]'`), Gmail OAuth completed (token present),
  `PUSH_IMESSAGE_RECIPIENT` set, chromadb Icon\r gremlin cleared.
  **First real B generated end-to-end.**
- 017 authored executor-ready (Wave 4). 025 authored (imagegen v2,
  local-first, fal retired). 023/024 renumbered + registered (L-CAND-12).

## In flight

- PR #109 (wave-3 hardening) — CI running as of authoring.
- PR #108 — superseded by the wave-4 docs PR; close it.
- 016 review loop: a week of Jacob judging real Bs. Not code.

## Blocked on Jacob

- `.env` line 1 stray quote (cosmetic; doctor `env:parse` in #109 names it).
- Register his 2–3 real projects (`./kitty project add`) and start judging Bs.
- 025 installs half (Draw Things API server, model downloads) when that
  packet builds. **Preflight: his live imagen checkout is under
  `~/Projects/`, NOT this repo's `mcp/imagen/` copy — see 025 step 0.**
## Done recently

- 004 shipped (#98) — HomeState console replaces DashboardHome.
- 005 shipped (#99).
- 007 shipped (eb3afad, Jacob) — packet.delegate generator.
- 008 shipped (#111) — expert retrieval; worktree cleaned.
- Track C C1 — Removed Modules pattern applied to 6 gateway modules.
- Track C C5 — `context_assembler.py` tightened; folded `parts.py`.
- Track C C6 — doc sprawl reduced; docs reorganized into `docs/phases/`, `docs/retired/`, and `docs/plans/`.
- Track B (full) — codemap, ADRs, npm fix, repo cleanup, pre-commit Icon block. Committed on main.
- C3 cron DB consolidation (live) — `data/cron_schedules.db` → `data/kitty/kitty.db:cron_schedules`. 1242 tests pass, backup verified. Direct push to main.
- Prefetcher — `gateway/prefetcher.py` (predictive cache + cron warm action). 8 tests.
- Memory Weave port (from salvage) — migration 013 + all 11 public methods + 17 tests.
- Stale worktrees cleaned: `kitty-packet-014`, `feat-packet-005-mail-connector`.
| Packet | Claimed by | Status |
| ------ | ---------- | ------ |
| 005 | opencode 2026-07-04 | ✅ shipped (#99) |
| 007 | Jacob (eb3afad) | ✅ done |
| 008-remainder | Codex / opencode | ✅ shipped (#111) |
| 015 | — | ✅ shipped (#103) — Jacob live-verified |
| 016 | — | ✅ merged (#107) |
| 017 | opencode 2026-07-06 | ✅ merged (#112) |
| 020 | antigravity 2026-07-07 | 🚧 claimed — GitHub connector |

## Facts from Jacob (load-bearing — read before talking to him)

- Phone-first; iOS pushes only channel that works (D12). Now live.
- He conflates "spec exists" with "built" — answer status questions with
  the registry legend's words.
- Missed student-loan deadline June 2026 (~$600) — trigger for 017. "There's
  something urgent. I don't know what it is."
- Disability (SAID/CDB/DTC) is the income track; job search parked (019).
  Recovery expert pack strictly opt-in; Kitty does not raise it.
- 2026-07-05: "magic kitty" — cross-project insight is the point (D13,
  packet 022). Basic-then-magic sequencing was his explicit call.
- fal is retired for imagegen (too expensive) — local-first, D25 packet.
- Kitty's house: the broken-screen MacBook Air, headless, on ethernet.

## Next actions

1. Merge #109 when CI is green; then the wave-4 docs PR.
2. First free executor: build 017 (claim it here first).
3. Jacob: register real projects, judge Bs for a week (closes 016).
4. 025 build when Jacob's ready to do his installs half alongside.
1. Review and merge PR #112 (017 — benefits rails) when CI green.
2. Packet 018 (expert packs) or 020 (GitHub connector) — next planned active packets after 017 lands.
3. C3-4 cleanup after 2026-07-13 (one-week stable window per C3 plan).
4. Wire `MemoryWeave` into `unified_context`/`context_assembler` call paths (next session, or as a small packet).
5. Salvage port queue: pick one (recommend `context_hierarchy.py` first — smallest, 284 LOC) when fresh session energy is available.
## Sessions (2026-07-07)

- Fable (remote, prototype sprint) — nav shell rebuilt (8 tabs: home / chat
  / projects / docs / providers / agents / image lab / settings), new
  ProjectsPanel (surfaces /projects/{id}/next), DocumentsPanel
  (knowledge.py wired: sources/search/ingest), ProviderCenter
  (plugins/MCP live + honest external-lane cards), SettingsPanel stub,
  chat save-state indicator (saving/saved/failed/offline + retry, error
  path now persists the user message), fixed fetchImageStatus fake
  "available" bug, added `dev:tailnet` / `make ui-tailnet` (dev binds
  loopback — that was the missing Tailscale step). 85 UI tests + build
  green; screenshots verified against a live gateway in the container.
  Branch `claude/kitty-prototype-sprint-srs5bl`.

## Blocked on

- Merge conflict resolution on PR #112

## Next actions

1. Resolve merge conflict on PR #112 — rebase branch onto main or use `gh pr merge`
2. Clean up macOS `Icon` files from `.git/` directories
3. Get CI green
4. Merge PR #112
5. Claim next packet from the registry
