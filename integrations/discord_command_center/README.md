# Discord Command Center — Phase 0

Phase 0 proves one path only:

`/vibe request → defer → private thread → disposable git worktree → advisory-readonly Codex → macOS write sandbox → post-run diff audit`

This integration is a Discord control surface, not a second KittyBuilder. It must not own Builder model routing, worker retries, publication, review, durable queues, or execution-cost policy.

## Local proof without Discord

Use Kitty's existing Python 3.12 environment:

```bash
cd ~/Projects/kitty/.worktrees/feat/discord-command-center-phase0
~/Projects/kitty/venv/bin/python -m integrations.discord_command_center.smoke --repo .
```

A successful smoke ends with `done` and `read-only diff audit clean`. A mutation ends with `readonly_violation` and the disposable worktree is preserved for inspection.

Progress status edits are coalesced to at most one every 2 seconds, and all Discord message/edit payloads are bounded to 1900 characters.

### Why Codex shows `danger-full-access` internally

Command Center deliberately disables Codex's *internal* sandbox because nesting it inside macOS `sandbox-exec` prevents Codex's app-server and shell from starting. This does **not** give the worker unrestricted macOS writes: the parent `sandbox-exec` profile is the actual OS boundary, permitting writes only inside the disposable run worktree (plus `/dev/null`). The read-only guarantee remains the mandatory post-run git audit; any repository mutation fails loudly and preserves the worktree.

Codex receives a throwaway HOME/CODEX_HOME inside that worktree and `--ignore-user-config`. Its runtime state is deleted before the audit so coordinator-owned cache files cannot hide a repository mutation.
Phase 0 also disables Codex apps, plugins, browser use, computer use, image generation, and multi-agent features. The worker is intended to inspect the local repository only.

## Discord application

Create a separate bot application named **Command Center**. Phase 0 needs OAuth scopes `bot` and `applications.commands` and these channel permissions: Send Messages, Send Messages in Threads, Create Private Threads, Read Message History, Embed Links, Attach Files, and Manage Threads. `Manage Threads` is narrowly required because the bot creates non-invitable private threads and must add the requesting member with `add_user`; it does not grant Administrator or broader moderation permissions.

Do **not** grant Administrator. The reaction-to-task phase may require
`Manage Messages`, public-thread creation, reactions, and the privileged
`MESSAGE_CONTENT` intent; this control slice does not. Keep `MESSAGE_CONTENT`
disabled until reaction-to-task is explicitly implemented and reviewed.

Configure the bot at runtime; never commit its token:

```bash
export COMMAND_CENTER_DISCORD_TOKEN='...'
export COMMAND_CENTER_GUILD_ID='123456789012345678'
export COMMAND_CENTER_WAR_ROOM_CHANNEL_ID='123456789012345678'  # optional in Phase 0
export COMMAND_CENTER_ALLOWED_USER_IDS='123456789012345678'  # required; comma-separated
# Or authorize a role instead of individual users:
# export COMMAND_CENTER_ALLOWED_ROLE_IDS='123456789012345678'
export COMMAND_CENTER_REPO="$HOME/Projects/kitty"
export COMMAND_CENTER_CODEX_PATH='/Applications/ChatGPT.app/Contents/Resources/codex'
export COMMAND_CENTER_CODEX_MODEL='gpt-5.4-mini'
# Safety limits; defaults are two total active runs and one per user.
export COMMAND_CENTER_MAX_CONCURRENT_RUNS='2'
export COMMAND_CENTER_MAX_RUNS_PER_USER='1'
~/Projects/kitty/venv/bin/python -m integrations.discord_command_center.bot
```

The Discord token is excluded from the Codex child environment. Outbound thread text is scrubbed for configured secret values and common OpenAI/GitHub/Discord token shapes.
The bot fails closed unless at least one allowed user ID or role ID is configured; authorization is checked before creating a task thread or starting Codex.

## Phase 1 controls

The bot remains slash-command-only and continues to use only the `guilds`
gateway intent. Each task receives an opaque ID in the ephemeral response and
task card. `/vibe-status` shows the requesting user's active task IDs, private
thread IDs, and elapsed time without echoing request text. `/vibe-cancel`
cancels the requesting user's active task by ID, or by the current private task
thread when no ID is supplied. Cancellation uses the existing worker process
group termination, cleanup, and audit path; uncertain cleanup preserves the
worktree for inspection.

Admission is bounded before a private thread is created. A full global limit or
per-user limit returns an ephemeral rejection and starts no worker. The task
registry is intentionally process-local: a bot restart does not claim that
in-flight tasks survive, and no durable queue or retry authority is introduced.

## Current boundary to KittyBuilder

Editing work does not exist in Phase 0 or this Phase 1 control slice. A later
phase may create an approved Builder proposal through a narrow Gateway endpoint,
then consume Builder status/evidence. Command Center must stop there:
KittyBuilder remains the execution service and inner spend authority.
