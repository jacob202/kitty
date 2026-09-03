# OK-TOOLS-01 — Tools and Capabilities Work From Product Language

**Status:** draft candidate; not activated
**Roadmap phase:** 3 — companion completion

## Mission
Make Kitty's safe tools/capabilities usable from Chat and discoverable elsewhere without requiring Jacob to understand MCP servers, schemas, plugin registries, or environment wiring.

## Depends on
- `KT-CHAT-TOOLS-01` frontend tool loop after its bridge dependency is truly available.
- `KH-PLUGIN-01` / `KH-CAPABILITY-01` for truthful capability health where needed.
- Existing approval rules remain authoritative: spending, sending to others, deleting user data, and publishing code retain their explicit gates.

## Product acceptance moment
Ask Kitty in Chat to perform a safe local action that requires a tool. Kitty selects/invokes it, visibly explains what ran in product language, incorporates the result, and finishes the answer without a generic permission prompt. Then exercise one unavailable capability and get one truthful reason/next action.

## Required behavior
- Tool schema discovery comes from the existing bridge/capability authority; no hardcoded frontend tool catalog.
- Tool-call loop is bounded and cannot run indefinitely.
- Safe local calls run without unnecessary confirmation; consequential calls preserve the existing approval boundary.
- Tool execution and final model answer are distinct; a successful tool call cannot be reported if invocation failed.
- Failure preserves the tool name/purpose in human terms plus the gateway's safe reason/recovery.
- Capability discovery shows useful names/descriptions and configured/available state, not raw server IDs.
- Command palette/action discovery may reuse the same capability metadata instead of maintaining a second list.

## Verification
**Tier 1:** tool bridge/chat client/capability tests including success, failure, loop bound and approval-required class.

**Tier 2:** desktop + iPhone-class Chat running-app proof with one safe tool success and one unavailable tool/capability; no raw MCP/provider jargon required for the normal path.

**Tier 3:** independent reviewer completes the safe action without terminal intervention and verifies the unavailable case is actionable.

## Non-goals
- Adding a large new tool catalog.
- A second plugin execution engine.
- Removing consequential-action approvals.

## Done when
“Kitty can do things” is a real product property rather than a backend capability count.
