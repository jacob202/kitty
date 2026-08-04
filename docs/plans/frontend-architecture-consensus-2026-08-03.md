# Frontend architecture consensus and raccoon product direction — 2026-08-03

**Status:** reviewed synthesis and product-direction input. It does not supersede `docs/ROADMAP.md`, accepted ADRs, or the active Mission until formally reconciled.

**Sources summarized:** independent frontier-model reviews supplied by Jacob, including Kimi K3 and GLM 5.2 analysis, plus the final cross-review synthesis.

## Executive decision

Kitty needs two horizons, not another abrupt rewrite:

1. **Immediate daily driver:** finish and stabilize the pinned stock Open WebUI integration so Jacob has dependable chat, models, tools, image generation, persistence, startup, diagnostics, and rollback.
2. **Deliberate custom product surface:** when the daily driver is stable, build a fresh Vite + React + TypeScript application centred on the **Den**, using the Gateway as the product authority. Do not revive or incrementally archaeologize the existing Next.js frontend as the strategic foundation.

Open WebUI is the near-term chat shell. The future custom frontend exists to deliver Kitty's distinctive life-first, capacity-adaptive experience—not merely to reproduce generic chat.

## Product identity: raccoon direction

The visible product should move toward a raccoon identity because “Kitty” collides with the popular Kitty terminal emulator and many existing GitHub repositories.

Treat this as a compatibility-preserving product rebrand, not an indiscriminate code rename:

- use a friendly, simple cartoon raccoon as the mascot;
- begin with an inline SVG mascot and CSS animation;
- keep CLI names, paths, package names, APIs, and stored identifiers stable until an explicit migration decision is made;
- inventory user-facing names, icons, favicons, launch shortcuts, Open WebUI labels, prompts, docs, screenshots, repository descriptions, and onboarding copy;
- develop the final name and compatibility strategy separately from the visual mascot rollout;
- do not violate Open WebUI branding or licensing requirements.

Rive may be evaluated later if a reactive mascot state machine materially improves capacity modes. Do not add Lottie now.

## Agreed future frontend stack

- Vite
- React
- TypeScript
- shadcn/ui components copied into the project so Kitty owns the implementation
- TanStack Query for all server state
- React Router v7 in library mode unless a demonstrated routing requirement justifies TanStack Router
- Vite proxy for `/api` and `/ws` during development
- FastAPI serves the built SPA in production so the browser sees one origin
- TanStack Query Devtools in development
- per-panel error boundaries using `react-error-boundary` and query-reset integration

Next.js is not recommended for the future local product shell. Kitty does not need SSR or SEO, and the server/client boundary creates complexity without corresponding product value.

## Architectural rules

### The Gateway remains the product

The frontend is a thin client over current Gateway APIs. Do not move personal memory, life-first planning, authorization, routing, tool execution, provider attribution, or Builder truth into the browser.

### One owner of connectivity

Exactly one connectivity layer decides whether the Gateway is healthy and exposes that state to the rest of the UI. Individual panels must not independently invent “online,” “offline,” or “stale.”

Suggested ownership:

- `lib/health.ts`: health queries, timestamps, service projections, staleness policy
- `lib/socket.ts`: authenticated WebSocket lifecycle, heartbeat, reconnect, resynchronization

### The socket is a courier, not a store

WebSocket state is never authoritative.

- high-frequency transient streams, such as chat tokens, may update the relevant TanStack Query cache directly;
- state-change events invalidate affected queries and trigger a refetch from the Gateway;
- reconnect always resynchronizes authoritative state rather than trusting the missed interval.

### Reconnection requirements

- exponential backoff;
- jitter;
- bounded maximum delay and retry policy;
- server-side heartbeat around the verified infrastructure timeout window;
- authenticated reconnect and token-refresh handling;
- explicit degraded/offline state;
- refetch truth after reconnect.

Start with one native WebSocket implementation in `lib/socket.ts` because the current FastAPI side does not require Socket.IO. Evaluate `react-use-websocket` only if the native implementation becomes materially harder to test or maintain.

### Visible staleness

Every server-derived view exposes its freshness. Data older than approximately three times its intended poll interval renders visibly stale and must not silently appear current.

Use server timestamps when available and TanStack Query `dataUpdatedAt` as the client receipt time. The UI should distinguish:

- live/current;
- refreshing;
- stale;
- unavailable;
- last known value.

### Polling

- use adaptive `refetchInterval` functions;
- poll faster while work is active or recovery is underway;
- slow down when idle;
- use `networkMode: 'always'` for localhost health because browser internet-state events do not prove Gateway reachability;
- do not use polling to conceal a broken event contract.

### Panel isolation

One failed endpoint must not take down the Den. Each major panel receives an error boundary, an actionable failure state, and a bounded retry/reset action.

