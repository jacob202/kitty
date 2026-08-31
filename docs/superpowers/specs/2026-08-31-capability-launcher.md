# Capability Launcher Design

## Goal
Make Kitty's existing abilities visible and launchable from one keyboard-first surface without creating a second execution authority.

## Product contract
- Cmd-K remains the global entry point but becomes capability-first, not navigation-first.
- Gateway exposes a read-only capability catalog composed from Kitty-owned surfaces plus discovered Skills.
- Every capability declares a launch mode. Initial modes are `view` and `skill`.
- `view` capabilities route to the existing owning surface.
- `skill` capabilities compose an explicit `Use skill: <name>` directive into Chat; Kitty's context assembler resolves that exact installed skill and injects its prompt.
- Existing search and recent-chat behavior remain available below capabilities.
- No capability executes consequential mutations from the catalog itself.

## Initial catalog
Core: Work, Projects, Image Lab, Library, Automations, Agents, Tutor, Journal.
Dynamic: every currently discovered non-archived Skill.

## Safety / authority
The catalog is projection only. Views keep their existing authorities. Skills are loaded from the existing Skill Registry. Mutation approvals, Builder, automations, Image Lab, and ActionQueue semantics are unchanged.

## Acceptance
1. GET `/capabilities` returns core capabilities and current Skills with stable typed launch metadata.
2. `Use skill: agent-council` deterministically injects that installed skill rather than relying on fuzzy trigger matching.
3. Cmd-K shows capability descriptions/categories and routes a view capability immediately.
4. Selecting a Skill opens Chat with an explicit skill directive and focuses the composer.
5. Existing search/recent-chat tests stay green.
