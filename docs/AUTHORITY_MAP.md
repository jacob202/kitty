# Kitty Authority Map

This file routes a clean agent to the owner of each kind of truth. It does not
repeat that truth. If two files disagree, use the authority named here and
report the contradiction rather than blending the claims.

## Authority table

| Concern ID | Authority | Owns | Does not own |
|---|---|---|---|
| `constitution` | `docs/CONSTITUTION.md` | Highest architectural authority. All ADRs, roadmaps, and plans must be consistent with it. Amended only by explicit Constitution-amendment ADRs per Article VII.5. | Implementation details, live status, or specific packet contents |
| `product_purpose` | `docs/NORTH_STAR.md` | Why Kitty exists and the life-first outcome | Current implementation or queue state |
| `engineering_doctrine` | `AGENTS.md` | Safety, verification, change, Git, and agent operating rules | Product architecture or live status |
| `execution_frame` | `docs/ALIGNMENT_MAP.md` | Kitty/KittyBuilder layering, boundaries, non-goals, and the required architecture-proposal analysis checklist | Authority order, delivery sequencing, live status, or specific packet contents — Constitution, ratification, and ROADMAP own those |
| `free_execution_contract` | `docs/FREE_MODEL_PACKET_STANDARD.md` | What a packet must be for unattended free execution and deterministic acceptance | Packet priority or live readiness |
| `architecture` | `docs/ARCHITECTURE.md` | Current runnable system shape and component boundaries | Durable decision history or roadmap priority |
| `gateway_api` | `docs/reference/GATEWAY_API.md` | Stable Gateway HTTP schema discovery, authentication, native proxy, OpenAI-compatible, bounded tool, and client-integration boundaries; routes readers to generated OpenAPI/source for concrete operations | Domain business rules, live endpoint availability, or a handwritten endpoint inventory independent of generated schema |
| `decisions` | `docs/DECISIONS.md` | Accepted decisions, amendments, supersession, and routing into `docs/adr/` | Live status or implementation sequencing |
| `ratification` | `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` | Cross-cutting architectural adjudication of 12 decisions. Records exact authority sources, evidence, and merge conditions. | Numbered ADRs or routine decisions |
| `roadmap` | `docs/ROADMAP.md` | The one active forward-looking sequence and phase exit criteria (ADR 0020; Ratification Decision 5). | Live Builder state or historical planning narrative |
| `roadmap_v2_target` | `docs/ROADMAP_V2.md` | Historical/superseded V2 target detail retained for traceability. Its Open WebUI-primary sequence is not executable current priority. | Active priority or execution sequencing |
| `planning_inputs` | `docs/plans/`, `docs/packets/`, `docs/initiatives/` | Preserved ideas, evidence, candidate work, and executable contracts after explicit current approval | Priority, activation, or ownership merely by existing |
| `launcher_contract` | `docs/reference/LAUNCHER_CONTRACT.md` | The single launcher interface across production and development modes; required shared properties | Alternative server entry points or silently bootable paths |
| `prevention_mechanisms` | `docs/reference/PREVENTION_MECHANISMS.md` | Enforceable prevention mechanisms for the repository: red-main freeze, lane limits, freshness, overlap detection, stale-draft policy, independent review, evidence requirements | Implementation details of CI workflows |
| `live_status` | `docs/PROJECT_STATUS.md` | Dated shipped-capability and limitation evidence at its stated SHAs; retained under the stable `live_status` concern ID for receipt compatibility | Live runtime state, current priority, or unverified present state |
| `active_mission` | `docs/ACTIVE_MISSION.md` | The canonical mission record and acceptance contract. Its status may be terminal; a terminal record means no running mission exists until Jacob explicitly approves a replacement. | Builder task/run truth |
| `interactive_continuity` | `workspace_global` via the Global Agent Room CLI/MCP | Primary mutable cross-agent and cross-session handoffs, questions, reviews, results, and status. Read the relevant inbox/thread and acknowledge received messages. | Product architecture, roadmap authority, Git publication truth, or Builder execution state |
| `session_checkpoint` | `.claude/STATE.md` | Legacy compatibility checkpoint used only through the validated fallback path when current GAR continuity is unavailable or no durable GAR locator exists and the receipt requires it | Current interactive continuity when GAR is available, historical checkpoints, or product purpose |
| `continuation` | `.claude/HANDOFF.md` | Legacy compatibility handoff used only through the validated fallback path when its metadata remains valid | Current GAR handoff/thread, append-only history, or authority after invalidation |
| `builder_state` | `data/kittybuilder/builder_queue.db` | Initiatives, packets, tasks, attempts, leases, runs, evidence, and publication state, read only through supported CLI/API projections | Product intent or personal data |
| `builder_interfaces` | `docs/KITTYBUILDER_QUICKSTART.md` | Supported operator commands and execution safety rails | Live queue contents |
| `historical_records` | `Git history` | Prior checkpoints, changes, and superseded claims | Current truth until re-verified |
| `historical_docs` | `docs/archive/README.md` | Archived narrative and retired operating material | Current instructions |