## Product sequence

Build the **Den** first. Deliberately defer Studio, Library, Projects, and deeper polish until the re-entry experience is excellent.

The Den is the primary “come back to my life and system” surface. It should answer:

- What is happening?
- What needs me?
- What is stale or broken?
- What is the one useful next move?

“It's a chat app trying to be a dashboard” is the product problem to correct. Chat remains important, but it is not the organizing metaphor for the custom application.

## Capacity-adaptive UI

Forage/focus mode is core product behaviour, not an optional theme.

For the first version, it is the same Den with different information density:

- **Forage:** stop after urgent and immediately actionable information, roughly ten lines or equivalent visual weight;
- **Focus:** expose deeper status, context, evidence, and controls.

Do not create two divergent screens. Preserve keyboard navigation, screen-reader structure, reduced motion, visible focus, and understandable state in both modes.

## Visual direction

The raccoon mascot should be inline SVG, small, themable, and editable by coding agents. CSS animation should primarily use transforms and opacity.

The design system must operationalize the intended hand-drawn, calm, slightly unpolished character rather than merely declaring colour variables. Define and test:

- subtle noise texture;
- irregular but consistent border radii;
- a restrained serif display face paired with a highly legible UI face;
- tactile cards and dividers without sacrificing clarity;
- accessible contrast;
- reduced-motion behaviour;
- keyboard-first navigation.

## Migration strategy

Use a strangler strategy until evidence supports retirement:

- Open WebUI remains the dependable chat surface during the transition;
- the existing Next.js UI remains rollback/reference, not the new strategic foundation;
- the Den is built as a fresh bounded application;
- secondary old screens may remain temporarily if they work and are not worth immediate migration;
- retire an old surface only after the replacement passes contract, browser, restart, and user-acceptance checks.

Do not kill a fallback merely to make the repository look clean.

## Required validation before custom frontend implementation

### Existing API contract

Inventory the Gateway before designing frontend contracts. For each required Den capability, record:

- current endpoint or WebSocket event;
- request and response schema;
- auth requirements;
- timestamps/freshness evidence;
- error semantics;
- whether the endpoint is authoritative or derived;
- missing backend work.

Do not invent `/api/health`, `/api/den`, `/api/session`, or other convenient endpoints without checking what already exists.

### Authentication and trust harness

Explicitly design and test:

- HTTP token storage and injection;
- WebSocket authentication;
- token expiry/refresh;
- reconnect after refresh;
- logout/revocation;
- local-only and future remote-access boundaries;
- redaction in logs and browser storage.

### Builder count correctness

The historical “55 Builder packets” problem is not automatically a frontend bug. Verify backend query truth, queue transitions, event emission, timestamps, and projection semantics before applying staleness UI as a cosmetic fix.

### Migration verification

Before retiring any old screen, compare old and new outputs against the same Gateway state and record reproducible evidence. Include expected failure, stale-state, reconnect, and service-restart cases.

### Service health specifics

Health projection must explicitly cover the real system, including Gateway, LiteLLM/providers, Builder, codegraph daemon where relevant, and the image-generation pipeline. A generic `services` map is not enough without verified semantics and remediation.

## AI-agent working agreement

The future frontend repository or directory must contain a short architecture contract that every coding session reads. It should state:

- Gateway is authoritative;
- TanStack Query owns server-state caching;
- one connectivity module owns health/offline state;
- WebSockets are couriers, not stores;
- stale data is visible;
- no duplicated API clients or ad hoc polling;
- accessibility is part of acceptance;
- one vertical slice at a time;
- do not expand scope until the current slice passes real-browser verification.

This document compensates for agent session amnesia and is an engineering control, not decorative prose.

## Jacob's minimum learning floor

Jacob does not need to become a frontend specialist. He does need enough understanding to supervise AI-generated changes:

- browser origin and CORS model;
- request lifecycle and timeouts;
- basic React render/state model;
- server state versus local UI state;
- Network tab, console, and query-devtools inspection;
- how to identify stale data and the authority behind a number.

The system should teach these concepts through observability rather than requiring framework archaeology.

## Explicit non-decisions

The following remain open until live repository/API inspection:

- final public product name;
- exact raccoon logo/mascot design;
- permanent disposition of every existing Next.js screen;
- native WebSocket versus `react-use-websocket` after a tested prototype;
- exact auth/token-refresh implementation;
- whether a dedicated aggregated Den endpoint is justified;
- timing of the custom frontend relative to Open WebUI capability onboarding.

## Near-term instruction

Do not let this future frontend decision derail the current Open WebUI baseline. Complete the daily-driver onboarding and verify it first. Then use this document as the starting architecture for a bounded Den prototype and adversarial review.