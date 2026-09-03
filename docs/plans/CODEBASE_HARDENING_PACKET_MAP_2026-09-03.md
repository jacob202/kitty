# Codebase Hardening Packet Map — 2026-09-03

**Review base:** `70c15583a6afa4aac9a6f6eb11abf840afa377a4`
**Status:** authored, not activated
**Authority:** packet execution still requires current Git/GitHub, Builder, `workspace_global`, and #490 checks.

## Goal
Convert the holistic codebase review into independently executable, evidence-first work without creating another mega-initiative or colliding with ONE KITTY. Each Builder packet has its own one-packet initiative manifest so it can be validated/activated independently. Frontend-only, legacy-continuity, and live-network work is explicitly interactive rather than pretending Builder can run Node or mutate security-sensitive runtime configuration safely.

## Ordering
| Priority | Packet | Owner | Cross-packet prerequisite | Why |
| --- | --- | --- | --- | --- |
| P0 | `KH-RUNTIME-01` | Builder | none | Runtime truth is prerequisite for trustworthy verification. |
| P0 | `KH-BODY-01` | Builder | none | Actual-byte request boundary; import depends on it. |
| P0 | `KH-VOICE-01` | Builder | none | Unauthenticated/unbounded WS + lost context. |
| P0 | `KH-BUILDER-SEC-01` | Builder | wait for current OK-ACTION-01/02 lane release | Close validation credential privilege gap. |
| P1 | `KH-IMPORT-01` | Builder | KH-BODY-01 | Stream imports; failures remain failures. |
| P1 | `KH-JSON-01` | Builder | none | Remove response rewriting from transport layer. |
| P1 | `KH-DEPS-PY-01` | Builder | none | Doctor detects active venv drift. |
| P1 | `KH-BUILDER-SEC-02` | Builder | KH-BUILDER-SEC-01 + queue compatibility inventory | Remove shell execution for new validation commands. |
| P1 | `KH-REMOTE-01` | Interactive | KH-RUNTIME-01 | Fix phone-access/security-model contradiction without weakening proxy. |
| P2 | `KH-ERRORS-01` | Interactive | KH-JSON-01 + KH-IMPORT-01 | Typed safe error core; targeted gateway.ts extraction. |
| P2 | `KH-ERRORS-02` | Interactive | KH-ERRORS-01 | Migrate remaining raw user-facing error consumers. |
| P2 | `KH-CONT-01` | Builder | none | Remaining GAR scoped-retrieval prerequisite. |
| P2 | `KH-CONT-02` | Interactive | KH-CONT-01 | Stop legacy checkpoint writers/read-carried recommendations. |
| P2 | `KH-CONT-03` | Interactive | KH-CONT-02 | Archive/delete checkpoint compatibility after cold-start proof. |
| P2 | `KH-DEPS-WEB-01` | Interactive | none | Resolve current high production dependency advisory without force. |
| P3 | `KH-PLUGIN-01` | Builder | none | Make existing plugin abstraction real or explicitly unsupported. |
| P3 | `KH-CAPABILITY-01` | Builder | KH-PLUGIN-01 | One derived capability health contract, no new store. |
| P3 | `KH-PERF-01` | Interactive | KH-ERRORS-01 + release shared ONE KITTY frontend paths | Event-driven invalidation with measured request reduction. |

## Deliberate non-packets
There is **no generic "split the big files" packet**. `PACKET_STANDARD.md` says an internal refactor with no observable outcome is a step, not a packet. Hotspot reduction is therefore attached to the seams that justify it: `KH-RUNTIME-01` centralizes one runtime probe, `KH-ERRORS-01` extracts the error client from `gateway.ts`, `KH-PERF-01` consolidates live invalidation, and plugin/capability work separates those authorities. Likewise, the review's boundary-test list is embedded into each relevant packet rather than creating a test-only backlog packet.

## Dedupe decisions
- `D1-tailnet-serve` is historical/not live in current Builder; `KH-REMOTE-01` revalidates and replaces its stale all-interface assumptions while preserving the intended authenticated-Tailscale direction.
- GAR archival work already landed `--skip-legacy-continuity` and final-handoff ordering. `KH-CONT-01/02/03` contain only the remaining scoped retrieval, writer retirement, and final archive/delete work from `docs/superpowers/plans/2026-09-01-global-agent-room-continuity-archival.md`.
- `KF-SESSION-01` owns the product-Home defect where developer checkpoints could appear as Jacob's day; the continuity packets do not recreate that Home work.
- Current `OK-ACTION-01` execution remains authoritative. Builder-security and shared frontend packets must not activate while it owns overlapping Builder/frontend seams.

## Activation rule
Do **not** apply all manifests at once. Activate one packet only after: (1) fresh main/review evidence still reproduces the finding; (2) #490/GAR/Builder collision scan is clear; (3) its predecessor is merged where listed; (4) the current worktree/base is refreshed; and (5) paid use, network mutation, or credentials have separate explicit authorization when required.

## Completion rule
A packet is not done because a worker says so. Require exact changed paths/SHA, Tier-1 commands, CI/Node evidence where applicable, service-on/service-off or failure-path proof, independent review, and Product Acceptance for user-visible changes. If evidence becomes unavailable, status is UNKNOWN—not inherited green.