## Non-authoritative catalogs and snapshots

These files are useful for archaeology or derived synthesis but do not own current
execution truth:

- `docs/DISPOSITION_LEDGER.md` — compatibility pointer to the frozen 2026-08-08 planning snapshot; not exhaustive after later packet/initiative families.
- `docs/KNOWLEDGE_GRAPH.md` — compatibility pointer to the frozen 2026-08-05 relationship analysis.
- `docs/KITTY_MASTER_PROGRAM.md` — dated derived synthesis; `ROADMAP.md` owns current sequence.
- `docs/audit/GITHUB_OPERATING_PICTURE_2026-08-04.md` — dated GitHub evidence, not current GitHub state.

A candidate plan, packet, or manifest becomes active only through explicit current
approval plus live ownership/coordination evidence. Historical catalog membership
never activates work.

Builder state must be read through supported Python/CLI projections. Do not
interpret SQLite tables from prose and do not introduce a second Builder state
machine. Runtime files under `data/` are local and are never committed.

## Conflict rules

1. Live Git, the current worktree, GitHub, and supported runtime probes beat
   prose.
2. `docs/CONSTITUTION.md` is the highest-level design artifact. All other
   documents that contradict it are wrong.
3. An accepted ADR beats an older architecture or plan claim.
4. `docs/ROADMAP.md` is the active living planning guide. `docs/ROADMAP_V2.md`
   is historical/superseded target detail, not an alternative execution order.
   Older plans are inputs until explicitly absorbed, rejected, or archived.
5. `docs/PROJECT_STATUS.md` may summarize shipped work but cannot redefine an
   ADR, roadmap, Mission, or live runtime fact.
6. `workspace_global` is the primary mutable interactive-continuity source. The
   `.claude/STATE.md` / `.claude/HANDOFF.md` pair is legacy compatibility fallback
   only and is invalid when its recorded Git identity, mission, path, or
   invalidation conditions no longer match.
7. Missing or unverifiable facts are `unknown`; they are never filled from an
   old handoff, report, or plausible guess.

### Product-surface authority resolution (2026-08-23)

The Constitution was explicitly amended to incorporate accepted ADR 0039: the native
`gateway/kitty-chat` frontend is Kitty's canonical user-facing product surface. Open
WebUI remains optional compatibility/reference software subject to ADR 0027/0033's
isolation and replaceability boundaries. The historical Open WebUI-primary M1/M2
sequence in `ROADMAP_V2.md` is therefore not executable current priority.

## Context receipts

`./kitty context --agent` is a derived receipt, not another authority. It reads
the owners above, records evidence and unknowns, and makes contradictions
visible. Running it must not fetch, mutate Builder state, or extend the
freshness of a stale checkpoint.
