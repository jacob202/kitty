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
| D26 | Open WebUI is a replaceable daily-driver shell | [0027](adr/0027-open-webui-shell-boundary.md) |

The full status/date index is in [`docs/adr/README.md`](adr/README.md). Older combined decision material remains historical in [`docs/retired/DECISIONS_AND_ROADMAP.md`](retired/DECISIONS_AND_ROADMAP.md).
