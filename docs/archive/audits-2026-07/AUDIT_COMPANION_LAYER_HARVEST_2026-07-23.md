# Companion-Layer Harvest — code, workflows, architecture, and solved problems

<!-- kitty-audit
{
  "audit_id": "AUDIT_COMPANION_LAYER_HARVEST_2026-07-23",
  "authored_at": "2026-07-23T18:50:00-06:00",
  "authored_by": "opencode-free",
  "scope": "Companion layer for Kitty chat/builder/experts: chat tool execution, vibe-coder workbench, experts-over-docs, self-diagnosis feed, chat import onboarding. Companion to the 2026-07-20 KFX-001 frontend harvest.",
  "license_disposition": "See register. All copy/adapt candidates are MIT or Apache-2.0. GPL/AGPL/Commercial sources are study-only."
}
-->

## 0. Why this audit exists

The 2026-07-20 KFX-001 frontend harvest surveyed the landscape and chose direct-copy/adapt candidates (assistant-ui, pipali, khoj, InvokeAI, HA, etc.) based on a top-level review. This companion goes deeper: it clones the highest-value repositories, reads their source, and extracts the **things that would otherwise take us months to discover** — the failure-mode table for tool streaming, the pre-flight correction pass for LLM-emitted shell commands, the plain-English event layer, the minimal Repairs data model, the citation grouping pattern. Every claim below cites a file in the clone and can be re-verified.

If the value of the prior harvest was "what to steal," the value of this one is "**what they've already solved that we don't want to re-solve**." Every section closes with a direct mapping to a KX-05 packet so the work is never orphaned.

## 1. Methodology and disposition

Five repositories cloned shallow (`--depth 1`) at `/Users/jacobbrizinski/.local/share/opencode/tool-output/`. Anything-LLM and OpenHands used `--sparse` to keep the frontend/ tree only (the backends are not where the design lessons live). HA frontend used `--sparse` to land only the repairs panel and its data model — the rest of HA's frontend is too large to be worth cloning.

| Repo | Local path | License | What I read | Disposition |
|---|---|---|---|---|
| `assistant-ui/assistant-ui` | `aui/` | MIT | `packages/core/src/runtimes/tool-invocations/EDGE_CASES.md`, `packages/core/src/runtimes/tool-invocations/*`, `packages/react/src/primitives/toolCall/*` | Adapt + cite (open-source contract is the design) |
| `stackblitz-labs/bolt.diy` | `bolt/` | MIT | `app/lib/runtime/action-runner.ts`, `app/lib/runtime/message-parser.ts`, `app/lib/stores/workbench.ts` | Adapt patterns; do **not** import (Turborepo/Remix routing is not our stack) |
| `Mintplex-Labs/anything-llm` | `allm/` (sparse, frontend) | MIT (with `enterprise/` excluded by sparse) | `frontend/src/components/WorkspaceChat/.../Citation/*`, `frontend/src/components/Sidebar/ActiveWorkspaces/*` | Adapt citation + workspace patterns |
| `All-Hands-AI/OpenHands` | `oh/` (sparse, frontend) | Mostly MIT (`enterprise/` excluded by sparse) | `frontend/src/components/features/chat/event-content-helpers/*`, `frontend/src/components/features/chat/event-message-components/*` | Adapt plain-English event layer |
| `home-assistant/frontend` | `haf/` (sparse, repairs) | MIT | `src/data/repairs.ts`, `src/panels/config/repairs/*` | Adapt Repairs data model + fix-flow contract |

**Hard stops from the prior harvest remain in force:** no GPL/AGPL sources, no `open-webui/open-webui` (custom-branded license), no `screenpipe/screenpipe` (commercial).

## 2. assistant-ui — the tool-call contract

### 2.1 Architecture, in one paragraph

assistant-ui defines a streaming runtime where tool calls have a **state machine** that the UI must render correctly even under hostile streaming conditions (regressions, retries, race conditions, result mutations, rollback, history restore). The data lives in two packages: `assistant-stream` (the language-agnostic streaming protocol) and `react` (the React surface that wraps the protocol). The whole reason `ToolInvocationTracker` exists — the centerpiece of the package — is to guarantee exactly-once execution of the host's `streamCall` / `execute` callbacks per `toolCallId`, no matter how the snapshot mutates.

### 2.2 The file you must read

`aui/packages/core/src/runtimes/tool-invocations/EDGE_CASES.md` (194 lines).

This is a register of every non-obvious state transition the tracker has been observed to encounter, with the chosen behavior and the rationale. A near-verbatim summary, organized as the file is:

