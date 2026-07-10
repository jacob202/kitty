# KittyBuilder Queue — Quickstart & Operations

The KittyBuilder queue is the durable, local source of truth for builder
tasks. It is a SQLite database at `data/kittybuilder/builder_queue.db` with a
strict state machine, fenced worker mutations, and an append-only event log.
GitHub issue #127 is only a bridge inbox; GitHub comments never override local
queue state.

All commands live under `./kitty builder queue ...` (or
`python3.12 -m gateway.builder_cli queue ...`). Data-returning commands accept
`--json`.

## Quickstart

```bash
# Add a task with acceptance criteria
./kitty builder queue add "Fix doctor timeout" \
  --description "doctor --json hangs when LiteLLM is down" \
  --acceptance '["doctor exits <5s with LiteLLM down", "tests pass"]' \
  --priority 5

# See what's queued
./kitty builder queue list --state queued
./kitty builder queue status

# Claim it (returns the lease token + claim version the worker must keep)
./kitty builder queue claim kb_mrelm4q5_9803 --worker opencode-1

# Worker starts execution
./kitty builder queue transition kb_mrelm4q5_9803 running \
  --lease-token <token> --claim-version <version>

# Inspect history at any time
./kitty builder queue events kb_mrelm4q5_9803
```

Task IDs look like `kb_<base36_ms>_<hex4>` and sort by creation time.

## Full lifecycle walkthrough (JSON + lease extraction)

Workers should use `--json` and keep the fencing values. Every later mutation
requires both; a stale token or version is rejected and logs nothing.

```bash
# 1. Add and capture the ID
TASK_ID=$(./kitty builder queue add "Small scoped task" \
  --acceptance '["tests pass"]' --json | jq -r '.id')

# 2. Claim and capture the fencing pair
CLAIM=$(./kitty builder queue claim "$TASK_ID" --worker opencode-1 --json)
LEASE=$(echo "$CLAIM" | jq -r '.lease_token')
VERSION=$(echo "$CLAIM" | jq -r '.claim_version')

# 3. Start running
./kitty builder queue transition "$TASK_ID" running \
  --lease-token "$LEASE" --claim-version "$VERSION"

# 4a. Finish: pr_opened → awaiting_review → done
./kitty builder queue transition "$TASK_ID" pr_opened \
  --lease-token "$LEASE" --claim-version "$VERSION" \
  --payload-json '{"pr": 999}'

# 4b. Or hit a wall: block with a reason (resumable with the same lease)
./kitty builder queue transition "$TASK_ID" blocked \
  --lease-token "$LEASE" --claim-version "$VERSION" \
  --payload-json '{"reason": "needs Jacob decision on schema"}'

# 4c. Or hand it back cleanly
./kitty builder queue release "$TASK_ID" --worker opencode-1 \
  --lease-token "$LEASE" --claim-version "$VERSION"
```

State machine (illegal moves are rejected and never logged):

```
queued → claimed → running → pr_opened → awaiting_review → done
running ⇄ blocked;  blocked → queued (operator) | failed | cancelled
queued/claimed/running/awaiting_review/blocked → failed | cancelled
```

Terminal states (`done`, `failed`, `cancelled`) clear the lease so a stale
worker can never mutate a finished task. `running → queued` is never allowed —
a stale running task goes through `blocked` and an operator decision.

## Operator commands

```bash
./kitty builder queue edit <id> --priority 9        # queued tasks only
./kitty builder queue operator-release <id> --reason "worker died"
./kitty builder queue archive --state done --older-than 14
./kitty builder queue show <id> --json
```

`operator-release` needs no lease — it is the human override for returning a
claimed or blocked task to `queued`. `archive` soft-archives terminal tasks by
setting `archived_at`; rows and events are never deleted.

## Kill switch

```bash
export KITTY_BUILDER_QUEUE_ENABLED=0
```

All mutating commands refuse before touching the DB; `list`, `show`, `events`,
and `status` keep working so a frozen queue stays inspectable. Unset the
variable (or set to `1`) to re-enable.

## Backups

The queue is authoritative, so back it up before risky work and at least every
couple of days:

```bash
mkdir -p data/kittybuilder/backups
sqlite3 data/kittybuilder/builder_queue.db \
  "VACUUM INTO 'data/kittybuilder/backups/builder_queue_$(date +%Y%m%d).db'"
```

`./kitty builder queue status` warns when the newest backup is missing or
older than 48 hours (and prints the exact command). There is deliberately no
backup daemon.

## Integrity check & crash recovery

```bash
sqlite3 data/kittybuilder/builder_queue.db "PRAGMA integrity_check;"   # → ok
```

The DB runs in WAL mode: a killed process (crash, `kill -9`, power loss)
leaves a `-wal` file that SQLite replays automatically on the next
connection — just run any queue command and verify with `queue list`.

To restore from a backup, stop anything using the queue, then:

```bash
cp data/kittybuilder/backups/builder_queue_<date>.db \
   data/kittybuilder/builder_queue.db
rm -f data/kittybuilder/builder_queue.db-wal data/kittybuilder/builder_queue.db-shm
sqlite3 data/kittybuilder/builder_queue.db "PRAGMA integrity_check;"
```

## Expired lease recovery & worker takeover

Leases default to 30 minutes (no heartbeat until Phase 1C). Recovery rules:

- `claimed` + expired lease → back to `queued` (safe: execution never started)
- `running` + expired lease → `blocked` with reason `stale_heartbeat`
  (never auto-requeued; an operator inspects and decides)

```bash
./kitty builder queue recover          # run the recovery scan
```

Takeover flow when a worker dies or runs out of credits:

```bash
./kitty builder queue recover                          # frees expired leases
./kitty builder queue operator-release <id> --reason "worker crashed"  # if blocked
./kitty builder queue brief <id>                       # new worker's full context
```

The brief includes the previous final report, attached PRs, and recent events,
so the next worker starts from what actually happened instead of a stale chat.

## Worker briefs, final reports, PR metadata (Phase 1B)

```bash
# Complete worker prompt: scope, criteria, branch, validation, fencing, stops
./kitty builder queue brief <id> [--branch feat/custom]

# Worker attaches a structured report (fenced)
./kitty builder queue attach-report <id> --report-json '{"summary": "...", "tests": "5/5"}' \
  --lease-token <token> --claim-version <version>

# Operator post-mortem on a dead task (unfenced, reason logged)
./kitty builder queue attach-report <id> --report-file report.json \
  --operator-reason "worker crashed, notes recovered"

# Advisory PR metadata (never changes task state — that stays fenced)
./kitty builder queue attach-pr <id> --pr 141 --url <url> --head-sha <sha>

# Cancel a queued/blocked task without a lease
./kitty builder queue operator-cancel <id> --reason "superseded"
```

## Known limitations

- No worker spawning, no PR automation, no daemon, no UI. Those are Phases
  1C–2 and gated separately.

## Cutting over from GitHub issue #127

Issue #127 stays the bridge inbox **until the local queue survives one full
dogfooded task lifecycle** (add → claim → work → PR → done, plus one recovery
event). After that:

1. New tasks go into the local queue (`queue add`), not #127 comments.
2. #127 stays open for audit/history and as bridge metadata
   (`bridge_source`/`bridge_external_id` on imported tasks) — comments there
   are advisory only and never mutate local state.
3. PR coordination is unchanged: reports, review, and merge approval happen
   on the PR per `docs/WORKFLOW.md`.

Double-tracking tasks in both places is the failure mode to avoid: after
cutover, if it isn't in the queue, it isn't a task.
