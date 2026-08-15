# Runtime truth receipt — issue #490 (Mac lane)

Captured 2026-08-15 from `/Users/jacobbrizinski/Projects/kitty`. No key values printed.
Nothing was cleaned, deleted, restarted, or reconfigured to produce this.

## VERIFIED

**Checkout is not the campaign baseline.**
- Branch `feat/builder-action-retirement` @ `01bb5e2d`; upstream `[gone]`.
- Campaign baseline `c01caddc` = `origin/main` = the PR #498 merge.
- `c01caddc` is **not** an ancestor of HEAD. HEAD is **6 ahead / 80 behind** origin/main.
- The shared-agent-workspace code from PR #498 **is not in this working tree**.
- 53 registered git worktrees.
- Stray empty file `main` at repo root shadows the branch name (`git log main` fails).

**Services**
| Port | PID | Owning checkout |
|---|---|---|
| :4000 UI | 8109 | `Projects/kitty/gateway/kitty-chat` |
| :8000 Gateway | 5199 | `Projects/kitty` |
| :8001 LiteLLM | 7154 | `~/kitty-services/venv-litellm` (**not this repo**) |

- Gateway health: `{"status":"ok","litellm_reachable":true}`.
- `kitty status` reports **"litellm not running"** while :8001 is listening and healthy — ownership detection is wrong.
- launchd `com.kitty.desktop.litellm` = pid **5209**, actual :8001 listener = pid **7154**. Duplicate or orphan.
- launchd loaded: `desktop.ui`(5196), `openwebui`(5219), `desktop.gateway`(5199), `desktop.litellm`(5209); `packet-drain`, `morning-brief`, `memory-prune`, `self-audit-skills`, `migration-audit` loaded, not running.

**Diagnostics**
- `kitty doctor`: 34 pass / 10 warn / 0 fail.
- `kitty builder initiative doctor`: 13 pass / 1 warn / 0 fail. Kill switch **enabled**. DB integrity ok.
- 18 initiatives paused (KPROOF-001/RETRY/FINAL-001/002/CLEAN-002/PAID-004/005/006, WORK-SPINE-001/004, autonomous-campaign-supervisor-v1, work-projection v1/v2/v3, ...). `CONSOLE-WORK-001` **failed**.
- codegraph daemon PID file exists, process dead — index may be stale.
- Continuity files record branch `fix/repo-prepush-gate-repair` @ `18dc32f4`; neither matches reality.

**Credentials** (names only)
- `.env` contains exactly three variables: `GATEWAY_SECRET`, `KITTY_GATEWAY_SECRET`, `OWNER_ID`. **No provider API keys.**
- Shell environment exports `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `NVIDIA_API_KEY`.
- `.env.before-agentrouter` (Jul 27) held `OPENROUTER_API_KEY` + `AGENTROUTER_API_KEY`; current `.env` (Aug 14) does not.
- No `OPENAI_API_KEY` anywhere — matches the `store:mem0` doctor warning.
- `GITHUB_TOKEN` in the environment is **invalid** (`gh` returns 401).
- `config/providers.json` order: `openrouter, local, openai, nvidia, gemini, agentrouter`; disabled: `[agentrouter]`.

**Local provider works**
- Ollama serving; `llama3.2:3b` returned `LOCAL_OK`.
- Models: `nomic-embed-text`, `llama3.2:3b`, `qwen3:4b`, `moondream`.

## INFERENCE

- The four-agent room run **cannot be attempted from this checkout** — PR #498's code is absent. Any result here would describe the wrong tree.
- PR #498's chain most likely died on **missing credentials in the process environment**, not on routing or orchestration: keys live in the shell (direnv) and not in `.env`, so a launchd-started service does not inherit them.
- The `openai` step in the chain will fail unconditionally — no key exists in any source checked.

## UNKNOWN

- Whether the OPENROUTER / GEMINI / NVIDIA keys still have credit or quota. **Not tested — testing costs money.**
- Whether the launchd-started Gateway inherited the shell keys, or is running without them.
- Whether LiteLLM at :8001 carries its own provider keys (its `/v1/models` requires a master key; returned 401).
- Whether the 53 worktrees include state that is still wanted. Nothing was pruned.

## Consequence for the campaign

Step 2 (live four-agent room run) is **blocked on being on the right code**, before any provider question.
Steps 3 and 4 inherit that block.
