# Project Status

**Repository evidence verified:** 2026-08-04 through `main` `c266b13c0c694929c728a3f3861187f56229dbac`, plus the documentation-only reconciliation in PR #398.

This file is a dated evidence summary, not a live runtime dashboard. Use Git/GitHub for repository state, supported probes for local services, and Builder's supported database/API/CLI for execution state.

## Current architecture

- Kitty Gateway is the product authority for conversation behavior, memory/context, projects, tools, Tutor, provider policy, and user-facing workflows.
- Open WebUI is the accepted replaceable local daily-driver shell under ADR 0027.
- The custom `kitty-chat` client remains a loopback-only fallback and development surface.
- KittyBuilder is the separate engineering execution control plane. GitHub issue comments are no longer a command queue.

## Verified repository state

- PR #400 restored native OpenRouter model IDs and returned deterministic pytest to green.
- PR #401 repaired private-repository PR diff retrieval for Agent Review.
- PR #402 removed unauthenticated all-interface `kitty-chat` listeners, enforced loopback binding, and completed issue #158.
- Issues #127, #158, #160, #161, and #381 are closed with evidence or explicit supersession comments.
- Current CI includes pytest, lint, typecheck, hygiene, Kitty Chat tests/build, and browser smoke; all passed on the final heads of #400–#402.
- ADR 0027 exists on `main` and defines the Open WebUI shell boundary.
- Personal image history remains unchanged by explicit owner decision.

## Active work

The one approved mission is [`ACTIVE_MISSION.md`](ACTIVE_MISSION.md): establish a trustworthy daily-driver baseline before broader expansion.

Immediate repository work:

1. merge the isolated `pydantic-settings` security update in #403 after current CI;
2. merge this authority/documentation reconciliation in #398;
3. complete #399's workflow ledger and enforceable protection proposal;
4. prove the local Open WebUI clean-start/chat/persistence/restart path;
5. complete one real #270 phone/PWA continuity loop.

Preserved but not current execution:

- #391 contains useful PAA alignment documentation but requires rebase and revalidation;
- #396 contains valuable model-policy, image-contract, and Builder-effectiveness work but is too broad to merge as one runtime-unproven unit;
- #316, #317, and #320 are independent dependency updates requiring separate current-CI review.

## Known unknowns

Repository evidence does not prove:

- Jacob's current local service, launchd, credential, quota, or provider state;
- that Open WebUI completes a real streamed chat and persistence/restart loop on Jacob's Mac today;
- current local Builder initiatives, packets, attempts, leases, or budgets;
- the real-phone timed-return and deduplication evidence required by #270;
- paid image-generation quality, likeness, cost, or cleanup state.

Unknown is not success and must not be presented as failure without evidence.

## Governance gaps

- The default-branch ruleset remains disabled.
- Fifty-one Actions workflows remain active, including one-shot and overlapping recovery workflows.
- Dependabot security alerts remain disabled through the accessible repository state.
- No release or milestone identifies a known-good daily-driver baseline.
- GitHub Projects were not verifiable through the connected API.

Issue #399 owns the correction. Workflow removal and protection changes require evidence that current consumers and required status contexts will not be broken.

## Supported live checks

```bash
./kitty context --agent
./kitty status
./kitty doctor --json
python3 scripts/openwebui_local.py verify
./kitty builder initiative doctor --json
```

Use explicit charge authorization before any verification path that invokes paid providers or GPU compute.
