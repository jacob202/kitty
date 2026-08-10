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
Kitty's core runtime dependency set.

## Local stdio server

Default transport is stdio:

```bash
cd ~/Projects/kitty
python3.12 -m mcp.builder.server
```

Configure a local MCP-capable client to start that command from the canonical
Kitty checkout.

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
  delegate to canonical Builder state transitions.
- `publication_status(...)` is read-only.
- `publication_prepare(task_id, confirmed=true, ...)` uses Builder's governed
  push/PR path. It refuses unless separately confirmed and never merges.

No MCP tool exposes arbitrary shell, SQL, raw Git push, PR merge, secrets/env,
or unrestricted filesystem mutation.

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
it is never converted into success.

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

## Evidence and debugging

For every MCP response, inspect `ok`, `state`, `error_code`, `error` and
`next_action`; transport success is not domain success.

The detached launcher writes only a runtime log under:

```text
data/kittybuilder/mcp-launch/
```

That log is diagnostic, not authoritative. Use Builder's supported projection
for execution truth.
