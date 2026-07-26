# Decisions

**Date:** 2026-07-26
**Status:** Index. Each durable decision lives in `docs/adr/` as a one-record-per-file ADR.

The full index is in [`docs/adr/README.md`](adr/README.md). Historical detail
that has not been promoted to a per-decision ADR remains in
[`docs/retired/DECISIONS_AND_ROADMAP.md`](retired/DECISIONS_AND_ROADMAP.md).

## Quick reference

| ID  | Title                                               | ADR                                                         |
| --- | --------------------------------------------------- | ----------------------------------------------------------- |
| D1  | Local-First Single User                             | [0002](adr/0002-local-first-single-user.md)                 |
| D2  | Gateway Is The Product                              | [0003](adr/0003-gateway-is-the-product.md)                  |
| D3  | memory_graph Owns Context Reads                     | [0004](adr/0004-memory-graph-owns-context-reads.md)         |
| D4  | Keep Inbox JSONL For Capture                        | [0005](adr/0005-keep-inbox-jsonl-for-capture.md)            |
| D5  | Phase B Is Consolidation — fulfilled/historical     | [0006](adr/0006-phase-b-is-consolidation.md)                |
| D6  | Borrow Patterns, Not Random Complexity              | [0007](adr/0007-borrow-patterns-not-random-complexity.md)   |
| D7  | StorageRouter Is A Thin Write-Side Seam, Not A Port | [0008](adr/0008-storage-router-thin-write-seam.md)          |
| D8  | Lint Is High-Signal Only; E501 Not Enforced         | [0009](adr/0009-lint-high-signal-only-e501-not-enforced.md) |
| D9  | Kitty Is A Personal Operating Layer — amended       | [0010](adr/0010-kitty-is-personal-operating-layer.md)       |
| D10 | Privacy Boundary In The LLM Router                  | [0011](adr/0011-privacy-boundary-in-llm-router.md)           |
| D11 | Mail Connector Uses The Gmail API, Read-Only        | [0012](adr/0012-mail-connector-gmail-readonly.md)           |
| D12 | Phone-First Delivery And The Move-In Bar — amended  | [0013](adr/0013-phone-first-delivery-move-in-bar.md)        |
| D13 | Magic Kitty: Cross-Project Insight                  | [0014](adr/0014-magic-kitty-cross-project-insight.md)       |
| D14 | Resume Loop Is The Product; Builder Boundary — amended | [0015](adr/0015-resume-loop-and-builder-boundary.md)     |
| D15 | Life-First Ordering                                 | [0016](adr/0016-life-first-ordering.md)                     |
| D16 | Kitty → Mission → KittyBuilder Control Plane — amended | [0017](adr/0017-kitty-mission-builder-control-plane.md)  |
| D17 | Evidence-Gated Auto-Merge — amended                 | [0018](adr/0018-builder-campaign-auto-merge.md)              |
| D18 | Audit-Harvest Ratifications                         | [0019](adr/0019-audit-harvest-ratifications.md)              |
| D19 | One Canonical Roadmap And Planning Ownership        | [0020](adr/0020-one-canonical-roadmap.md)                    |
| D20 | Proactive Builder Execution And Model Policy        | [0021](adr/0021-proactive-builder-execution.md)              |
| D21 | Session-End Carry-Forward Lives In The Checkpoint   | [0022](adr/0022-session-end-carry-forward-recommendations.md) |

Supersession and amendment details live in the ADRs themselves. A plan, packet,
report, or chat statement does not become a durable decision merely by existing.
