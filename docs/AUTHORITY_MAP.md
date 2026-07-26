# Kitty Authority Map

This file routes a clean agent to the owner of each kind of truth. It does not
repeat that truth. If two files disagree, use the authority named here and
report the contradiction rather than blending the claims.

## Authority table

| Concern ID | Authority | Owns | Does not own |
|---|---|---|---|
| `product_purpose` | `docs/NORTH_STAR.md` | Why Kitty exists and the life-first outcome | Current implementation or queue state |
| `engineering_doctrine` | `AGENTS.md` | Safety, verification, change, Git, and agent operating rules | Product architecture or live status |
| `execution_frame` | `docs/ALIGNMENT_MAP.md` | Kitty/KittyBuilder layering, authority order, delivery phases, non-goals, and required architecture analysis | Live status or specific packet contents |
| `free_execution_contract` | `docs/FREE_MODEL_PACKET_STANDARD.md` | What a packet must be for unattended free execution and deterministic acceptance | Packet priority or live readiness |
| `architecture` | `docs/ARCHITECTURE.md` | Current runnable system shape and component boundaries | Durable decision history or roadmap priority |
| `decisions` | `docs/DECISIONS.md` and `docs/adr/` | Accepted decisions, amendments, and supersession | Live status or implementation sequencing |
| `roadmap` | `docs/ROADMAP.md` | The one active forward-looking sequence and phase exit criteria | Live Builder state or historical planning narrative |
| `planning_inputs` | Existing files under `docs/plans/`, `docs/planning/`, `docs/packets/`, research, audits, and initiative manifests | Preserved ideas, evidence, candidate work, and executable contracts when explicitly approved | Roadmap authority merely by existing |
| `live_status` | `docs/PROJECT_STATUS.md` | Verified shipped capabilities and known limitations at its stated SHA | Current priority or unverified present state |
| `active_mission` | `docs/ACTIVE_MISSION.md` | The one approved current mission, authority, and acceptance contract | Builder task/run truth |
| `session_checkpoint` | `.claude/STATE.md` | Current branch checkpoint, blockers, and exact next action only while its identity and invalidation conditions remain valid | Historical checkpoints or product purpose |
| `continuation` | `.claude/HANDOFF.md` | Current resumable handoff only when its metadata says `valid` | Append-only history or authority after invalidation |
| `builder_state` | `data/kittybuilder/builder_queue.db` through supported CLI/API projections | Initiatives, packets, tasks, attempts, leases, runs, evidence, and publication state | Product intent or personal data |
| `builder_interfaces` | `docs/KITTYBUILDER_QUICKSTART.md` | Supported operator commands and execution safety rails | Live queue contents |
| `historical_records` | Git history | Prior checkpoints, changes, and superseded claims | Current truth until re-verified |
| `historical_docs` | `docs/archive/README.md` | Archived narrative and retired operating material | Current instructions |

Builder state must be read through supported Python/CLI projections. Do not
interpret SQLite tables from prose and do not introduce a second Builder state
machine. Runtime files under `data/` are local and are never committed.

## Conflict rules

1. Live Git, the current worktree, GitHub, and supported runtime probes beat
   prose.
2. An accepted ADR beats an older architecture or plan claim.
3. `docs/ROADMAP.md` is the only active planning sequence. Older plans are
   inputs until explicitly absorbed, rejected, or archived.
4. `docs/PROJECT_STATUS.md` may summarize shipped work but cannot redefine an
   ADR, roadmap, Mission, or live runtime fact.
5. `.claude/STATE.md` and `.claude/HANDOFF.md` are invalid when their recorded
   Git identity, mission, path, or invalidation conditions no longer match.
6. Missing or unverifiable facts are `unknown`; they are never filled from an
   old handoff, report, or plausible guess.

## Context receipts

`./kitty context --agent` is a derived receipt, not another authority. It reads
the owners above, records evidence and unknowns, and makes contradictions
visible. Running it must not fetch, mutate Builder state, or extend the
freshness of a stale checkpoint.
