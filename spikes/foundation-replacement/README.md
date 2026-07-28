# Kitty foundation replacement spike

This spike tests whether Kitty should keep its current `assistant-ui` shell or move onto a mature, permissively licensed application foundation.

## Non-negotiable legal rule

Only foundations whose core code is permissively licensed and may be modified, rebranded, and redistributed are eligible. Open WebUI is excluded as a fork target because its current custom license does not meet that rule. No Open WebUI source code is copied here.

Eligible candidates in this spike:

- **Current Kitty + assistant-ui** — MIT-licensed component foundation already used by `gateway/kitty-chat`.
- **LibreChat** — MIT-licensed full application foundation.
- **AnythingLLM** — MIT-licensed full application foundation.

The external repositories are cloned at pinned commits into a disposable directory outside this repository. The bootstrap script verifies that each checkout contains an MIT license before applying Kitty-only configuration.

## What is being proved

All candidates must use the same existing Kitty intelligence path:

```text
candidate UI -> Kitty Gateway /v1/chat/completions -> Kitty context + memory + routing -> provider
```

The spike does not replace Kitty's personal intelligence, permissions, continuity, projects, model policy, Image Lab, or KittyBuilder. It tests which mature shell lets those Kitty-owned capabilities reach the user fastest.

## Prerequisites

- Kitty Gateway running on `127.0.0.1:8000`
- Docker Desktop running
- `git`, `curl`, and `docker compose`
- `GATEWAY_SECRET` exported in the shell

No secret is written to this repository. Candidate-local `.env` files are created only in the disposable work directory.

## Run

```bash
export GATEWAY_SECRET='the same value Kitty Gateway uses'

# Verify the existing Kitty compatibility surface without invoking a model.
./spikes/foundation-replacement/bootstrap.sh verify

# Start one candidate at a time.
./spikes/foundation-replacement/bootstrap.sh librechat
./spikes/foundation-replacement/bootstrap.sh anythingllm

# Stop a candidate.
./spikes/foundation-replacement/bootstrap.sh stop librechat
./spikes/foundation-replacement/bootstrap.sh stop anythingllm
```

Default locations and ports:

| Candidate | URL | Disposable checkout |
|---|---|---|
| Current Kitty | `http://127.0.0.1:4000` | existing repo |
| LibreChat | `http://127.0.0.1:3080` | `~/.cache/kitty-foundation-spike/librechat` |
| AnythingLLM | `http://127.0.0.1:3001` | `~/.cache/kitty-foundation-spike/anythingllm` |

Override the work directory with `KITTY_FOUNDATION_WORKDIR`.

## Evaluation

Run the same real workflows in all three candidates and record evidence in `RESULTS.md`:

1. Start a new conversation and verify Kitty-specific personal context reaches the model.
2. Switch the underlying model without losing the conversation.
3. Attach a document and continue within a project/workspace.
4. Complete one tool-backed task.
5. Resume the conversation from a phone-sized viewport.
6. Inspect how much candidate code would need modification for Kitty projects, permissions, proactive interventions, Image Lab, and Builder status.

A candidate wins only if it materially reduces custom plumbing without forcing Kitty's unique product model into the candidate's assumptions.
