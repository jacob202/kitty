# Open WebUI daily driver — onboarding progress

Branch: `feat/openwebui-tomorrow-ready` · PR: [#384](https://github.com/jacob202/kitty/pull/384)

Machine-readable acceptance state: `docs/plans/openwebui-onboarding-checklist.json`.

Answers the four defects and the nine baseline criteria in
`docs/plans/openwebui-agent-handoff-2026-08-02.md`. Every OBSERVED statement it
carried about this Mac was re-checked live; the evidence below replaces it.

## Current objective

Slice 1 — the daily-driver baseline: launch, login, streaming, persistence,
diagnostics, backup, restore, rollback. Complete except where noted under
Blockers.

## Acceptance criteria for this slice

| # | Criterion | State |
|---|-----------|-------|
| 1 | Open WebUI starts from the login service with no shell attached | pass |
| 2 | The service never sees Kitty's `PYTHONPATH` or repo working directory | pass |
| 3 | Exactly one `admin@localhost` account, enforced on every start | pass |
| 4 | Real provider streaming reaches the user through Open WebUI | pass |
| 5 | Chats and the account survive a full service restart | pass |
| 6 | A provider failure shows the user a cause, not a blank reply | pass |
| 7 | `status` and `doctor` report actionable state | pass |
| 8 | `backup` → mutate → `restore` returns the earlier state | pass |
| 9 | `rollback` hands the day back to the existing Kitty UI | pass |
| 10 | No secrets or runtime data in the repository | pass |

## What was broken, and the evidence

### Chat could not complete a single turn

`config/providers.json` pinned `active: agentrouter`. An explicit pin never
falls through — `call_selected_provider` is deliberate about that — and
AgentRouter answers:

```
HTTP 401 {"error":{"message":"unauthorized client detected"},"type":"unauthorized_client_error"}
```

Every turn ended in `ProviderChainExhausted`. Switched to `active: auto` with
OpenRouter first (live key, verified against `https://openrouter.ai/api/v1/key`)
and `agentrouter` disabled until its token is replaced.

Commit `a659a1f9`.

### Every chat turn carried a 447KB system prompt

`compact_runtime_context` inlined the whole runtime manifest, and the manifest
embeds `build_runtime_snapshot()` — all 31 Builder initiative records.

| | before | after |
|---|---|---|
| `compact_runtime_context` | 428,958 chars | 4,455 chars |
| system prompt | 447,759 chars | ~24,200 chars |

Roughly 107k tokens of prompt per message, on a paid provider, that nothing
read. The Builder fact is now summarised to queue, integrity, worker sessions
and an initiative count; the full snapshot stays on the manifest endpoint and
the Builder CLIs.

Commit `ad616048`.

### Kitty memory was dead, and the embedder cold-started every turn

Two failures compounded:

- `gateway/memory.py` configured mem0's Ollama embedder, but the `ollama`
  client was not installed. mem0 prompts on stdin when it is missing, which
  under launchd is `EOFError` — so `memory initialization failed` on every
  request. Fixing that surfaced the next one: mem0's `litellm` LLM provider
  imports an SDK Kitty deliberately keeps out of the gateway venv. Moved to
  mem0's `openai` provider, which routes to OpenRouter on its own.
- Ollama evicts an idle model after ~5 minutes and reloading
  `nomic-embed-text` costs ~46s on this Mac, far past the 5s query timeout. So
  knowledge context silently vanished after any idle gap, and preprocessing ran
  19–78s. The embed request now pins the model with `keep_alive`.

| | before | after |
|---|---|---|
| preprocessing | 19,083–78,004 ms | 3,856–4,137 ms |
| time to first token | 25.6–27.7s | 3.8–6.4s |

`add_memory` → `list_memories` round trip returns the stored fact.

Commit `b3f1c6d2`.

### Open WebUI's MCP SDK was shadowed by Kitty's own `mcp/` package

Reproduced, running from the repo working directory:

```
ImportError: cannot import name 'ClientSession' from 'mcp'
  (<repo root>/mcp/__init__.py)
```

Two vectors, both fixed:

- `runtime_env()` copied `os.environ` wholesale, and `./kitty` exports
  `PYTHONPATH=<repo root>`. It now drops `PYTHONPATH`, `PYTHONHOME`,
  `PYTHONSTARTUP` and sets `PYTHONNOUSERSITE=1`.
- Python puts the working directory on `sys.path`. The LaunchAgent ran with
  `WorkingDirectory` = repo root, and the foreground `service` path inherited
  this process's directory through `execve`. Both now run from the service
  root.

`PYTHONPATH` is absent from the plist rather than set empty — an empty
`PYTHONPATH` puts the working directory back on the path.

Verified on the running launchd process: `cwd` is the service root, only
`PYTHONNOUSERSITE=1` is set, and `import mcp` resolves to the venv's SDK.

### Six pending admin accounts, and the activation wall

One bug, two symptoms.

`WEBUI_AUTH=False` signin checks for `admin@localhost` and inserts it when
absent. The check and the insert are not atomic and `user.email` has no unique
index, so the concurrent signins a first page load fires all missed and all
inserted — six rows sharing one `created_at`.

`signup_handler` then inserts at `DEFAULT_USER_ROLE` (stock: `pending`) and
promotes only when the new row is the *single* row after its own insert. With
six racing inserts nobody qualified, so every account stayed `pending` and Open
WebUI showed "Account Activation Pending" — with no second user who could
approve it.

Three changes, all idempotent:

- `DEFAULT_USER_ROLE=admin`. This is a single-user local install; there is
  nobody to approve anyone.
- `dedupe_system_admin()` runs on every start while the server is down. It
  refuses rather than deleting when a duplicate owns rows in any table with a
  `user_id` column, and promotes the survivor if it is not already admin.
- `claim_system_admin()` does one serial signin after the server is healthy, so
  a fresh database gets its admin from a single request and the race has no
  window.

Live: 6 accounts → 1, and the account kept is the one the UI was already using.
Forcing that row back to `role='pending'` and restarting returns it to `admin`
with no intervention.

### A provider failure reached the user as a blank reply

The gateway emitted its `{"error": {...}}` frame and then re-raised, tearing the
connection down. Open WebUI cannot parse that frame and saw no `[DONE]`, so the
user got an empty assistant message. The smoke test reported `did not produce a
complete SSE response` — true, and useless.

`sse_error_event` now emits three frames in a load-bearing order:

1. Kitty's `{"error": {...}}` frame — `chat-client.ts` throws on it and never
   reads further, so it must stay first or Kitty's own UI shows the failure
   twice.
2. An OpenAI-shaped chunk with the same copy in `delta.content`.
3. `[DONE]`.

Proven end to end by temporarily re-pinning the revoked provider:

```
Open WebUI shows: "Kitty couldn't complete this request — the selected model
provider didn't accept it (it may be out of credit or unavailable). Your
message is saved. Tap retry, or check Settings to pick a different model."

smoke exit=1: Gateway refused the streaming turn — routing: Kitty couldn't
complete this request …
```

### `.env` held a dead duplicate of the gateway secret

`ensure_gateway_secret` tested the shell environment, not the file, so
`append_env_secret` added a second `GATEWAY_SECRET` with a different value.
Line 3 returned HTTP 401; line 15 returned 200. Any reader taking the first
match authenticated with the dead one.

`append_env_secret` now replaces the key in place. Verified idempotent over
three rewrites in isolation, and `./kitty install` no longer duplicates keys on
the real file. The live `.env` was rewritten to keep only the working values,
backed up first.

### `./kitty up` tears down the launchd stack

`cmd_down` boots out `com.kitty.{ui,gateway,litellm}`, so rollback's original
`./kitty up` call took the whole stack down on its way to putting the UI back —
observed live, gateway and LiteLLM vanished from `launchctl list`. Added
`./kitty ui`, which starts only the Next.js UI, and rollback now uses
`./kitty install` + `./kitty ui`.

## Configuration applied

Environment is authoritative (`ENABLE_PERSISTENT_CONFIG=False`), so
`runtime_env()` in `scripts/openwebui_tool/common.py` is the single source.

- Kitty Gateway is the only OpenAI-compatible backend; Ollama probing off.
- `kitty-default` is the default, pinned, and task model.
- `ENABLE_EVALUATION_ARENA_MODELS=False` — removed the stray `arena-model`
  entry that sat next to `kitty-default` in the menu.
- Telemetry off: `ANONYMIZED_TELEMETRY`, `DO_NOT_TRACK`, `SCARF_NO_ANALYTICS`.
- Community sharing and version-update checks off; bound to `127.0.0.1`.

## Operator commands

```bash
python3 scripts/openwebui_local.py status
python3 scripts/openwebui_local.py doctor
python3 scripts/openwebui_local.py smoke --accept-charges
python3 scripts/openwebui_local.py backup
python3 scripts/openwebui_local.py down && python3 scripts/openwebui_local.py restore
python3 scripts/openwebui_local.py rollback
```

## Blockers for Jacob

1. **The AgentRouter token in `.env` is revoked.** It answers
   `unauthorized_client_error`. Kitty runs on OpenRouter instead, which is
   verified working with credit. Replace the token or leave AgentRouter
   disabled — nothing else needs it.

## Next action

Slice 2 — the user-facing model set (`Kitty Auto` / `Fast` / `Think` / `Code` /
`Vision` / `Image`), which needs gateway-side aliases before Open WebUI can
present them.

## Temporary runtime state

- Ollama was wedged (1d22h uptime, embeddings never returned) and was
  restarted. It runs unmanaged — `homebrew.mxcl.ollama.plist` exists in
  `~/Library/LaunchAgents` but is not loaded, so Ollama does not start at
  login. Knowledge/RAG needs it. Not yet resolved.
- Backups written during this work live under
  `~/kitty-services/openwebui/backups/` (mode 0700, outside the repository).