**Hard contract.** `streamCall` / `execute` fires **exactly once per logical `toolCallId`**. The tracker never invokes the host tool callback a second time. The host's side effects (which is the entire reason this callback exists) cannot double-run. The cost: post-completion mutations are not surfaced to the host through the tool callback; a planned `reader.events()` API will cover that case.

**Never throw in the hot path.** Every public method that observes runtime state (`setState`, `reset`, `abort`, `resume`) wraps its work in try/catch and logs to `console.error`. The tracker is on the message-processing hot path; a malformed snapshot must never crash the host runtime.

**A. Tool changes shape after first observation.** Six edge cases: args grow (normal streaming), args regress mid-stream (no restart, keep prior prefix, log divergence), args complete then equivalent-JSON key reorder (silent update, no re-fire), args complete then change to non-equivalent (no re-fire, no restart, log), first result (close controller + skip execute), result replaced (ignored), result lost (ignored).

**B. Tool call disappears from snapshot.** Do **not** auto-clean. A future snapshot may re-introduce the same `toolCallId`; auto-clean would re-fire `streamCall` and violate the exactly-once contract. The cost is bounded memory; `reset()` clears it.

**C. Initial vs live snapshot.** `isLoading=true` (history load) seeds entries as **restored** — `streamCall` does not fire. The first live snapshot **promotes** a restored entry to active only when its signature (args + result) changes. PR #4057's promotion path.

**D. Nested tool calls.** Identity by `toolCallId`, not array index. A different id at the same nested position is a fresh call; the same id with different shape re-runs A.1–A.4.

**E. Malformed snapshot.** Null message, non-array content, non-tool-call parts, identical-content different-reference, thrown handler — all silent skip + log. The `_lastSnapshot` / `_isRunning` mutations are deferred until *after* successful processing, so a transient failure does not corrupt the tracker's view.

**F. Concurrency and lifecycle.** `reset()` while execute in flight → `abort()`, reject with `Tool execution aborted`, drop late result chunks via `_skipExecuteStreamIds`. `setState` during reset → process against empty entries, seed restored (because reset re-armed `_pendingRestore`). `resume` for an unknown id → silent no-op. Pipeline itself errors → flip `_pipelineDead` once, demote active entries to restored before rebuilding (so rebuilt pipeline does not re-fire).

**Known limitations (documented, deferred).** Result delivery after args regression can race the args-text-finish chunk; tracked separately. Host callback throws are caught; the tracker's own loop survives. Args-stream divergence after A.2/A.4 is observable only through the future `reader.events()` API.

### 2.3 Solved problems (this is the steal list)

| # | Problem | How assistant-ui solved it | Maps to |
|---|---|---|---|
| 1 | LLM streams tool args in chunks; partial args must not re-fire execute | Snapshot-delta app, exactly-once contract | KX-02-01 tool cards |
| 2 | Mid-stream args regression (snapshot rewinds) | Keep already-streamed prefix, do not restart, log | KX-02-01 |
| 3 | Result delivered twice (e.g. backend re-sends) | `entry.hasResult` short-circuits both result paths | KX-02-01 |
| 4 | Rollback / branch switch removes a tool call | Do not auto-clean; treat reappearance as same id | KX-02-04 retry/recovery |
| 5 | History load replays old tool calls, re-firing side effects | Restored vs live distinction; promote only on signature change | KX-02-01 |
| 6 | Malformed snapshot kills the runtime | Never-throw, log-and-skip at every observer | KX-02-01 |
| 7 | Abort during in-flight execute | Per-action abort controller; drop late result chunks via skip-list | KX-02-04 |
| 8 | Pipeline itself errors | Flip `_pipelineDead`, demote-and-rebuild once | KX-02-04 |
| 9 | Host callback throws | Wrapper catches and logs; tracker survives | KX-02-01 |
| 10 | Nested tool calls lose identity across positions | Key by `toolCallId`, not index | KX-02-01 (when we add sub-tools) |

### 2.4 Code worth lifting (do not vendor the package)

The tracker is in TypeScript and tied to assistant-ui's stream model — the package as a whole is too heavy to drop into Kitty (it owns its own message protocol, runs in a different runtime boundary, and would couple Kitty's chat to a fork-prone surface). But the **state machine and the edge-case register** are pure logic. The way to steal it is to:

1. Copy the `EDGE_CASES.md` list into Kitty's own `gateway/kitty-chat/docs/CHAT_TOOL_INVARIANTS.md` (a Kitty-local copy, with a note that the original lives in `aui/packages/core/src/runtimes/tool-invocations/EDGE_CASES.md` and the MIT license is preserved).
2. Build a `gateway/chat_tools/tracker.py` that implements the same state machine in Python over the `/chat/turn` SSE stream, with the same exactly-once contract on the host side.
3. Write tests that reproduce each section of the EDGE_CASES doc (A.1 through F.4) against Kitty's own chat model adapter.

