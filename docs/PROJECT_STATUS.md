# Project Status

**Repository evidence verified:** 2026-08-04 through `main` `6f6966568a8d84125896472fc0c58752b4efb919`, plus this documentation-only reconciliation in PR #404.

This file is a dated evidence summary, not a live runtime dashboard. Use Git/GitHub for repository state, supported probes for local services, and Builder's supported database/API/CLI for execution state.

## Current architecture

- Kitty Gateway is the product authority for conversation behavior, memory/context, projects, tools, Tutor, provider policy, and user-facing workflows.
- Open WebUI is the accepted replaceable local daily-driver shell under ADR 0027.
- The custom `kitty-chat` client remains a loopback-only fallback and development surface.
- KittyBuilder is the separate execution organization and engineering control plane. GitHub issue comments are no longer a command queue.

## What's shipped

- PR #400 restored native OpenRouter model IDs and returned deterministic pytest to green.
- PR #401 repaired private-repository PR diff retrieval for Agent Review.
- PR #402 removed unauthenticated all-interface `kitty-chat` listeners, enforced loopback binding, and completed issue #158.
- PR #403 upgraded `pydantic-settings` to 2.14.2, outside the GHSA-4xgf-cpjx-pc3j affected range.
- PR #405 removed age-based stale auto-closure and added the complete 51-record Actions ledger without changing current RunPod/image workflows.
- Issues #127, #158, #160, #161, and #381 are closed with evidence or explicit supersession comments.
- Current CI includes pytest, lint, typecheck, hygiene, Kitty Chat tests/build, and browser smoke; all passed on the merged maintenance/security heads.
- ADR 0027 exists on `main` and defines the Open WebUI shell boundary.
- Personal image history remains unchanged by explicit owner decision.

## Active work

The one approved mission is [`ACTIVE_MISSION.md`](ACTIVE_MISSION.md): establish a trustworthy daily-driver baseline before broader expansion.

Immediate work:

1. merge this authority/documentation reconciliation in #404 after current CI;
2. apply the #399 admin/API mutation bundle when a capable interface is available: disable orphaned registry records, enable enforceable default-branch rules, and enable security alerts;
3. prove the local Open WebUI clean-start/chat/persistence/restart path;
4. complete one real #270 phone/PWA continuity loop.

Preserved but not current execution:

- #391 contains useful PAA alignment documentation but requires rebase and revalidation;
- #396 contains valuable model-policy, image-contract, and Builder-effectiveness work but is too broad to merge as one runtime-unproven unit;
- #316, #317, and #320 are independent dependency updates requiring separate current-CI review.

## Known unknowns

Repository evidence does not prove:

- Jacob's current local service, launchd, credential, quota, or provider state;
- that Open WebUI completes a real streamed chat and persistence/restart loop on Jacob's Mac today;
- **Builder investigation:** current local initiatives, packets, attempts, leases, and budgets remain unverified through GitHub;
- the real-phone timed-return and deduplication evidence required by #270;
- paid image-generation quality, likeness, cost, or cleanup state.

Unknown is not success and must not be presented as failure without evidence.

## Governance gaps

- The default-branch ruleset remains disabled.
- GitHub still reports 51 active workflow registry records, but current `main` contains 11 workflow YAML files after #405; four records are GitHub-managed and 35 are registry-only historical entries.
- Dependabot security alerts remain disabled through the accessible repository state.
- No release or milestone identifies a known-good daily-driver baseline.
- GitHub Projects were not verifiable through the connected API.

Issue #399 owns the remaining correction. The exact workflow IDs and recommended rules are in [`audit/GITHUB_WORKFLOW_LEDGER_2026-08-04.md`](audit/GITHUB_WORKFLOW_LEDGER_2026-08-04.md).

## Supported live checks

```bash
./kitty context --agent
./kitty status
./kitty doctor --json
python3 scripts/openwebui_local.py verify
./kitty builder initiative doctor --json
```

Use explicit charge authorization before any verification path that invokes paid providers or GPU compute.
