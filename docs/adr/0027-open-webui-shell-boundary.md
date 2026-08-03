# ADR 0027: Open WebUI may serve as Kitty's replaceable daily-driver shell

**Date:** 2026-08-02  
**Status:** Accepted  
**Decision authority:** Jacob explicitly directed the project to move back to Open WebUI and configure it as the daily-driver interface.

## Context

ADR 0019 ratified an audit-era recommendation that Khoj, Open WebUI, and Screenpipe remain study-only because of licensing and product-boundary concerns. That was a reasonable default while Kitty's own UI was the intended product surface.

The product decision has since changed. Jacob wants a usable personal AI workspace now, and the existing Kitty UI has not met that bar reliably. Stock Open WebUI already supplies the commodity chat shell, mobile-friendly conversation experience, persistence, model selection, and extension points that Kitty would otherwise have to rebuild and maintain.

Leaving ADR 0019 unchanged while installing Open WebUI as a persistent login service creates a governance contradiction: the code implements a decision the accepted architecture still forbids.

## Decision

Open WebUI may be installed and operated as Kitty's local daily-driver **shell**, subject to these boundaries:

1. **Kitty remains the authority.** Model routing, provider policy, memory, projects, Tutor, tools, personal context, and KittyBuilder boundaries remain owned by Kitty's Gateway and domain modules.
2. **Open WebUI remains replaceable.** Integrate through supported OpenAI/OpenAPI/configuration surfaces. Do not fork or move Kitty business logic into Open WebUI.
3. **Local single-user only by default.** The unauthenticated configuration may bind only to loopback. Any network exposure requires a separate security decision and authentication design.
4. **No ambient credential inheritance.** The Open WebUI process receives only the environment required to operate the shell and reach Kitty's local Gateway.
5. **Upgrades are explicit and reversible.** Pin the supported Open WebUI version; back up and isolate persistent data before a version change; preserve a tested rollback to Kitty's own UI.
6. **Success is end-to-end.** Health checks must prove that the shell can discover Kitty's models/tools and complete the intended user path, not merely that an HTTP process answers.
7. **Builder stays read-only from chat unless separately authorized.** The shell may inspect bounded Builder projections; it does not create, approve, publish, or merge work through this decision.

This ADR supersedes **ADR 0019 decision 7 only**. The study-only decisions for Khoj and Screenpipe remain unchanged.

## Consequences

- PR #384 is within authorized scope once it satisfies the boundaries above.
- Open WebUI-specific code should remain a thin adapter and operator layer, not a second Kitty architecture.
- Future shell replacements should reuse the same Gateway contracts rather than require migration of Kitty state or logic.
- Any fork, public/LAN exposure, or write-capable Builder integration requires a new explicit decision.