The single most important behavior to copy: **the `setState` deferred-commit pattern** (defer `_lastSnapshot` and `_isRunning` mutation until *after* successful processing). This is the difference between "transient failure retries cleanly" and "we have to restart the gateway."

### 2.5 Pitfalls to skip

- assistant-ui's primitives are React-rendering-focused. Kitty's chat needs the **tracker layer** to be Python (it's in front of the model route), not React. Do not try to import the package.
- The `reader.events()` API is "planned" in the doc — it does not exist yet. Do not depend on it.

## 3. bolt.diy — chat-driven workbench + pre-flight command correction

### 3.1 Architecture, in one paragraph

bolt.diy is a vibe-coder app where the LLM emits a stream of typed actions (`file`, `shell`, `start`, `build`, `mcp`) and the runtime executes them in order against a WebContainer filesystem + shell. The chat UI shows the actions as cards; the workbench shows the resulting file tree and a preview pane. The `ActionRunner` is the workhorse: it tracks per-action state through `'pending' | 'running' | 'complete' | 'aborted' | 'failed'`, owns a per-action `AbortController`, and exposes a callback for alert surfaces. The two design moves worth stealing are the **`ActionStatus` union** (not a string field) and the **`#validateShellCommand` pre-flight pass** that corrects LLM-emitted shell mistakes before they hit the shell.

### 3.2 The pre-flight pass — solved problems

`bolt/app/lib/runtime/action-runner.ts`, function `#validateShellCommand`. Verbatim rules (paraphrased from source):

| Rule | What the LLM emits | What the runner does | Why |
|---|---|---|---|
| `rm` without `-f` when target doesn't exist | `rm path/to/file` | Prepend `-f` flag, log "Added -f flag because some target files do not exist" | The LLM cannot know in advance which files exist; the runner can. `rm` returning non-zero aborts the whole action. |
| `cd` to a non-existent directory | `cd newapp` | Replace with `mkdir -p newapp && cd newapp` | LLM generates `cd` to a fresh dir before initializing it. |
| `cp` / `mv` with a missing source | (incomplete source visible) | `cp -r` fallback or skip-and-warn | (Saw partial code; full rule continues in source.) |

The pattern is: **never trust the model's command verbatim when a pre-flight check can correct it.** The runner returns `{ shouldModify, modifiedCommand?, warning? }`; the caller applies the modification and proceeds, with the warning recorded on the action for the UI to display.

### 3.3 Solved problems table

| # | Problem | How bolt.diy solved it | Maps to |
|---|---|---|---|
| 1 | LLM emits shell commands that fail on common edge cases | Pre-flight correction pass with explicit rule list | KX-05-03 (builder worker command validation) — the free worker runs shell commands; this pattern applies to the gateway's builder runtime |
| 2 | User clicks abort mid-action, action is half-complete | Per-action `AbortController`; `action.abort()` invoked; late result chunks dropped | KX-05-03 (cancel a running packet) |
| 3 | Action fails, error is opaque | `ActionCommandError` with `header` + `output`; UI alert shows both | KX-05-03 (decision cards: show the error plainly, not "Scope failure · attempt 2") |
| 4 | Validation passes for the wrong type (race in the state machine) | `unreachable('Expected shell action')` in `#runShellAction` — a *typed* precondition | KX-05-03 — model packet state as a discriminated union, not a string field |
| 5 | File write fails because parent dir doesn't exist | `fs.mkdir(folder, { recursive: true })` before `fs.writeFile`; error logged but action continues if mkdir fails | KX-05-03 — be tolerant of infra noise in the error log, fail loudly only on the user-facing result |

### 3.4 Code worth lifting

The `ActionStatus` union, verbatim, is the right shape for Kitty's packet state. The current Kitty code uses a `task_state` string field with values like `'blocked' | 'failed' | 'cancelled'`. Compare:

```ts
// bolt.diy
type ActionStatus = 'pending' | 'running' | 'complete' | 'aborted' | 'failed';
type ActionState = BaseActionState | FailedActionState;  // discriminated union
```

A discriminated union forces the renderer to handle each branch. Kitty's projection (`packetNeedsAttention`) currently counts `'cancelled'` as "needs attention" — that bug would have been impossible to write if the state were a tagged union where `'cancelled'` lives in a "terminal-by-operator" branch that the `attention` reducer doesn't even visit. **KX-05-03 should adopt this pattern.** Map to the gateway by changing `gateway/builder_queue_db.py` so the state column is a check-constrained enum, and update `BuilderSurface.tsx` to render a discriminated union.

The `ActionCommandError` with `header` + `output` fields is the right shape for KX-05-03 decision cards: the backend can return `{ kind: 'command_error', header: 'dev server failed', output: '...' }` and the UI renders header as the card title, output as the expanded details.

### 3.5 Pitfalls to skip

- bolt.diy is a Remix + Turborepo app with a WebContainer runtime. Do not adopt the build / routing. Steal patterns, not code.
- The `enhanced-message-parser.ts` is tightly coupled to WebContainer's filesystem. Not portable.
- The `#validateShellCommand` rules are written against a WebContainer shell (Node + Linux). Kitty's gateway shells out to bash on macOS; the rules need porting, not copy-paste.

## 4. anything-llm — citations and the "workspace = expert" model

### 4.1 Architecture, in one paragraph

Anything-LLM's central abstraction is the **workspace**: a doc collection plus a system prompt plus a chat mode (`query` for retrieval-augmented Q&A, `chat` for raw model). The chat layer renders answers with **inline citation chips** that point back to specific chunks of specific source documents. A user can click a citation to open the **Sources sidebar** with the full passage. The citation component is the design worth stealing — it solves three problems at once: dedupe by document, surface chunk-level provenance, and turn the model's "I read this somewhere" into a verifiable link.

### 4.2 The citation component — solved problems

`allm/frontend/src/components/WorkspaceChat/ChatContainer/ChatHistory/Citation/index.jsx`. The data shape and the rendering:

- **Group by document title.** When a retrieval returns multiple chunks from the same document, the component folds them: `combined[title].chunks.push(...)`. The user sees one citation per document, with chunk count and a similarity score badge on each chunk.
- **Similarity score as a percent.** `score` is a float in [0, 1]; rendered via `toPercentString(score)` next to the chunk. A `data-tooltip-id="similarity-score"` exposes a tooltip.
- **Source-type icons.** A `CIRCLE_ICONS` map: `file`, `link`, `youtube`, `github`, `gitlab`, `confluence`, `drupalwiki`, `obsidian`, `paperlessNgx`. A `CIRCLE_IMAGES` map for sources that have a brand image (`gmailThread`, `googleCalendar`, `outlookThread`). For `link` type, the component fetches a Google favicon service by hostname (`https://www.google.com/s2/favicons?domain=...&sz=64`) and falls back to the link icon on error. The `useState` / `useEffect` pair around `imgError` is the fallback dance.
- **Truncated chunk preview.** `truncate(text, 45)` for the title; the chunk text is shown in full when the user expands the source.
- **Decoding HTML entities** in the source title via `he` (HTMLDecode) — the LLM will return `&amp;` etc. and the title must render correctly.

### 4.3 Solved problems table

| # | Problem | How anything-llm solved it | Maps to |
|---|---|---|---|
| 1 | Multi-chunk citation to same doc is noisy | Group by document title, show chunk list under one citation | KX-05-04 (experts over books) |
| 2 | User can't tell if a chunk is relevant | Similarity score as percent with tooltip | KX-05-04 |
| 3 | Citation looks the same regardless of source type | Per-type icon map + favicon fallback for links | KX-05-04 |
| 4 | LLM emits HTML-entity-escaped text in citations | Decode on render with `he` | KX-05-04 |
| 5 | Long doc titles break the layout | `truncate(title, 45)` with ellipsis | KX-05-04 |
| 6 | "Workspace" abstraction hides doc collection + persona | One model object with `systemPrompt` + pinned docs | KX-05-04 (expert = persona + filtered book collection) |

### 4.4 Code worth lifting

The `CIRCLE_ICONS` / `CIRCLE_IMAGES` / `SourceTypeCircle` pattern is a clean way to express "different sources look different but render the same way." The Kitty version for KX-05-04 would have a `BookIcon`, `DocIcon`, `EmailIcon`, etc. — but the data shape (source-type + optional favicon URL) is what to copy.

The `score` field is a small but important thing to add to Kitty's `idea_mine_items` and any future evidence record. Today the gateway's memory evidence has no confidence field exposed to the UI; that's why "kitty remembered 13 things" reads as noise — there is no signal of "and these 11 are low-confidence." Add `score` to the evidence payload and the UI can hide low-confidence items by default.

### 4.5 Pitfalls to skip

- The full workspace management UI (admin) is overkill. Steal the model (persona + collection) and the citation component; ignore the rest.
- The Google favicon service is convenient but a privacy/availability issue. The Kitty version should resolve book covers locally from the manifest, not fetch a third-party favicon.

## 5. OpenHands — plain-English event layer

### 5.1 Architecture, in one paragraph

OpenHands runs an agent that emits a stream of typed events: `Action` (the agent did something — read, write, run, call_tool_mcp) and `Observation` (the runtime responded — file contents, command output, error). The UI renders these as chat messages. The component that turns the internal event type into a human-readable title is `frontend/src/components/features/chat/event-content-helpers/get-event-content.tsx`, and the pattern is **an i18n-keyed title table**: every event type has a translation key like `ACTION_MESSAGE$READ` or `OBSERVATION_MESSAGE$RUN` that resolves to a sentence with named placeholders. The component looks up the key with `i18n.exists(actionKey)`; if a key exists, it renders the translation with placeholders substituted; if not, it falls back to the uppercase event type. This is the only sane way to render agent trajectories without either (a) leaking implementation strings to the user or (b) hand-rolling one component per event type.

### 5.2 The plain-English event layer — solved problems

The key files:

- `oh/frontend/src/components/features/chat/event-content-helpers/get-event-content.tsx`
- `oh/frontend/src/components/features/chat/event-content-helpers/get-action-content.ts`
- `oh/frontend/src/components/features/chat/event-content-helpers/get-observation-content.ts`
- `oh/frontend/src/components/features/chat/event-content-helpers/should-render-event.ts`
- `oh/frontend/src/components/features/chat/event-content-helpers/parse-message-from-event.ts`

The translation-key pattern: `ACTION_MESSAGE$${event.action.toUpperCase()}`. Placeholders: `path`, `command` (trimmed to 80 chars by `trimText(command, 80)`), `mcp_tool_name`. Two renderer components — `<PathComponent />` (renders the path as a monospace span) and `<MonoComponent />` (renders the command as a monospace span) — are passed to `<Trans>` as `components={{ path, cmd }}`. `i18n.exists()` is the fast path: no key → fall back to `event.action.toUpperCase()`.

`trimText(command, 80)` is the unsung hero. LLM-emitted commands can be 4,000 characters of curl flags. The UI truncates to 80 and ellipses. The full command lives in the action's `args` payload and the user can expand.

`should-render-event.ts` is the noise filter. The repo keeps it short — most agents emit a few event types that are not worth showing to the user (system pings, internal checkpoints, the same observation twice). This file decides which events become chat messages and which stay internal. The pattern is a small list of predicate functions.

### 5.3 Solved problems table

| # | Problem | How OpenHands solved it | Maps to |
|---|---|---|---|
| 1 | Agent event types are implementation strings; UI leaks them | i18n-keyed title table; fall back to uppercase only when no key | KX-05-03 (packet titles, attempt history) |
| 2 | Commands are enormous in tool-call args | Trim to 80 chars in the title; full text in the expand | KX-02-01 (tool cards) |
| 3 | Paths and commands need visual treatment in the sentence | `PathComponent` + `MonoComponent` renderers passed to `Trans` | KX-02-01 |
| 4 | Some events are noise | `should-render-event.ts` predicate list | KX-02-04 (don't show every retry to the user) |
| 5 | LLM messages and agent observations interleave in the chat | `parse-message-from-event.ts` discriminates; user-assistant events get one rendering, observations another | KX-02-01 |

### 5.4 Code worth lifting

The **i18n-keyed title table with placeholder substitution** is the design to copy. For KX-05-03, the gateway should expose packet events with a `title_key` and `placeholders` shape, and the client resolves them through a local (or gateway-served) catalog. Example shape:

```json
{
  "event": "packet_attempt_failed",
  "title_key": "packet.scope_violation",
  "placeholders": { "packet_id": "KX-03-01", "file": "gateway/kitty-chat/src/app/page.tsx", "allowed_paths": "..." }
}
```

The client has a small catalog:

```ts
"packet.scope_violation": "Worker {packet_id} tried to touch {file}, which is outside {allowed_paths}",
"packet.identity_failure": "Worker {packet_id} got the repo identity wrong — rebase on current main first",
"packet.retry_exhausted": "{packet_id} ran out of retries; {last_error}"
```

That catalog replaces the current "attempt 2 · scope failure" titles with full sentences. The trim rule (80 chars max for any placeholder value) is what makes the rendered sentence fit a single line of the card.

`should-render-event.ts` becomes a `gateServerMessage()` in the chat client: a list of predicates that decide whether a packet-update event deserves to surface as a chat message. Today every packet state change probably reaches the user; with the gate, only the ones that need attention (new attempt started, attempt failed, decision required) become messages.

### 5.5 Pitfalls to skip

- OpenHands' agent state machine is Python (`agenthub`) and tied to Docker. Out of scope.
- The observation rendering uses Lexical for rich text; Kitty doesn't need that. The event-title pattern is independent of the body renderer.

## 6. Home Assistant — the Repairs pattern (KX-05-02 blueprint)

### 6.1 Architecture, in one paragraph

HA's **Repairs** feature is the canonical "system tells the user what's wrong, and offers a fix" surface. A repair is **not** an error log and **not** a notification. It is a first-class entity with a domain, a severity, a fixable flag, a learn-more URL, and a translation key for the user-facing text. The backend declares a repair; the dashboard renders it; the user can **ignore** it (durable state) or **fix** it (which opens a multi-step flow). The data model is tiny, the API surface is small, and the UX works because the backend decides what the user sees — the UI does not invent copy. KX-05-02's blueprint is this, plus the Kitty-shaped wrapper (a single `/repairs` endpoint that composes doctor + litellm + builder + disk into one feed).

### 6.2 The data model

`haf/src/data/repairs.ts`:

```ts
export interface RepairsIssue {
  domain: string;              // e.g. "kitty.builder", "kitty.litellm", "kitty.disk"
  issue_domain?: string;       // optional sub-domain
  issue_id: string;            // unique per domain
  active: boolean;
  is_fixable: boolean;         // backend declares: can we offer a fix?
  severity: "error" | "warning" | "critical";
  breaks_in_ha_version?: string;
  ignored: boolean;            // durable user state: did they ignore this?
  created: string;             // ISO timestamp
  dismissed_version?: string;  // version in which the user dismissed it
  learn_more_url?: string;
  translation_key?: string;    // user-facing sentence comes from here, not from a backend string
  translation_placeholders?: Record<string, string>;
}

export const severitySort = { critical: 1, error: 2, warning: 3 };
```

API:

- `repairs/list_issues` — fetch all
- `repairs/ignore_issue` — durable ignore / un-ignore
- `repairs/issues/fix` — `POST { handler, issue_id }` creates a fix flow (a multi-step dialog)
- `repairs/issues/fix/{flowId}` — `GET` and `POST` to step the flow
- `repairs_issue_registry_updated` — websocket event; the client debounces at 500ms (`debounce(..., 500, true)`) before refetching

### 6.3 Solved problems table

| # | Problem | How HA solved it | Maps to |
|---|---|---|---|
| 1 | System status leaks raw internals (e.g. "Exception in thread worker-2") | `translation_key` + `translation_placeholders`; the backend never sends the user-facing string | KX-05-02 (Repairs feed) |
| 2 | Some issues are advisory, some are urgent | `severity: critical \| error \| warning`; rendered in `severitySort` order | KX-05-02 |
| 3 | Some issues can be auto-fixed, some just need information | `is_fixable: boolean`; the UI renders the fix button only when true | KX-05-02 |
| 4 | User dismisses the issue; it re-appears on the next reload | `ignored: boolean` is durable; `dismissed_version` lets re-dismissals be per-release | KX-05-02 |
| 5 | Fixes that need user input (credentials, choices) need a flow, not a one-click button | `repairs/issues/fix` returns a `DataEntryFlowStep`; the UI steps through it | KX-05-02 (routes through the existing action queue: propose → approve → execute) |
| 6 | Update spam during a release with many issues | Debounce 500ms before refetching on the registry event | KX-05-02 |
| 7 | User wants to understand the issue beyond the title | `learn_more_url` opens a docs page | KX-05-02 (link to a `docs/REPAIRS/<id>.md` per issue) |
| 8 | Same issue keeps recurring after version bump | `dismissed_version` lets the team reset ignores on a new release | Future KX work |

### 6.4 Code worth lifting

The full data model. The API surface. The debounce pattern. The `severitySort`. The fix-flow contract.

For KX-05-02, the implementation is:

1. **Gateway endpoint `GET /repairs`** that returns `{ issues: RepairsIssue[] }` composed from:
   - `kitty doctor` JSON output (already exists; map to RepairsIssue shape)
   - LiteLLM reachability from the runtime manifest
   - Builder queue: stale lease, exhausted budget, zombie tasks (the exact things I cleaned today)
   - Disk: queue backup age, chroma size, books_manifest integrity
2. **Gateway endpoints `POST /repairs/ignore`** and **`POST /repairs/fix`** that route through the existing `action_queue` (T2 enforcement, T0 actions like "release a stale lease" can be auto-executed).
3. **Client component `RepairsCard.tsx`** that fetches `/repairs`, sorts by `severity`, renders one card per issue with title from `translation_key` (a small gateway-served catalog), `learn_more_url` as a footer link, and a "Fix" button when `is_fixable && !ignored`. The fix button opens a one-step confirm modal that calls the action queue's `propose` endpoint.

### 6.5 Pitfalls to skip

- HA's websocket subscription pattern is overkill for a single user. A simple `useQuery` with 30s refetch is sufficient.
- `breaks_in_ha_version` is a HA concept (semver cadence); not relevant to Kitty.
- The full HA "data entry flow" machinery (DataEntryFlowStep etc.) is bigger than what we need; the action queue is the right primitive.

## 7. Solved problems register — a flat list across all five repos

The harvest of solved problems, deduplicated and cross-referenced. Each entry: **problem → source → KX-05 mapping**.

1. **Tool execution must be exactly-once** under streaming regressions, retries, and snapshot mutations → assistant-ui EDGE_CASES §A–F → KX-02-01, KX-02-04.
2. **Never throw in the hot path** of a tracker / state observer → assistant-ui EDGE_CASES preface → KX-02-01.
3. **History-loaded tool calls must not re-fire** side effects → assistant-ui EDGE_CASES §C → KX-02-01.
4. **Result mutations after first observation are silently ignored** → assistant-ui EDGE_CASES §A.5–A.7 → KX-02-01.
5. **Pre-flight correction of LLM-emitted shell commands** (rm -f, mkdir before cd) → bolt.diy `action-runner.ts#validateShellCommand` → KX-05-03.
6. **Per-action abort controller** so a user-cancel does not leave the runtime in a half-state → bolt.diy `ActionRunner` → KX-05-03.
7. **Errors include header + output** for the UI to render title and detail → bolt.diy `ActionCommandError` → KX-05-03.
8. **Discriminated union for action / packet state** (not a free-form string) → bolt.diy `ActionState` → KX-05-03.
9. **Citations grouped by document** with similarity scores per chunk → anything-llm `Citation/` → KX-05-04.
10. **Source-type icon and favicon fallback** for heterogeneous provenance → anything-llm `SourceTypeCircle` → KX-05-04.
11. **HTML-entity decode in LLM-emitted titles** → anything-llm `he` import → KX-05-04.
12. **i18n-keyed title table with placeholder substitution** so internal event types never leak → OpenHands `get-event-content.tsx` → KX-05-03, KX-02-01.
13. **Truncate oversized placeholders** to fit the card title line → OpenHands `trimText(80)` → KX-02-01, KX-05-03.
14. **Per-event `shouldRender` predicate** to filter noise from the chat surface → OpenHands `should-render-event.ts` → KX-02-04, KX-05-05.
15. **Repairs as a first-class entity** with severity, is_fixable, ignored, translation_key → HA `RepairsIssue` → KX-05-02.
16. **Debounce 500ms on the repair registry event** to avoid update spam → HA `subscribeRepairsIssueUpdates` → KX-05-02.
17. **Multi-step fix flow** for issues that need user input → HA `createRepairsFlow` → KX-05-02 (via the existing action queue).
18. **Domain-prefixed issue IDs** so the same id can exist across subsystems without collision → HA `RepairsIssue.domain` → KX-05-02.

## 8. Code-harvest register — update for the 2026-07-20 audit

Updates and additions to the register in `docs/AUDIT_KITTY_FRONTEND_EXPERIENCE_HARVEST_2026-07-20.md` §Stage 5.

### 8.1 Direct-copy candidates (already vetted by the prior harvest)

| Mechanism | Source | License | Status |
|---|---|---|---|
| `react-photo-album` | `igordanchenko/react-photo-album` | MIT | Unchanged from prior audit |
| `yet-another-react-lightbox` | `igordanchenko/yet-another-react-lightbox` | MIT | Unchanged from prior audit |

### 8.2 Adapt candidates (new this harvest)

| Mechanism | Source | License | Lane | Why it solves a problem we have today | Integration size |
|---|---|---|---|---|---|
| Tool-call edge-case register | `aui/packages/core/src/runtimes/tool-invocations/EDGE_CASES.md` | MIT | KX-02-01 / KX-02-04 | 10 documented failure modes for streaming tool calls | Small (port to Python tracker; copy the table into a Kitty doc) |
| Tool-call exactly-once tracker | `aui/packages/core/src/runtimes/tool-invocations/*` | MIT | KX-02-01 | Guarantees host side effects run once regardless of snapshot mutations | Medium (write a Python port; do not vendor) |
| `ActionStatus` discriminated union | `bolt/app/lib/runtime/action-runner.ts` | MIT | KX-05-03 | Prevents the "cancelled counts as attention" bug by construction | Small (change the gateway column + client reducer) |
| `#validateShellCommand` pre-flight pass | `bolt/app/lib/runtime/action-runner.ts` | MIT | KX-05-03 | LLM-emitted shell commands corrected before they hit the shell | Small (port the rules, adapt to bash on macOS) |
| `ActionCommandError { header, output }` | `bolt/app/lib/runtime/action-runner.ts` | MIT | KX-05-03 | Backend returns structured error that the UI renders as a decision card | Small |
| i18n-keyed event title table | `oh/frontend/src/components/features/chat/event-content-helpers/get-event-content.tsx` | MIT | KX-05-03 | Backend emits `{ title_key, placeholders }`; client resolves through a local catalog | Small |
| `trimText(80)` placeholder truncation | `oh/.../get-event-content.tsx` | MIT | KX-05-03, KX-02-01 | Fits long error messages into a card title line | Small |
| `should-render-event` predicate list | `oh/.../should-render-event.ts` | MIT | KX-05-05 | Filters packet-update noise from the chat surface | Small |
| Citation grouping + score badge | `allm/frontend/src/components/WorkspaceChat/.../Citation/` | MIT | KX-05-04 | Renders chunk-level provenance grouped by document | Small |
| `SourceTypeCircle` per-source icon + favicon fallback | `allm/.../Citation/SourceTypeCircle` | MIT | KX-05-04 | Different sources look different but render the same way | Small |
| `RepairsIssue` data model | `haf/src/data/repairs.ts` | MIT | KX-05-02 | The shape of "system tells you what's wrong" — severity, is_fixable, ignored, translation_key | Small |
| Repairs fix-flow contract | `haf/src/data/repairs.ts` (createRepairsFlow, handleRepairsFlowStep) | MIT | KX-05-02 | Multi-step fix dialog for issues that need user input | Small (port the shape; use action queue) |
| Severity-sorted dashboard | `haf/src/data/repairs.ts` severitySort | MIT | KX-05-02 | Critical first | Small |
| Debounce 500ms on registry updates | `haf/.../repairs.ts` subscribeRepairsIssueUpdates | MIT | KX-05-02 | Avoid update spam during a release | Small |

### 8.3 Study-only register (new this harvest)

| Source | License | What to study | Why study-only |
|---|---|---|---|
| `All-Hands-AI/OpenHands` `agenthub/` | Mostly MIT, some non-MIT | Multi-agent state machine, sandbox lifecycle | Out of scope; KittyBuilder has its own execution model |
| `Mintplex-Labs/anything-llm` `enterprise/` | Custom / non-MIT | Workspace admin features | Not compatible with our license posture |
| `home-assistant/frontend` non-repairs | MIT | Lovelace card model, integration panels | Heavy; not on our roadmap |
| `stackblitz-labs/bolt.diy` Remix routing | MIT | App-level routing | Different framework |

### 8.4 Do-not-copy register (unchanged from prior harvest)

In force: no GPL/AGPL sources, no `open-webui/open-webui`, no `screenpipe/screenpipe`, no ComfyUI source. New: do not import the `assistant-ui` package itself (it owns its own message protocol; we want the patterns, not the dependency).

## 9. Mapping back to KX-05

Every KX-05 packet is anchored in this harvest.

| KX-05 packet | What this harvest gives it |
|---|---|
| **KX-05-01 Onboarding import** | Anything-LLM's workspace model (persona + collection) shapes the "expert" mental model the import feeds. The HTML-decode + truncate habits apply to the import summary. |
| **KX-05-02 Repairs** | The full HA Repairs data model + API + UX. Solved-problems #15–18. |
| **KX-05-03 Builder control deck** | Solved-problems #5–8 (bolt.diy), #12–13 (OpenHands). The discriminated-union state change prevents the "cancelled counts as attention" bug. The pre-flight pass goes into the gateway's builder runtime. |
| **KX-05-04 Experts shelf** | Solved-problems #9–11 (anything-llm). The citation card design. |
| **KX-05-05 Chat polish sweep** | Solved-problem #14 (`should-render-event`) for the `ActiveTaskCards` noise filter. |

## 10. Verification

Every claim in this audit is verifiable by `ls /Users/jacobbrizinski/.local/share/opencode/tool-output/{aui,bolt,allm,oh,haf}` and the file paths cited. The repositories were cloned at 2026-07-23T18:40–18:50-06:00 and not modified; HEADs are at the shallow `main` tip of each repo. License headers were verified from the LICENSE / LICENSE.md files at each repo root.

Companion back to:
- `docs/AUDIT_KITTY_FRONTEND_EXPERIENCE_HARVEST_2026-07-20.md` (the 2026-07-20 harvest this builds on)
- `docs/initiatives/kx-05-companion-layer-v1.json` (the manifest this harvest informs)
- `docs/ACTIVE_MISSION.md` (KFX-001, the charter)
