# Decisions

**Status:** Current index. Durable decisions live one-per-file in [`docs/adr/`](adr/).

A plan, issue, packet, report, metric, or chat statement does not become architecture merely by existing. Accepted ADRs govern until explicitly amended or superseded.

| ID | Decision | ADR |
|---|---|---|
| D1 | Local-first single user | [0002](adr/0002-local-first-single-user.md) |
| D2 | Gateway is the product | [0003](adr/0003-gateway-is-the-product.md) |
| D3 | `memory_graph` owns context reads | [0004](adr/0004-memory-graph-owns-context-reads.md) |
| D4 | Keep inbox JSONL for capture | [0005](adr/0005-keep-inbox-jsonl-for-capture.md) |
| D5 | Phase B consolidation — fulfilled/historical | [0006](adr/0006-phase-b-is-consolidation.md) |
| D6 | Borrow patterns, not random complexity | [0007](adr/0007-borrow-patterns-not-random-complexity.md) |
| D7 | StorageRouter is a thin write seam | [0008](adr/0008-storage-router-thin-write-seam.md) |
| D8 | Lint is high-signal only | [0009](adr/0009-lint-high-signal-only-e501-not-enforced.md) |
| D9 | Kitty is a personal operating layer | [0010](adr/0010-kitty-is-personal-operating-layer.md) |
| D10 | Privacy boundary in LLM router — superseded by D21 | [0011](adr/0011-privacy-boundary-in-llm-router.md) |
| D11 | Gmail connector is read-only | [0012](adr/0012-mail-connector-gmail-readonly.md) |
| D12 | Phone-first delivery and move-in bar | [0013](adr/0013-phone-first-delivery-move-in-bar.md) |
| D13 | Magic Kitty cross-project insight | [0014](adr/0014-magic-kitty-cross-project-insight.md) |
| D14 | Resume loop and Builder boundary | [0015](adr/0015-resume-loop-and-builder-boundary.md) |
| D15 | Life-first ordering | [0016](adr/0016-life-first-ordering.md) |
| D16 | Kitty → Mission → KittyBuilder boundary | [0017](adr/0017-kitty-mission-builder-control-plane.md) |
| D17 | Evidence-gated Builder auto-merge policy | [0018](adr/0018-builder-campaign-auto-merge.md) |
| D18 | Audit-harvest ratifications | [0019](adr/0019-audit-harvest-ratifications.md) |
| D19 | One canonical roadmap | [0020](adr/0020-one-canonical-roadmap.md) |
| D20 | Proactive Builder execution and model policy | [0021](adr/0021-proactive-builder-execution.md) |
| D21 | Retire the D10 local-only privacy boundary | [0022](adr/0022-retire-privacy-boundary.md) |
| D22 | Session-end recommendations carry forward in checkpoint | [0023](adr/0023-session-end-carry-forward-recommendations.md) |
| D23 | KittyBuilder has an independent operator application | [0024](adr/0024-independent-kittybuilder-operator-application.md) |
| D24 | Session learning without a second backlog | [0025](adr/0025-session-learning-without-a-second-backlog.md) |
| D25 | Measured KB effectiveness and single execution ownership | [0026](adr/0026-measured-kb-effectiveness-and-execution-ownership.md) |
| D26 | Open WebUI replaceable-shell boundary — product-surface role superseded by D38; compatibility/isolation boundary retained | [0027](adr/0027-open-webui-shell-boundary.md) |
| D27 | Commodity software precedes custom code | [0028](adr/0028-commodity-software-precedence.md) |
| D28 | Capability Manifest is the single source of runtime truth | [0029](adr/0029-capability-manifest-single-truth.md) |
| D29 | Repository simplification is a strategic priority | [0030](adr/0030-repository-simplification-strategic-priority.md) |
| D30 | Open Brain/Ringer/Open Engine migration is deferred | [0031](adr/0031-architecture-migration-deferred.md) |
| D31 | Evidence-backed claims — no fabricated success | [0032](adr/0032-evidence-backed-claims.md) |
| D32 | Open WebUI shell integration boundary is enforced in code | [0033](adr/0033-open-webui-shell-boundary.md) |
| D33 | Memory policy is a Kitty concern; storage remains open | [0034](adr/0034-memory-policy-vs-storage.md) |
| D34 | UI claims require browser-verified evidence | [0035](adr/0035-browser-verified-evidence.md) |
| D35 | Builder infrastructure is preserved, refactored for extraction readiness | [0036](adr/0036-builder-infrastructure-refactor.md) |
| D36 | PAA is Kitty's reference architecture and portability profile, not a replacement codebase | [0037](adr/0037-paa-reference-profile.md) |
| D37 | Builder crash recovery follows a durable recovery contract | [0038](adr/0038-builder-crash-recovery-durability.md) |
| D38 | Native Kitty owns the canonical product surface; Open WebUI is compatibility/reference software | [0039](adr/0039-kitty-native-product-surface.md) |
| D39 | Image Lab uses FLUX.2-first intent compilation and native references | [0040](adr/0040-image-lab-flux2-execution-architecture.md) |

The full status/date index is in [`docs/adr/README.md`](adr/README.md). Older combined decision material remains historical in [`docs/retired/DECISIONS_AND_ROADMAP.md`](retired/DECISIONS_AND_ROADMAP.md).
