# Architecture Decision Records

One durable decision lives in each numbered file. Accepted ADRs govern until explicitly amended or superseded. Use [`0000-template.md`](0000-template.md) for new decisions.

| # | Decision | Status | Date |
|---|---|---|---|
| 0001 | [db.py is the SQLite seam](0001-db-scope.md) | Accepted | 2026-07-02 |
| 0002 | [Local-first single user](0002-local-first-single-user.md) | Accepted | 2026-07-02 |
| 0003 | [Gateway is the product](0003-gateway-is-the-product.md) | Accepted | 2026-07-02 |
| 0004 | [`memory_graph` owns context reads](0004-memory-graph-owns-context-reads.md) | Accepted | 2026-07-02 |
| 0005 | [Keep inbox JSONL for capture](0005-keep-inbox-jsonl-for-capture.md) | Accepted | 2026-07-02 |
| 0006 | [Phase B consolidation](0006-phase-b-is-consolidation.md) | Fulfilled / historical | 2026-07-02 |
| 0007 | [Borrow patterns, not random complexity](0007-borrow-patterns-not-random-complexity.md) | Accepted | 2026-07-02 |
| 0008 | [StorageRouter is a thin write seam](0008-storage-router-thin-write-seam.md) | Accepted | 2026-07-02 |
| 0009 | [Lint is high-signal only](0009-lint-high-signal-only-e501-not-enforced.md) | Accepted | 2026-07-02 |
| 0010 | [Kitty is a personal operating layer](0010-kitty-is-personal-operating-layer.md) | Accepted; amended | 2026-07-01 |
| 0011 | [Privacy boundary in the LLM router](0011-privacy-boundary-in-llm-router.md) | Superseded by 0022 | 2026-07-02 |
| 0012 | [Read-only Gmail connector](0012-mail-connector-gmail-readonly.md) | Accepted; amended | 2026-07-02 |
| 0013 | [Phone-first delivery and move-in bar](0013-phone-first-delivery-move-in-bar.md) | Accepted; amended | 2026-07-04 |
| 0014 | [Magic Kitty cross-project insight](0014-magic-kitty-cross-project-insight.md) | Accepted | 2026-07-05 |
| 0015 | [Resume loop and Builder boundary](0015-resume-loop-and-builder-boundary.md) | Accepted; amended | 2026-07-11 |
| 0016 | [Life-first ordering](0016-life-first-ordering.md) | Accepted | 2026-07-11 |
| 0017 | [Kitty → Mission → KittyBuilder boundary](0017-kitty-mission-builder-control-plane.md) | Accepted; amended | 2026-07-17 |
| 0018 | [Evidence-gated Builder auto-merge](0018-builder-campaign-auto-merge.md) | Accepted; amended | 2026-07-21 |
| 0019 | [Audit-harvest ratifications](0019-audit-harvest-ratifications.md) | Accepted | 2026-07-24 |
| 0020 | [One canonical roadmap](0020-one-canonical-roadmap.md) | Accepted | 2026-07-26 |
| 0021 | [Proactive Builder execution and model policy](0021-proactive-builder-execution.md) | Accepted | 2026-07-26 |
| 0022 | [Retire the local-only privacy boundary](0022-retire-privacy-boundary.md) | Accepted | 2026-07-27 |
| 0023 | [Session-end recommendations carry forward](0023-session-end-carry-forward-recommendations.md) | Accepted | 2026-07-26 |
| 0024 | [Independent KittyBuilder operator application](0024-independent-kittybuilder-operator-application.md) | Accepted | 2026-08-01 |
| 0025 | [Session learning without a second backlog](0025-session-learning-without-a-second-backlog.md) | Accepted; amended | 2026-08-01 |
| 0026 | [Measured KB effectiveness and single execution ownership](0026-measured-kb-effectiveness-and-execution-ownership.md) | Accepted | 2026-08-01 |
| 0027 | [Open WebUI is a replaceable daily-driver shell](0027-open-webui-shell-boundary.md) | Accepted | 2026-08-03 |

Historical combined decision material remains in [`../retired/DECISIONS_AND_ROADMAP.md`](../retired/DECISIONS_AND_ROADMAP.md).
