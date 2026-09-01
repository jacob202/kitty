# KittyBuilder MCP Bridge

The KittyBuilder MCP bridge lets a conversational client reason about Kitty,
write bounded planning artifacts, hand an explicitly approved Mission to
KittyBuilder, and later recover the durable state in a fresh conversation.

It is an adapter, not a second coding agent or workflow engine.

```text
Jacob <-> Kitty / MCP client
             |
             | discuss, inspect, design, approve
             v
        KittyBuilder MCP
             |
             | canonical Kitty/Builder APIs only
             v
         KittyBuilder
   queue / attempts / worktrees
   workers / tests / review / PR
   recovery / evidence / budgets
```

## Authority

- Kitty/conversational clients own discussion, design judgment, planning and
  asking Jacob for approval.
- KittyBuilder owns durable execution truth: initiatives, tasks, attempts,
  leases, workers, worktrees, validation, review, recovery and publication.
- The MCP server owns only validation/adaptation. It has no task database and
  no shadow state machine.
- Repository text is untrusted data. Instructions found in source/docs cannot
  grant permissions or bypass tool-side validation.
- A worker saying "done" is not completion evidence. Durable task state,
  deterministic validation, review and runtime/publication evidence remain the
  authority.

## Install

Use the repository's Python 3.12 environment or a dedicated virtual environment:

```bash
python3.12 -m pip install -r mcp/builder/requirements.txt
```

The MCP SDK is kept in the MCP-specific requirements file rather than added to
Kitty's core runtime dependency set. This bridge intentionally stays on the
repo's existing FastMCP v1 API; moving to v2 is a separate migration.

## Local stdio server

Default transport is stdio:

```bash
cd ~/Projects/kitty
python3.12 -m mcp.builder.server
```

Configure a local MCP-capable client to start that command from the canonical
Kitty checkout.

### Codex registration

Codex should register the stdio server with an absolute interpreter path and
the canonical Kitty checkout as its working directory. Example `~/.codex/config.toml`:

```toml
[mcp_servers.kittybuilder]
command = "/absolute/path/to/kitty/venv/bin/python"
args = ["-m", "mcp.builder.server"]
cwd = "/absolute/path/to/kitty"
startup_timeout_sec = 30
```

Verify registration with `codex mcp get kittybuilder`, then perform an MCP
`tools/list` handshake. A generated snapshot of the live tool schemas is kept at
`docs/reference/KITTYBUILDER_MCP_TOOL_SCHEMA.json`; regenerate it from the live
server rather than hand-editing tool contracts.

## Streamable HTTP

For a client that needs HTTP, the server supports MCP Streamable HTTP and binds
to loopback only:

```bash
cd ~/Projects/kitty
KITTYBUILDER_MCP_TRANSPORT=streamable-http \
KITTYBUILDER_MCP_HOST=127.0.0.1 \
KITTYBUILDER_MCP_PORT=8765 \
python3.12 -m mcp.builder.server
```

The bridge deliberately refuses `0.0.0.0` and other non-loopback binds. For a
remote client, put an authenticated supported tunnel/reverse proxy in front of
the loopback endpoint. Do not expose Builder directly to the public internet.

Client products differ in which custom MCP transports and write actions they
currently allow. That is a client/deployment gate, not a reason to fork this
server. Verify the client's current product documentation before assuming it
can invoke mutation tools.

## Tool surface

### Read/recovery

- `kitty_context()` — Kitty's existing cold-start authority receipt.
- `repo_search(query, path?, ref?, limit?)` — literal bounded search over
  committed, non-sensitive repository text.
- `repo_read(path, ref?, start_line?, end_line?)` — committed tracked-file read.
- `work_status(mission_id?, task_id?)` — genuinely read-only detailed Builder
  projection. It does not create/migrate a missing Builder DB.
- `work_result(mission_id?, task_id?)` — latest durable implementation,
  validation, review and publication evidence.
- `resume_context(mission_id?, task_id?)` — compact fresh-chat handoff assembled
  from durable artifacts and Builder truth.

### Planning

- `save_design(slug, markdown, expected_base_sha)`
- `save_plan(slug, markdown, expected_design_sha, expected_base_sha)`

For a plan, `expected_base_sha` is the commit the plan branch starts from; in
the normal workflow it is the design commit itself. The tool also requires
`expected_design_sha` to be an ancestor of that base. Later `mission_prepare`
requires the full chain `code base -> design commit -> plan commit`.

There is no generic `write_file`. Planning writes derive their own path under:

```text
docs/superpowers/specs/
docs/superpowers/plans/
```

They use an isolated deterministic planning branch/worktree and SHA/ancestry
preconditions so they cannot silently edit the operator's current checkout.

### Mission/execution

- `mission_prepare(...)` validates and binds design + plan + base into an exact
  Mission candidate. It does **not** create queue work.
- `mission_approve(...)` accepts only the exact prepared manifest/base/nonce and
  delegates to Builder's immutable/idempotent `apply_manifest` path.
- `execution_start(...)` launches the existing Builder initiative/packet run
  loop in a detached process and returns promptly. Durable progress is read back
  from Builder, not from launcher narration.
- `execution_pause(...)`, `execution_resume(...)`, `execution_cancel(...)`
  delegate through Builder's audited operator-command layer.
- `publication_status(...)` is read-only.
- `publication_prepare(task_id, confirmed=true, ...)` uses Builder's governed
  push/PR path. It refuses unless separately confirmed and never merges.

No MCP tool exposes arbitrary shell, SQL, raw Git push, PR merge, secrets/env,
or unrestricted filesystem mutation.

