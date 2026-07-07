# STATE — Kitty

> Live packet coordination. Read before picking up work. Update when claiming or finishing.

## Branch

claude/packet-018-expert-packs

## Sessions (2026-07-07)

- Fable (prototype sprint) — nav shell rebuilt (8 tabs), ProjectsPanel, DocumentsPanel, ProviderCenter, chat save-state indicator, Tailscale bind. Branch `claude/kitty-prototype-sprint-srs5bl`. Merged as #113.
- OpenCode — fixed memory_weave typecheck errors, created PR #115 (test fixture cleanup, open).
- Antigravity — added WeatherTile/WorkingSources, whimsy styling, crayon borders, cat eyes. Branch `claude/packet-020-github-connector` (includes GitHub connector).
- Models working on packet 018 (expert packs). **Leave alone.**

## Latest merges

| PR | What | CI |
| -- | ---- | -- |
| #115 | fix(tests): test_brief_deadlines.py duplicate seed | ⏳ check-description fixed, re-running |
| #114 | UI sprint pass 2 — weather, sources, cat eyes | ✅ |
| #113 | UI sprint — nav shell, DocumentsPanel, ProviderCenter, save state, memory_weave typefix | ✅ |
| #112 | 017 benefits rails — deadlines, sweep, watch, routes | ✅ |
| #111 | 008 knowledge expert retrieval | ✅ |
| #110 | docs: wave-4 authoring (017 spec, 025 spec) | ✅ (typecheck fixed by #113) |
| #109 | projects hardening — timeout, PATCH, degraded next-step | ✅ |

## Packet claims

| Packet | Status |
| ------ | ------ |
| 001–016 | ✅ all shipped |
| 017 (benefits rails) | ✅ shipped (#112) |
| 018 (expert packs) | 🚧 claimed — models building. **Leave alone.** |
| 020 (GitHub connector) | 🚧 claimed — Antigravity |
| 022 (magic kitty) | 🧭 next after 025 |
| 023 (memory taste) | 🧭 planned |
| 024 (chat log idea mine) | 🧭 planned |
| 025 (imagegen v2) | 🧭 **next build** — local-first, Draw Things, fal retired |

**Rule for other agents:** if the status above is anything other than `available`, the packet is taken.

## Facts from Jacob (load-bearing)

- Phone-first; iOS pushes only channel that works (D12). Now live.
- He conflates "spec exists" with "built" — answer status questions with the registry legend's words.
- Missed student-loan deadline June 2026 (~$600) — trigger for 017.
- Disability (SAID/CDB/DTC) is the income track; job search parked (019). Recovery expert pack strictly opt-in; Kitty does not raise it.
- "Magic kitty" — cross-project insight is the point (D13, packet 022). Basic-then-magic sequencing was his explicit call.
- fal is retired for imagegen (too expensive) — local-first, D25 packet.
- Kitty's house: the broken-screen MacBook Air, headless, on ethernet.

## Blocked on Jacob

- Register his 2–3 real projects (`./kitty project add`) and start judging real Bs (closes 016).
- 025 installs half (Draw Things API server, model downloads) before packet builds. **Preflight:** his live imagen checkout is under `~/Projects/`, NOT this repo's `mcp/imagen/` copy.

## Next actions

1. **Build packet 025 (imagegen v2)** — local-first, Draw Things A1111-compatible API, fal retired. Spec at `docs/packets/025-imagegen-pipeline-v2.md`.
2. **Build packet 022 (magic kitty)** — cross-project insight synthesis (D13). Comes after 025.
3. Clean up stale worktrees: `/tmp/kitty-fix`.
4. Wire `MemoryWeave` into `unified_context`/`context_assembler` call paths (small packet).
