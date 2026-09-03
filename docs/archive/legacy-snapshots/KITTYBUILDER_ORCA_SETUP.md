# KittyBuilder Orca Setup

> **Historical snapshot archived 2026-09-03.** Do not use this file for current Builder routing, approval, or publication rules; use `docs/KITTYBUILDER_QUICKSTART.md`, `docs/FREE_WORKERS.md`, and `AGENTS.md`.

KittyBuilder may use Orca as an outer worktree/worker adapter. The local SQLite
queue is already the durable Builder task authority.

## Current Role Split

- **Orca** creates isolated worktrees, tracks task dispatch, carries worker messages, and exposes decision gates.
- **OpenCode** is the default implementation, planning, packaging, and cheap review lane.
- **Codex** is reserved for high-risk review or blocked escalation.
- **KittyBuilder queue** remains the authoritative task state.
- **GitHub issue #127** is historical bridge/audit metadata only; it is not an execution inbox.

## Setup Hook

Configure the Kitty repo setup hook in Orca to run:

```bash
./scripts/orca_worktree_setup.sh
```

The hook is intentionally read-only. It prints the current branch, dirty status, model routing rules, approval tiers, and the key files an agent should read before working.

## Approval Tiers

| Tier | Approver | Examples |
| --- | --- | --- |
| T0 | Automatic | read-only audits, task cards, formatting, local tests, PR descriptions |
| T1 | Separate model reviewer | normal scoped implementation, local commits, draft PR preparation |
| T2 | Jacob | push, merge, deletes, auth/secrets/env, paid or heavy dependencies, broad scope changes |

The implementer must not approve its own work. A model approval must be from a separate session or agent lane and should return a clear `APPROVE` or `BLOCK`.

## Provider Routing

Builder model routing is owned by [`docs/FREE_WORKERS.md`](../../FREE_WORKERS.md): two
explicit DeepSeek Harness (DSH) lanes — `--free` (zero-spend, OpenRouter free
models only) and `--paid` (governed OpenRouter value route with the compute
governor). Omitting both is not an implicit default. Current routing lives in
the sources, not here, so it does not go stale when providers change:

- Command contract and `--free`/`--paid` dispatch: `gateway/builder_cli.py`
  (`./kitty builder initiative run-packet <initiative> <packet> --free|--paid --watch`).
- DSH worker/reviewer adapters: `scripts/kittybuilder_dsh_worker.sh`,
  `scripts/kittybuilder_dsh_reviewer.sh`, `scripts/kittybuilder_dsh.sh`.
- Paid model/ceiling config: `config/builder_paid_routes.json`; compute
  governor: `gateway/compute_governor.py` + `config/compute_governor.json`.
- OpenCode free-train launcher and adapters: `scripts/opencode_free_train.sh`,
  `scripts/kittybuilder_opencode_worker.sh`,
  `scripts/kittybuilder_opencode_reviewer.sh`; OpenCode defaults in `opencode.jsonc`.

Do not copy model lists into docs — they go stale when providers change. Cap
silent provider retries quickly: one cheap attempt, one stronger attempt, then
block or escalate. Do not loop through providers silently.

## Free-Only Build Train

The repository `opencode.jsonc` defaults to OpenCode free models (e.g.
`opencode/deepseek-v4-flash-free`), disables session sharing (`share: disabled`),
blocks external-directory access, subagent spawning (`task`), and questions,
and denies force-push, `git reset`/`clean`/`restore`, and `rm` even when OpenCode
runs with `--auto`. The launcher (`scripts/opencode_free_train.sh`) itself never
pushes or merges.

Launch one task card from a clean Orca worktree:

```bash
bash scripts/opencode_free_train.sh <task-card.md>
```

The zero-cost fallback ladder is defined in `scripts/opencode_free_train.sh`
itself — read that source for the current list, and see
[`docs/FREE_WORKERS.md`](../../FREE_WORKERS.md) for the authoritative DSH `--free`
routing. Do not copy the model list into docs; it goes stale when providers
change. `OPENCODE_FREE_MODEL` forces one builder model and
`OPENCODE_FREE_REVIEW_MODEL` forces one reviewer model.

