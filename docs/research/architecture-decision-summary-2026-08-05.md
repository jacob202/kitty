# Architecture Decision Summary — 2026-08-05

Harvested from 2026-08 investigations: repository simplification audit, architecture
migration analysis, Builder core runtime audit, Open WebUI onboarding, architecture
honesty audit, feature reality audit, foundation replacement study, and architecture
correction.

## ADR Dependency Graph

```
                    ┌──────────────┐
                    │  0002 local- │
                    │  first user  │
                    └──────┬───────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
     ┌──────────┐   ┌──────────┐   ┌──────────┐
     │0003 gate-│   │0015 res- │   │0016 life-│
     │way=prod  │   │ume loop  │   │first     │
     └────┬─────┘   └────┬─────┘   └──────────┘
          │              │
     ┌────▼─────┐   ┌────▼─────┐
     │0017 Kit. │   │0027 Open │
     │→Builder  │   │WebUI(8/2)│
     └────┬─────┘   └────┬─────┘
          │              │
     ┌────▼─────┐   ┌────▼─────┐
     │0021 pro- │   │0033 Open │
     │active B. │   │WebUI bou.│
     └────┬─────┘   └──────────┘
          │
     ┌────▼─────┐
     │0028 com- │
     │modity OS │
     └────┬─────┘
          │
     ┌────┼────┬──────────┬──────────┐
     ▼    ▼    ▼          ▼          ▼
  0030   0031 0032       0034       0036
  simp-  mig-  evid-     memory     builder
  lifi-  ration ence      policy     infra
  cation defer           vs store   preserve

  0029 capability manifest (independent, depends on 0003)
  0035 browser-verified (depends on 0032)
```

## Decision Timeline

| Date | ADRs | Theme |
|---|---|---|
| 2026-07-02 | 0001–0009 | Foundation: SQLite, local-first, gateway, memory |
| 2026-07-11 | 0014–0016 | BluePrint: resume loop, life-first |
| 2026-07-17 | 0017 | Kitty → Builder boundary |
| 2026-07-24–26 | 0019–0023 | Audit harvest, roadmap, proactive Builder |
| 2026-08-01 | 0024–0026 | Builder operator app, session learning, KB |
| 2026-08-02 | 0027 | Open WebUI shell |
| 2026-08-05 | 0028–0036 | **9 decisions from investigations** |

## Open Decisions That Still Require Investigation

| Decision | Status | Required |
|---|---|---|
| Single vector store choice | Open | Benchmark SQLite-vec vs ChromaDB at Kitty's scale (<1M vectors, single user) |
| mem0 removal path | Open | Audit mem0 consumers; design direct embedding management; test context quality before/after |
| Open Brain actual API fitness | Open | Project maturity unknown; requires stable release and API documentation |
| Ringer worker lifecycle compatibility | Open | Evaluate worktree isolation, Git integration, heartbeat contracts |
| Conversational Image Agent | Authorized, not started | Issue #336. Blocked on Gate 0.8. Needs RunPod credentials |
| Gate 0 prevention mechanisms | Defined, not enforced | Branch protection on main requiring 6 CI checks — needs Jacob's GitHub admin |
| kitty-chat Console repositioning | Direction set, not planned | How many of 60+ components stay as Console vs move to Open WebUI |
| Suspicious wired modules audit | Not started | `prefetcher.py`, `inbox_watcher.py`, `insight_loop.py`, `life_awareness.py`, `telegram_bot.py`, `antigravity_tools.py`, `web_tracker.py`, `self_review.py` — value unknown |

## Immutable Decisions

Do not reopen without extraordinary evidence:

1. **ADR 0003:** Gateway is the product. Intelligence layer stays in Gateway.
2. **ADR 0017:** Kitty → Mission → KittyBuilder boundary. No joining Builder tables into other state machines.
3. **ADR 0015:** The resume loop is the product. Everything serves it.
4. **ADR 0027/0033:** Open WebUI as replaceable shell. Shell state ≠ Kitty state.
5. **ADR 0028:** Commodity software precedence. Do not rebuild chat UI, vector DBs, RSS readers, browser automation, workflow engines.
6. **ADR 0032:** No fabricated success. Never return `null`/`[]`/`completed` to hide failure.
7. **ADR 0035:** Browser-verified evidence required. Code inspection ≠ product proof.

## Documents to Update

| Document | What's Stale | Status |
|---|---|---|
| `docs/DECISIONS.md` | Missing ADRs 0027–0036 | Updated (2026-08-05) |
| `docs/adr/README.md` | Missing ADRs 0027–0036 | Updated (2026-08-05) |
| `docs/ARCHITECTURE.md` | References deleted `openwebui_filters/`, outdated module lists | Needs update |
| `docs/reference/CODEBASE_MAP.md` | Stale module counts, Builder module count | Needs update after Builder refactor |
| `docs/BLUEPRINT.md` | Telegram "off" but still wired in `app.py` | Needs resolution |
| `docs/FEATURE_REALITY_2026-07-28.md` | Feature reality table out of date | Needs refresh |
| `docs/AUTHORITY_MAP.md` | May need new ADR authority references | Review |
| `docs/ROADMAP.md` | ADR 0030 (simplification) and 0036 (Builder refactor) not in outcomes | Add outcomes |
