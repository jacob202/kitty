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
| `execution_frame` | `docs/ALIGNMENT_MAP.md` | Kitty/KittyBuilder layering, authority order, delivery phases, non-goals, and required architecture analysis | Live status or specific packet contents |
| `free_execution_contract` | `docs/FREE_MODEL_PACKET_STANDARD.md` | What a packet must be for unattended free execution and deterministic acceptance | Packet priority or live readiness |
| `architecture` | `docs/ARCHITECTURE.md` | Current runnable system shape and component boundaries | Durable decision history or roadmap priority |
| `gateway_api` | `docs/reference/GATEWAY_API.md` | Stable Gateway HTTP schema discovery, authentication, native proxy, OpenAI-compatible, bounded tool, and client-integration boundaries; routes readers to generated OpenAPI/source for concrete operations | Domain business rules, live endpoint availability, or a handwritten endpoint inventory independent of generated schema |
| `decisions` | `docs/DECISIONS.md` | Accepted decisions, amendments, supersession, and routing into `docs/adr/` | Live status or implementation sequencing |
| `ratification` | `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` | Cross-cutting architectural adjudication of 12 decisions. Records exact authority sources, evidence, and merge conditions. | Numbered ADRs or routine decisions |
| `roadmap` | `docs/ROADMAP.md` | The one active forward-looking sequence and phase exit criteria (ADR 0020; Ratification Decision 5). | Live Builder state or historical planning narrative |
| `roadmap_v2_target` | `docs/ROADMAP_V2.md` | Historical/superseded V2 target detail retained for traceability. Its Open WebUI-primary sequence is not executable current priority. | Active priority or execution sequencing |
| `master_program` | `docs/KITTY_MASTER_PROGRAM.md` | Derived synthesis of ROADMAP, ROADMAP_V2, and the extension backlog into a single dependency-ordered program. Not an independent authority. | Active priority or execution sequencing independent of ROADMAP.md |
| `knowledge_graph` | `docs/KNOWLEDGE_GRAPH.md` | The relationship map across ADRs, architecture docs, roadmaps, research, issues, PRs, initiatives, and packets | Implementation or live status |
| `planning_inputs` | `docs/plans/` | Existing plans, planning notes, packets, research, audits, and initiative manifests as preserved ideas, evidence, candidate work, or executable contracts when explicitly approved | Roadmap authority merely by existing |
| `disposition_ledger` | `docs/DISPOSITION_LEDGER.md` | The canonical disposition (ACTIVE, SCHEDULED, BLOCKED, BACKLOG, SUPERSEDED, REJECTED, ARCHIVED) of every retained planning file | Disposition of files not yet inventoried |
| `launcher_contract` | `docs/reference/LAUNCHER_CONTRACT.md` | The single launcher interface across production and development modes; required shared properties | Alternative server entry points or silently bootable paths |
| `prevention_mechanisms` | `docs/reference/PREVENTION_MECHANISMS.md` | Enforceable prevention mechanisms for the repository: red-main freeze, lane limits, freshness, overlap detection, stale-draft policy, independent review, evidence requirements | Implementation details of CI workflows |
| `live_status` | `docs/PROJECT_STATUS.md` | Verified shipped capabilities and known limitations at its stated SHA | Current priority or unverified present state |
| `active_mission` | `docs/ACTIVE_MISSION.md` | The canonical mission record and acceptance contract. Its status may be terminal; a terminal record means no running mission exists until Jacob explicitly approves a replacement. | Builder task/run truth |
| `interactive_continuity` | `workspace_global` via the Global Agent Room CLI/MCP | Primary mutable cross-agent and cross-session handoffs, questions, reviews, results, and status. Read the relevant inbox/thread and acknowledge received messages. | Product architecture, roadmap authority, Git publication truth, or Builder execution state |
| `session_checkpoint` | `.claude/STATE.md` | Legacy compatibility checkpoint used only through the validated fallback path when current GAR continuity is unavailable or no durable GAR locator exists and the receipt requires it | Current interactive continuity when GAR is available, historical checkpoints, or product purpose |
| `continuation` | `.claude/HANDOFF.md` | Legacy compatibility handoff used only through the validated fallback path when its metadata remains valid | Current GAR handoff/thread, append-only history, or authority after invalidation |
| `builder_state` | `data/kittybuilder/builder_queue.db` | Initiatives, packets, tasks, attempts, leases, runs, evidence, and publication state, read only through supported CLI/API projections | Product intent or personal data |
| `builder_interfaces` | `docs/KITTYBUILDER_QUICKSTART.md` | Supported operator commands and execution safety rails | Live queue contents |
| `historical_records` | `Git history` | Prior checkpoints, changes, and superseded claims | Current truth until re-verified |
| `historical_docs` | `docs/archive/README.md` | Archived narrative and retired operating material | Current instructions |

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