A failed model may hand off only if it left both the worktree and `HEAD`
unchanged. Once a builder changes anything, automatic provider fallback stops.
A successful build is reviewed by a different free model in a read-only lane.
Transcripts are written outside the repo under `/tmp` unless
`OPENCODE_FREE_LOG_DIR` is set.

Free endpoints may log prompts or use trial data for improvement. Use them only
for public repository code and task instructions. Never expose `.env` files,
credentials, runtime personal data, private memories, or uncommitted user
content.

Provider credentials remain in OpenCode's user credential store or environment. Never commit API keys. Check configured providers with:

```bash
opencode auth list
opencode models --refresh
```

### Packet adapter contract

The queue runner supplies `KB_BUNDLE_PATH`, `KB_RESULT_PATH`,
`KB_CONTEXT_MANIFEST_PATH`, `KB_TASK_ID`, and `KB_ATTEMPT_ID` to the free worker;
the reviewer also receives `KB_IMPL_RESULT_PATH`, `KB_REVIEW_RESULT_PATH`,
`KB_REVIEW_CONTEXT_PATH`, `KB_REVIEW_SHA`, and `KB_REVIEW_DIFF_SHA256`. The
checked-in adapter scripts copy runner-owned files into the isolated worktree,
verify task/attempt IDs and bundle hashes, and only copy a validated contract
back to the runner path. Reviewer input is bound to the exact worker `HEAD`
and diff digest; the runner rejects any changed worktree after review. OpenCode
prompts must use local staged copies, never an external queue path. A missing
file, mismatched hash, invalid contract, or reviewer worktree mutation is a
hard failure and leaves the attempt evidence available for inspection.

Each adapter family has its own checked-in zero-cost fallback ladder (see the
adapter source and [`docs/FREE_WORKERS.md`](../../FREE_WORKERS.md) for the current
list); the fail-loud handoff rule is shared: a model that fails cleanly (no
result written, worktree and `HEAD` untouched) hands off to the next free
model inside the same attempt, and any partial work stops fallback
immediately. `KITTYBUILDER_MODEL` / `KITTYBUILDER_REVIEW_MODEL` force a single
model; `KITTYBUILDER_MODELS` / `KITTYBUILDER_REVIEW_MODELS` (space-separated)
replace the ladder.

For a bounded launch with durable artifact paths, use the packet loop's watch
surface with the `--free` preset (see `docs/FREE_WORKERS.md`):

```bash
./kitty builder initiative run-packet <initiative-id> <packet-id> --free --watch
```

## GitHub Credential Hygiene

A build that finishes cleanly can still fail at the push/PR step on a stale
HTTPS credential. Two known failure modes and their fixes:

1. **Stale ambient `GITHUB_TOKEN`** overrides `gh` keyring auth. Run every
   GitHub operation as `env -u GITHUB_TOKEN gh ...` /
   `env -u GITHUB_TOKEN git push ...` (see `docs/WORKFLOW.md`).
2. **Stale keychain HTTPS credential** used by plain git. One-time fix on a
   new machine or after re-auth:

   ```bash
   gh auth setup-git
   ```

   This routes git's HTTPS credential prompts through `gh auth git-credential`
   so git always uses the current `gh` login. Verify with
   `git config --get-all credential.helper`.

`scripts/orca_worktree_setup.sh` warns on both conditions at worktree setup so
they surface before a build, not after it.

## Safe Build Train

Use this sequence for low-babysitting work:

1. Create an Orca worktree from `origin/main`.
2. Generate or paste one task card with allowed files, forbidden files, tests, and stop condition.
3. Dispatch OpenCode implementation.
4. Dispatch a separate OpenCode review gate.
5. Escalate to Codex only for high-risk safety review or repeated blocker.
6. Prepare PR text, but do not push or merge without the configured gate.

## Non-Goals

- No autonomous merge.
- No unattended paid-provider spending loop.
- No secrets or env edits from the setup hook.
- No worker spawning from the KittyBuilder queue until the queue CLI and runner gates exist.
