# Open WebUI daily driver — onboarding progress

Branch: `feat/openwebui-tomorrow-ready` · PR: [#384](https://github.com/jacob202/kitty/pull/384)

Machine-readable acceptance state: `docs/plans/openwebui-onboarding-checklist.json`.

Answers the four defects and the nine baseline criteria in
`docs/plans/openwebui-agent-handoff-2026-08-02.md`. Every OBSERVED statement it
carried about this Mac was re-checked live; the evidence below replaces it.

## Current objective

Slice 5 — Image Studio. The hosted lane works and is switched off pending
Jacob's decision on cost. Slices 1–4 are complete and verified; see below.

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

Jacob decides on image cost. With the switch on, the remaining work is
uploaded-image editing against a real photo and a `Kitty Image` menu row.

## Slice 2 — the model menu

`/v1/models` returned one id, so the menu was a single row and every message went
to the same model whatever the work was. It now returns five, with names and
descriptions Open WebUI renders:

| Menu | Route | Model |
|---|---|---|
| Kitty Auto | `kitty-default` | complexity classifier picks the tier |
| Kitty Fast | `kitty-small` | `deepseek/deepseek-v4-flash` |
| Kitty Think | `kitty-think` | `qwen/qwen3-235b-a22b-thinking-2507` |
| Kitty Code | `kitty-code` | `qwen/qwen3-coder` |
| Kitty Vision | `kitty-vision` | `mistralai/mistral-small-3.2-24b-instruct` |

`Kitty Image` is deliberately absent: image generation runs through Kitty's
`image_jobs` pipeline, not chat completions, and a menu row that fails when
picked is worse than no row.

Three things had to be true for the menu not to lie:

- **Think was a placebo.** `kitty-sonnet` pointed at `deepseek-v4-pro`, which is
  what `kitty-default` already serves. A test now fails if any two menu rows
  resolve to the same upstream model.
- **Vision was broken.** `kitty-vision` pointed at `mistral/mistral-small-latest`,
  which is not an OpenRouter model id — that route answered 404 for every image
  ever sent to it.
- **Auto was auto in name only.** The chat endpoint honoured whatever id arrived,
  so the classifier never ran. Only the auto ids reroute now; a pinned choice
  stays pinned.

Measured through Open WebUI: Auto 7.5s, Fast 5.5s, Think 4.7s to first token.

Also fixed here: the Open WebUI health check called `./kitty down` then `up`,
and `down` boots the launchd jobs out entirely — so a Gateway that was merely
slow came back as a shell-owned process that dies with the terminal and never
returns after a reboot. It reloads the launch services in place now.

## Hazard: KittyBuilder resets the primary checkout

An operator campaign (`initiative run … --publish --gate auto`) merges packets to
main, and each merge calls `_prepare_main_worktree`. That treats `path.is_dir()`
as proof of a worktree and then hard-resets to `origin/main` with `cwd` set to
it — but a missing or half-removed directory under
`.worktrees/kittybuilder-merge-check` makes `git -C path` walk up to the primary
checkout instead.

Observed twice in one session: the branch ref moved to `origin/main` and the
working tree was replaced, reflog reading `reset: moving to origin/main`.
Uncommitted work was destroyed both times.

The guard is committed here (`_prepare_main_worktree` now refuses unless the
directory resolves to itself as a git toplevel), but it is not on `main` yet, so
a campaign running from the primary checkout does not have it. Until this branch
lands, treat an unattended Builder campaign and uncommitted work in the primary
checkout as mutually exclusive.

## Slice 3 — Kitty's capabilities as tools

Open WebUI calls an OpenAPI server's operations as tools, so whatever the spec
lists is what the model can reach. The Gateway's own `/openapi.json` describes
more than two hundred operations across 54 route modules. `/tools/v1` is a
deliberate menu of six instead, each delegating to the function that already owns
the behaviour:

| Tool | What it reaches |
|---|---|
| `search_memory` | personal memory — facts, preferences, history |
| `remember` | store a durable fact |
| `search_notes` | the knowledge base (Tutor's substrate) |
| `list_projects` | tracked projects, life before code |
| `project_next_step` | one concrete next action |
| `builder_status` | queue counts and packets needing a human |

`builder_status` returns counts and attention items, never the corpus — the raw
snapshot is 425KB and a tool result lands in the model's context verbatim.

Registering the server was not enough. Kitty stripped `tools` from every request
and appended "tools are unavailable in this chat runtime" to the system prompt —
correct while nothing here could execute a call, and the reason the model
answered "tools are unavailable" with the Kitty server sitting there connected.
A caller that sends schemas is the one that runs the calls, so Kitty now forwards
them and drops the notice when they are present.

Verified live: the model emits a real call to `builder_status`, and the Gateway
trace reports `tool_execution: caller`.

### Two bugs the tools exposed on their first call

- **Memory search had never worked.** `search_memory` passed `user_id` inside
  `filters` rather than as the named argument, so mem0's own `user_id` stayed
  unset and it rejected every scopeless search with a `ValidationError`. `add`
  and `list` pass it correctly, which is why memory looked healthy. A test was
  asserting the broken call shape.
- **The embed `keep_alive` added earlier in this branch was wrong.** It was the
  string `"-1"`; Ollama parses that as a duration and answers `time: missing unit
  in duration "-1"`, so every knowledge lookup returned HTTP 400. It has to be
  the integer. The chat-latency measurement that "verified" the original change
  did not exercise the embed call itself.

## Slice 4 — agents, Tutor, calendar

Five workspace agents, created and updated idempotently on every start. Each is
one routing id plus a narrow system prompt and only the tools it needs:

| Agent | Runs on | Tools |
|---|---|---|
| Daily Kitty | Auto | all — life before code, personal facts via tools not guesses |
| Research | Think | all — cite the source or say it rests on nothing |
| Coding | Code | none |
| Tutor | Auto | all — answers only from ingested documents |
| Builder Operator | Auto | all — reports state, starts nothing |

Open WebUI opens on Daily Kitty and pins the five. The raw `kitty-*` ids stay
selectable but are plumbing, not the daily menu.

Two more tools: `calendar_today` and `ask_tutor`. The model picks
`calendar_today` unprompted when asked what is on the schedule.

`/tutor/ask` answered HTTP 500 whenever nothing had been ingested on a topic —
a fact about the library, not a server fault, and as a 500 it read as a crash
while hiding the one instruction that fixes it. It is a 404 now, and the tool
wrapper returns the shortfall as a normal result so the model relays it.

**Gmail and GitHub are deliberately absent.** No such surface exists in the
Gateway to expose. A tool that cannot answer is worse than no tool.

### `down` was fighting launchd

`down` signalled the pid while the LaunchAgent was still loaded. KeepAlive
restarted the process immediately, so the service looked stopped and then raced
the next start for port 3000 — which is exactly how the run meant to create these
agents failed. It unloads the job now and says plainly that login startup is off.

## Slice 5 — Image Studio

Image generation was not unproven, it was **unavailable**. Both existing engines
are local and neither runs on this Mac: Draw Things reports unavailable and
`DT_URL` does not resolve, ComfyUI is not up. `/image/status` said only
`available: false` and never said why.

The hosted lane is now a third engine inside the same runner, so it reuses the
`image_jobs` lifecycle, the artifact directory, history, and cancel rather than
growing a second pipeline. The model accepts image input as well as text, so the
same path does uploaded-image editing.

**Proven end to end through Kitty's own pipeline:** job created, transitions to
`SUCCEEDED`, a 497KB PNG persisted under `data/images/<job_id>/`, provider
recorded as `openrouter`. Two bounded paid runs, about $0.13 total.

**It is off by default.** `KITTY_IMAGE_PAID_ENABLED` is unset, the refusal lands
before the HTTP call, and `/image/status` reports the price and the switch
instead of a bare `false`. Measured 2026-08-02: **$0.067 per image** on
`google/gemini-3.1-flash-image`. Cheap next to a rented GPU box, not free, and
fal was retired over exactly this — so the switch is Jacob's.

`Kitty Image` stays off the chat menu until the lane is on. A row that fails when
picked is worse than no row.

## Temporary runtime state

- Ollama was wedged (1d22h uptime, embeddings never returned) and was
  restarted. It runs unmanaged — `homebrew.mxcl.ollama.plist` exists in
  `~/Library/LaunchAgents` but is not loaded, so Ollama does not start at
  login. Knowledge/RAG needs it. Not yet resolved.
- Backups written during this work live under
  `~/kitty-services/openwebui/backups/` (mode 0700, outside the repository).
