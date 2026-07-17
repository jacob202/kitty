# Kitty Authority Map

This file routes a clean agent to the owner of each kind of truth. It does not
repeat that truth. If two files disagree, use the authority named here and
report the contradiction rather than blending the claims.

## Authority table

| Concern ID | Authority | Owns | Does not own |
|---|---|---|---|
| `product_purpose` | `docs/NORTH_STAR.md` | Why Kitty exists and the life-first outcome | Current implementation or queue state |
| `engineering_doctrine` | `AGENTS.md` | Safety, verification, change, Git, and agent operating rules | Product architecture or live status |
| `architecture` | `docs/ARCHITECTURE.md` | Current runnable system shape and component boundaries | Durable decision history or release status |
| `decisions` | `docs/DECISIONS.md` | Index of accepted ADRs and supersession | Live status or implementation plans |
| `live_status` | `docs/PROJECT_STATUS.md` | Shipped capabilities, verified baseline, known limitations | Session progress or historical narrative |
| `active_mission` | `docs/ACTIVE_MISSION.md` | The one approved mission, scope, authorization, and acceptance contract | Builder task/run state |
| `session_checkpoint` | `.claude/STATE.md` | Current branch checkpoint, blockers, and exact next action | Historical checkpoints or product purpose |
| `continuation` | `.claude/HANDOFF.md` | Current resumable handoff only when its metadata says `valid` | Append-only history |
| `builder_state` | `data/kittybuilder/builder_queue.db` | Initiatives, packets, tasks, attempts, leases, runs, evidence, and publication state | Product intent or personal data |
| `builder_interfaces` | `docs/KITTYBUILDER_QUICKSTART.md` | Supported operator commands and execution safety rails | Live queue contents |
| `historical_records` | `Git history` | Prior checkpoints, changes, and superseded claims | Current truth until re-verified |
| `historical_docs` | `docs/archive/README.md` | Archived narrative and retired operating material | Current instructions |

Builder state must be read through supported Python/CLI projections. Do not
interpret SQLite tables from prose and do not introduce a second Builder state
machine. Runtime files under `data/` are local and are never committed.

## Conflict rules

1. Live Git, the current worktree, and supported runtime probes beat prose.
2. An accepted ADR beats an older architecture claim in a non-authoritative doc.
3. `docs/PROJECT_STATUS.md` may summarize shipped work but cannot redefine an ADR.
4. `.claude/STATE.md` and `.claude/HANDOFF.md` are invalid when their recorded
   Git identity, mission, path, or invalidation conditions no longer match.
5. Missing or unverifiable facts are `unknown`; they are never filled from an
   old handoff or a plausible guess.

## Context receipts

`./kitty context --agent` is a derived receipt, not another authority. It reads
the owners above, records evidence and unknowns, and makes contradictions
visible. Running it must not fetch, mutate Builder state, or extend the
freshness of a stale checkpoint.
