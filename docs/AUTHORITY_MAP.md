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
| `decisions` | `docs/DECISIONS.md` | Accepted decisions, amendments, supersession, and routing into `docs/adr/` | Live status or implementation sequencing |
| `ratification` | `docs/decisions/ARCHITECTURE_RATIFICATION_2026-08-06.md` | Cross-cutting architectural adjudication of 12 decisions. Records exact authority sources, evidence, and merge conditions. | Numbered ADRs or routine decisions |
| `roadmap` | `docs/ROADMAP.md` | The one active forward-looking sequence and phase exit criteria | Live Builder state or historical planning narrative |
| `roadmap_v2` | `docs/ROADMAP_V2.md` | Ratified V2 target plan (M1–M6 milestones, packet catalog). Accepted architecture, not execution schedule. Does not override `docs/ROADMAP.md` for active priority. | Active execution schedule or current priority |
| `master_program` | `docs/KITTY_MASTER_PROGRAM.md` | Derived synthesis of ROADMAP, ROADMAP_V2, and the extension backlog into a single dependency-ordered program. Not an independent authority. | Active priority or execution sequencing independent of ROADMAP.md |
| `knowledge_graph` | `docs/KNOWLEDGE_GRAPH.md` | The relationship map across ADRs, architecture docs, roadmaps, research, issues, PRs, initiatives, and packets | Implementation or live status |
| `planning_inputs` | `docs/plans/` | Existing plans, planning notes, packets, research, audits, and initiative manifests as preserved ideas, evidence, candidate work, or executable contracts when explicitly approved | Roadmap authority merely by existing |
| `disposition_ledger` | `docs/DISPOSITION_LEDGER.md` | The canonical disposition (ACTIVE, SCHEDULED, BLOCKED, BACKLOG, SUPERSEDED, REJECTED, ARCHIVED) of every retained planning file | Disposition of files not yet inventoried |
| `launcher_contract` | `docs/reference/LAUNCHER_CONTRACT.md` | The single launcher interface across production and development modes; required shared properties | Alternative server entry points or silently bootable paths |
| `prevention_mechanisms` | `docs/reference/PREVENTION_MECHANISMS.md` | Enforceable prevention mechanisms for the repository: red-main freeze, lane limits, freshness, overlap detection, stale-draft policy, independent review, evidence requirements | Implementation details of CI workflows |
| `live_status` | `docs/PROJECT_STATUS.md` | Verified shipped capabilities and known limitations at its stated SHA | Current priority or unverified present state |
| `active_mission` | `docs/ACTIVE_MISSION.md` | The one approved current mission, authority, and acceptance contract | Builder task/run truth |
| `session_checkpoint` | `.claude/STATE.md` | Current branch checkpoint, blockers, and exact next action only while its identity and invalidation conditions remain valid | Historical checkpoints or product purpose |
| `continuation` | `.claude/HANDOFF.md` | Current resumable handoff only when its metadata says `valid` | Append-only history or authority after invalidation |
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
4. `docs/ROADMAP.md` is the active planning sequence. `docs/ROADMAP_V2.md` is a
   ratified target plan (V2 milestone targets, per the Constitution) and does
   not override `docs/ROADMAP.md` for active priority.
   Older plans are inputs until explicitly absorbed, rejected, or archived.
5. `docs/PROJECT_STATUS.md` may summarize shipped work but cannot redefine an
   ADR, roadmap, Mission, or live runtime fact.
6. `.claude/STATE.md` and `.claude/HANDOFF.md` are invalid when their recorded
   Git identity, mission, path, or invalidation conditions no longer match.
7. Missing or unverifiable facts are `unknown`; they are never filled from an
   old handoff, report, or plausible guess.

## Context receipts

`./kitty context --agent` is a derived receipt, not another authority. It reads
the owners above, records evidence and unknowns, and makes contradictions
visible. Running it must not fetch, mutate Builder state, or extend the
freshness of a stale checkpoint.