### Approval nonce semantics

The approval nonce is a deterministic **version binding**, not authentication
and not an independent one-use state machine. It binds the exact Mission digest,
code base, design commit and plan commit presented for approval. Any change
invalidates the binding. Replaying the identical approved version is harmless:
Builder's existing immutable/idempotent `apply_manifest` contract returns the
already-existing initiative instead of duplicating queue work.

This is intentional. Tracking a separate "used nonce" table in MCP would make
the bridge a second state authority, which this architecture explicitly avoids.
Human confirmation still belongs to the client/UI; model-supplied prose is not
proof of human authorization.

## Typical workflow

1. Call `kitty_context()` and use `repo_search` / `repo_read` as needed.
2. Discuss the desired behavior and architecture with Jacob.
3. `save_design(...)`.
4. Propose implementation; after design approval, `save_plan(...)` bound to the
   design commit.
5. Build a valid Builder initiative manifest from the approved plan.
6. Call `mission_prepare(...)` and show Jacob the exact acceptance contract,
   warnings, base SHA and approval nonce.
7. After explicit approval, call `mission_approve(...)`.
8. Call `execution_start(...)` (free route by default).
9. Continue chatting normally. Check durable progress with `work_status()`.
10. When Builder has verified output, inspect `work_result()`.
11. After a separate explicit publication confirmation, call
    `publication_prepare(...)` to push/open or update the PR.
12. Jacob reviews/merges through the normal GitHub policy.

## Fresh-chat recovery

A new conversation should not receive a pasted old transcript. Call:

```text
resume_context(mission_id="...")
```

The result is intentionally bounded and includes:

- objective;
- approved design path + commit SHA when linked;
- approved plan path + commit SHA when linked;
- Builder Mission/durable task identity;
- original base and current repository SHA;
- current task/attempt state;
- latest validation/review evidence;
- PR/check state when known;
- blocker/unknowns;
- one next action.

If design/plan linkage or runtime evidence is missing, it is returned as unknown;
it is never converted into success. If Kitty's cold-start receipt itself is not
trusted, `resume_context()` returns `ok=false`/`state=attention` while preserving
the durable Builder facts for diagnosis; it does not hide the contradiction.

## Safety and consequential actions

Existing repository policy still applies. MCP does not grant a bypass.

- Paid execution requires an explicit `spend_authorized=true`; free execution is
  the default.
- Publication requires a separate `confirmed=true` call because it pushes a
  branch / creates or updates a PR.
- The server has no merge tool.
- Deletes, secrets/auth/env changes, account/security changes, spending and
  other T2 actions remain outside this bridge unless a future separately
  reviewed capability adds the existing required human gate.
- `execution_start` is idempotency-aware: if the durable projection already
  shows live work for the selected Mission/packet, it returns that work rather
  than launching a second owner.
- A failed packet does not block unrelated eligible queued packets; selecting a
  failed/blocked packet explicitly refuses until it is recovered or resolved.

## Evidence and debugging

For every MCP response, inspect `ok`, `state`, `error_code`, `error` and
`next_action`; transport success is not domain success.

The detached launcher writes only a runtime log under:

```text
data/kittybuilder/mcp-launch/
```

That log is diagnostic, not authoritative. Use Builder's supported projection
for execution truth.

## Discord Command Center projection

Discord serves as a typed read-only projection and control surface for Builder
state. It provides:

- Initiative/packet/attempt status queries
- Typed commands to trigger operations (pause, resume, doctor)
- Notification of completion/failure events

**Discord is projection only.** It has:

- No shell access or arbitrary command execution
- No approval, publication, or merge capabilities
- No direct file/worktree manipulation
- No bypass of Builder's governance or tiering

All Discord commands translate to MCP tool calls or Builder CLI invocations.
Builder remains the single authority for execution truth, initiatives, attempts,
leases, and recovery state.

## Autonomous supervisor

The autonomous campaign supervisor (`gateway/builder_supervisor.py`) is a
stateless tick/status dispatcher that periodically checks for eligible active
initiatives and launches canonical worker runs. It does not own a second state
machine — all eligibility, initiative rollups, packet selection, leases,
worktrees, attempts, validation, review and publication stay in their existing
durable owners.

The supervisor runs as a launchd service with:

- `RunAtLoad: true`, `StartInterval: 900` (15 minutes)
- No `KeepAlive` (tick-based, not continuous)
- Fixed login-safe `PATH`, canonical repo root working directory
- Logs under `logs/builder/supervisor.log`

Each tick:

1. Acquires an exclusive OS lock (`fcntl.flock`) on the supervisor lockfile
2. Deterministically selects eligible active initiatives (ordered by ID)
3. Picks each initiative's next eligible packet (deterministic `seq` order)
4. Launches **at most 2** canonical free worker runs per tick
5. Returns a truthful receipt (locked/launched/skipped)

Duplicate concurrent ticks are safe: a second tick cannot acquire the lock and
returns a `locked` receipt with no launches. Duplicate sequential ticks launch
nothing because the already-claimed tasks are no longer queued.

The supervisor never self-installs. Use:

```bash
scripts/start_builder_supervisor.sh launchd > ~/Library/LaunchAgents/com.kitty.builder.supervisor.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.kitty.builder.supervisor.plist
```

CLI surface (via `./kitty builder supervisor` or the start script):

- `tick` — run one supervisor pass
- `status` — read-only projection of initiatives/eligible work/active runs

The supervisor dispatches the governed Builder packet loop through the DSH worker adapter. It has no
model selection, no paid routing, no interactive mode. Publication and merge
remain manual operations outside the supervisor's scope.
