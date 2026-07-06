# STATE — Kitty

> Live packet coordination. Read before picking up work. Update when claiming or finishing.

## Goal

Execute open implementation packets without duplicate agent work.

## Branch

main

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
