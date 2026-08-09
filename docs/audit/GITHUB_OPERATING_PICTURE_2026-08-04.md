# GitHub Operating Picture — 2026-08-04

**Repository baseline inspected:** `main` through `c266b13c0c694929c728a3f3861187f56229dbac`  
**Purpose:** dated evidence and maintenance record. Accepted ADRs, current Git/GitHub state, and supported runtime probes remain authoritative.

## Current architecture

- Kitty Gateway is the product authority for conversation behavior, context, memory, projects, tools, Tutor, provider policy, and user-facing workflows.
- KittyBuilder is the separate engineering execution control plane for Missions, queues, workers, attempts, leases, retries, validation, reviews, budgets, evidence, and PR publication.
- ADR 0027 authorizes pinned stock Open WebUI as the replaceable local daily-driver shell.
- The custom Next.js `kitty-chat` client is retained as a loopback-only fallback and development surface.
- Daily reliability and completed user workflows outrank speculative architecture.

## Changes completed

- Closed #160 and #161 after matching acceptance criteria to merged code and tests.
- Closed #381 as superseded by ADR 0027 and merged Open WebUI work in #384/#393.
- Closed #127 as a live command queue; Builder database/API/CLI state is execution authority.
- Merged #400, restoring native OpenRouter model IDs and repairing deterministic pytest.
- Merged #401, fixing PR Agent Review diff retrieval for this private repository.
- Merged #402, removing unauthenticated all-interface `kitty-chat` listener commands, enforcing loopback binding, and completing #158.
- Opened #399 for the 51-workflow ledger and enforceable branch-protection correction.
- Replaced the stale custom-UI mission, July status snapshot, and historical roadmap pile with a short current authority stack in #398.
- Recreated the stale Dependabot security update as isolated current-main PR #403 after the bot branch auto-closed during refresh.

## Explicit image-history decision

Previously removed personal images remain in Git history. Jacob explicitly chose not to rewrite that history. This maintenance pass does not alter, purge, enumerate, or otherwise touch it.

## Pull-request disposition

| PR | Disposition |
|---|---|
| #403 | Isolated `pydantic-settings` security patch; merge after current CI. |
| #316 | Uvicorn behavior change; review independently against current runtime. |
| #317 | Filelock update; review independently after current CI. |
| #320 | Large Anthropic SDK jump; require compatibility review and current CI. |
| #391 | Preserve and rebase the PAA matrix/ADR; revalidate every claim. |
| #396 | Preserve unique work but split model policy, image contracts, and Builder effectiveness into separate proven slices. |
| #398 | Current authority and documentation reconciliation; merge after current CI. |

## Remaining high-impact work

1. Merge #403 after all deterministic gates pass.
2. Prove the supported Open WebUI clean-start, real chat, attribution, persistence, restart, and failure-recovery path on Jacob's Mac.
3. Complete one real #270 phone/PWA return loop with restart and deduplication evidence.
4. Finish #399's workflow ledger and exact branch-protection proposal.
5. Retire only conclusively obsolete one-shot workflows without touching image/RunPod lanes or useful recovery tools.
6. Preserve and disposition unique work in #391, #396, and uncertain branches without deleting by age alone.

## Governance facts

- The accessible default-branch ruleset is disabled.
- Fifty-one Actions workflows remain active, including one-shot diagnostics and overlapping recovery generations.
- Dependabot security alerts remain disabled through the accessible repository state.
- No release or milestone identifies a known-good daily-driver baseline.
- GitHub Projects were not verifiable through the connected API.

## Branch handling

No image-related or uncertain branch was deleted. Two branches previously showed zero unique commits and remain safe deletion candidates, but the connected GitHub actions do not expose branch-ref deletion. They were left intact rather than misreported as deleted.

## Current priority order

1. Green and secure repository baseline.
2. One authoritative operating picture.
3. Verified Open WebUI daily-driver operation.
4. One real end-to-end continuity loop.
5. Enforceable repository governance.
6. Only then broader product, image, architecture, or research expansion.
