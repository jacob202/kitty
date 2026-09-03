# KT-CHAT-TOOLS-01 — Kitty's chat can actually do things

**Initiative:** none — deliberately has no Builder manifest
**Owner:** codex (or an interactive session)
**Depends on:** `KT-TOOLBRIDGE-01` must be merged first
**Base:** `origin/main` `8cdc8e2e` or later
**Findings:** `CHAT-B001` — the frontend half
**Decision:** `D-012`, confirmed by Jacob as `D-015`

## Why there is no manifest
Frontend-only, and a Builder worktree has no `node_modules` (`PACKET_STANDARD.md`
F9, `D-007`). There is no Tier-1 gate Builder could run.

## What Jacob can do after this
Ask Kitty to do something in chat and have it happen, instead of being told
tools are unavailable.

## Why this is the next thing
The backend is not missing. It is finished, and nothing calls it. All verified
at the base SHA above:

- `gateway/routes/completions.py:345` — `caller_supplies_tools = bool(body.get("tools"))`.
- `gateway/routes/completions.py:548` — when the caller sends no tools, the
  request gets the `_NO_TOOL_EXECUTOR_SYSTEM` instruction, which tells the model
  to "state plainly that tools are unavailable".
- `gateway/routes/completions.py:586-589` — `tools`, `tool_choice` and
  `parallel_tool_calls` are stripped from the outbound request.
- `gateway/routes/completions.py:624` — the response reports
  `"tool_execution": "unavailable"`.

So the completions path honours tools the moment a caller supplies them. It
never has, because kitty-chat never sends any.

- `gateway/mcp_tool_bridge.py:349` `get_tool_schema_for_llm()` already publishes
  the schemas, and `gateway/routes/integrations.py:74` already serves them at
  `GET /mcp/tools`. `gateway/kitty-chat/src/lib/gateway.ts:1955` already fetches
  that endpoint — for a count on a status surface, not for chat.
- `gateway/mcp_tool_bridge.py:249` `invoke(server_name, tool_name, arguments)`
  already runs a tool with a bounded timeout, process cleanup and a failure
  cutoff. `KT-TOOLBRIDGE-01` exposes it over HTTP; that route is this packet's
  dependency.

## Jacob's ruling on approval
`D-015`, in his words: *"kitty chat almost never should need my okay for
anything"*. Do not add a per-call confirmation. Approval survives for exactly
four things, and none of them is a local tool call:

1. spending money,
2. sending something to another person,
3. deleting his data,
4. pushing or merging code.

If a tool falls in that list, confirm once for that call. Everything else runs.

## Plan
1. Confirm `KT-TOOLBRIDGE-01` is merged and read the route it added.
2. Read `gateway/routes/completions.py` around lines 340-630 so the request
   body matches what the backend already expects.
3. Fetch the tool schemas and include them in the chat completion request.
4. When the model returns `tool_calls`, run each one through the tool route,
   append the results as tool messages, and send the conversation back. Loop
   until the model answers without a tool call, with a bounded number of rounds.
5. Show Jacob what ran, in plain words, while it runs and after. He must be able
   to see what Kitty did without reading JSON.
6. A tool failure is shown, not swallowed. Use the reason the gateway returned.
   `ArtifactChatRejection` in `gateway/kitty-chat/src/lib/gateway.ts` is the
   precedent for surfacing the gateway's own `detail`.
7. Check at an iPhone-class width.

## Not in scope
Changing `gateway/routes/completions.py`, `gateway/mcp_tool_bridge.py`, or the
route `KT-TOOLBRIDGE-01` adds. Adding tools. Which MCP servers are configured.
Any per-call approval UI beyond the four-item list above. Streaming redesign.

## Stop condition
If wiring tools requires changing `completions.py`, stop. The premise of this
packet is that it already works; if that turns out to be false, the finding is
wrong and it needs re-scoping, not a wider fence.

## Verification
**Tier 1 — mechanical.** Not available to Builder. For Codex or a person:
`cd gateway/kitty-chat && npx vitest run --reporter=dot` and `npx tsc --noEmit`.
Tests must cover: tools are included in the request body; a returned tool call
is executed and its result fed back; a failing tool shows the gateway's reason;
the loop terminates at its bound instead of running forever.

**Tier 2 — running app.** A smoke spec at both `desktop` and `mobile` that
route-stubs the tool route and asserts a tool call is shown to the user and its
result reaches the reply. Never call a real MCP server from a smoke test.

**Tier 3 — product acceptance.** Required (D-008). An independent reviewer, on
the running product: ask Kitty to do something that needs a tool, confirm it
happens without a permission prompt, and confirm a failing tool says what went
wrong in plain language.

## Recovery
Frontend only. If it fails part-way, the dangerous half-state is a chat that
sends tools but cannot execute the calls that come back — that is worse than
today, because the model will promise actions it never takes. Ship steps 3 and
4 together or not at all.
