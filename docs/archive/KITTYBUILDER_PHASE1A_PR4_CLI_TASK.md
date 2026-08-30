# KittyBuilder Phase 1A — PR 4 CLI Integration Task

## Goal

Complete the approved Phase 1A PR 4 by wiring the durable local queue into the existing `./kitty builder queue ...` CLI namespace. PRs 1–3 are already on `main`: schema/store, state transitions, and claim/fencing/release/expiry are implemented and tested.

This is a focused CLI integration PR. It is not a runner, daemon, autonomous loop, worktree manager, GitHub adapter, or UI.

## Read First

- `AGENTS.md`
- `.claude/HANDOFF.md`
- `.claude/STATE.md`
- `docs/KITTYBUILDER_ORCHESTRATOR_PHASE1A.md`, especially Sections 4.5, 4.6, and 7
- `gateway/builder_cli.py`
- `gateway/builder_queue.py`
- `tests/test_builder_cli.py`
- `tests/test_builder_queue.py`

## Required Commands

Add the `queue` subcommand group under `./kitty builder`:

- `queue add "title" --description "..." --acceptance '["criterion"]' --priority <int> --allowed-paths '["path"]'`
- `queue edit <id>` for queued-only editable fields: title, description, priority, acceptance criteria, and allowed paths
- `queue list [--state <state>] [--include-archived] [--json]`
- `queue show <id> [--json]`
- `queue claim <id> --worker <name> [--lease-seconds <int>] [--json]`
- `queue claim-next --worker <name> [--lease-seconds <int>] [--json]`
- `queue release <id> --worker <name> --lease-token <token> --claim-version <int> [--json]`
- `queue operator-release <id> --reason "..." [--json]`
- `queue transition <id> <state> --lease-token <token> --claim-version <int> [--payload-json '{...}'] [--json]`
- `queue events <id> [--json]`
- `queue status [--json]`
- `queue archive --state <done|failed|cancelled> --older-than <days> [--json]`

Use the existing queue library for state, claim, fencing, release, and recovery behavior. Add only narrow library helpers that the CLI genuinely needs and that are currently missing, such as queued-only edit, event listing, status counts, and soft archive. Do not duplicate queue mutation logic inside argparse handlers.

## Output and Error Contract

- Commands with `--json` print exactly one valid JSON value to stdout and no decorative text.
- Human output is compact and useful; never print full lease tokens unless the command is the claim result or explicit JSON output where the caller needs the token.
- Parse JSON arguments strictly. Acceptance criteria and allowed paths must be arrays of strings. Transition payload must be a JSON object.
- Known queue and validation errors go to stderr with a clear cause and return nonzero; do not emit tracebacks for ordinary operator mistakes.
- `claim-next` with no eligible task must have a deterministic nonzero result and clear message.
- Initialize the queue database safely before command dispatch.
- Preserve the existing `brief`, `contract validate`, and intentionally disabled `run`, `loop`, `repl`, and `delegate` behavior.

## Allowed Files

- `gateway/builder_cli.py`
- `gateway/builder_queue.py` only for narrow missing Phase 1A library helpers
- `tests/test_builder_cli.py`
- `tests/test_builder_queue.py` only when needed to cover new queue helpers
- `.claude/STATE.md`
- `.claude/HANDOFF.md` only if work remains incomplete

## Forbidden Scope

Do not modify:

- `gateway/builder.py`
- `gateway/task_runner.py`
- generic `/tasks` routes or `TASK_DB`
- database schema or migrations unless an existing Phase 1A field is genuinely unusable; stop and report instead of improvising
- HTTP API, daemon, worker spawning, worktree creation, GitHub push/PR automation, UI, auto-merge, provider billing, secrets, or env files
- unrelated formatting or refactors

## Verification

At minimum run:

```bash
python3.12 -m pytest tests/test_builder_cli.py tests/test_builder_queue.py tests/test_builder_contract.py -q --tb=short
python3.12 -m mypy gateway/builder_cli.py gateway/builder_queue.py
python3.12 -m ruff check gateway/builder_cli.py gateway/builder_queue.py tests/test_builder_cli.py tests/test_builder_queue.py
```

Also run focused manual smoke commands against a temporary database or patched `BUILDER_QUEUE_DB` so the real local queue is not polluted. Verify JSON output parses successfully.

## Acceptance Criteria

1. Every required queue command exists and dispatches to tested behavior.
2. JSON output is machine-readable and stable enough for Phase 1B brief generation.
3. Worker mutations remain fenced by lease token and claim version.
4. Edit is rejected unless the task is queued.
5. Archive is soft-only, terminal-state-only, age-filtered, and preserves events.
6. Existing Builder commands and tests remain unchanged in behavior.
7. No forbidden files or deferred-phase features are touched.
8. The implementation is committed locally with a focused Conventional Commit.
9. `.claude/STATE.md` contains the branch, commit, exact tests/results, blockers, and next action.
10. Stop without pushing or merging.

## Final Report

Return:

- branch and commit SHA
- changed files
- exact tests and results
- manual smoke verification
- scope confirmation
- reviewer decision if available
- remaining blockers
- the exact next command for opening the PR, but do not run it
