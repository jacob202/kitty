# Architecture Decision Records

This directory holds the project's ADRs — one decision per file, numbered
sequentially. Each ADR records context, the durable decision, consequences, and
any supersession or amendment.

Use [`0000-template.md`](0000-template.md) when adding a new ADR.

## Index

| #    | Title                                                                                          | Status                         | Date       |
| ---- | ---------------------------------------------------------------------------------------------- | ------------------------------ | ---------- |
| 0001 | [db.py Is The SQLite Seam For App-State Stores](0001-db-scope.md)                              | Accepted                       | 2026-07-02 |
| 0002 | [Local-First Single User](0002-local-first-single-user.md)                                     | Accepted                       | 2026-07-02 |
| 0003 | [Gateway Is The Product](0003-gateway-is-the-product.md)                                       | Accepted                       | 2026-07-02 |
| 0004 | [memory_graph Owns Context Reads](0004-memory-graph-owns-context-reads.md)                      | Accepted                       | 2026-07-02 |
| 0005 | [Keep Inbox JSONL For Capture](0005-keep-inbox-jsonl-for-capture.md)                           | Accepted                       | 2026-07-02 |
| 0006 | [Phase B Is Consolidation](0006-phase-b-is-consolidation.md)                                   | Fulfilled / historical         | 2026-07-02 |
| 0007 | [Borrow Patterns, Not Random Complexity](0007-borrow-patterns-not-random-complexity.md)        | Accepted                       | 2026-07-02 |
| 0008 | [StorageRouter Is A Thin Write-Side Seam, Not A Port](0008-storage-router-thin-write-seam.md)  | Accepted                       | 2026-07-02 |
| 0009 | [Lint Is High-Signal Only; E501 Not Enforced](0009-lint-high-signal-only-e501-not-enforced.md) | Accepted                       | 2026-07-02 |
| 0010 | [Kitty Is A Personal Operating Layer](0010-kitty-is-personal-operating-layer.md)               | Accepted; amended 2026-07-26   | 2026-07-01 |
| 0011 | [Privacy Boundary In The LLM Router](0011-privacy-boundary-in-llm-router.md)                   | Superseded by 0022             | 2026-07-02 |
| 0012 | [Mail Connector Uses The Gmail API, Read-Only](0012-mail-connector-gmail-readonly.md)          | Accepted; local-only clause retired by 0022 | 2026-07-02 |
| 0013 | [Phone-First Delivery And The Move-In Bar](0013-phone-first-delivery-move-in-bar.md)           | Accepted; amended 2026-07-26   | 2026-07-04 |
| 0014 | [Magic Kitty: Cross-Project Insight](0014-magic-kitty-cross-project-insight.md)                | Accepted                       | 2026-07-05 |
| 0015 | [The Resume Loop Is The Product; Builder Boundary](0015-resume-loop-and-builder-boundary.md)   | Accepted; amended 2026-07-26   | 2026-07-11 |
| 0016 | [Life-First Ordering](0016-life-first-ordering.md)                                             | Accepted                       | 2026-07-11 |
| 0017 | [Kitty → Mission → KittyBuilder Control-Plane Boundary](0017-kitty-mission-builder-control-plane.md) | Accepted; amended 2026-07-26 | 2026-07-17 |
| 0018 | [Evidence-Gated Auto-Merge for Builder Work](0018-builder-campaign-auto-merge.md)              | Accepted; amended 2026-07-26   | 2026-07-21 |
| 0019 | [Audit-Harvest Ratifications](0019-audit-harvest-ratifications.md)                             | Accepted                       | 2026-07-24 |
| 0020 | [One Canonical Roadmap and Planning Ownership](0020-one-canonical-roadmap.md)                  | Accepted                       | 2026-07-26 |
| 0021 | [Proactive Builder Execution and Model Policy](0021-proactive-builder-execution.md)            | Accepted                       | 2026-07-26 |
| 0022 | [Retire The D10 Local-Only Privacy Boundary](0022-retire-privacy-boundary.md)                  | Accepted                       | 2026-07-27 |
| 0023 | [Session-End Recommendations Carry Forward In The Checkpoint](0023-session-end-carry-forward-recommendations.md) | Accepted | 2026-07-26 |
| 0024 | [KittyBuilder Has an Independent Operator Application](0024-independent-kittybuilder-operator-application.md) | Accepted | 2026-08-01 |
| 0025 | [Session Learning Without a Second Backlog](0025-session-learning-without-a-second-backlog.md) | Accepted; amended 2026-08-01 | 2026-08-01 |
| 0026 | [Measured KB Effectiveness and Single Execution Ownership](0026-measured-kb-effectiveness-and-execution-ownership.md) | Accepted | 2026-08-01 |
| 0027 | [Open WebUI May Serve As Kitty's Replaceable Daily-Driver Shell](0027-open-webui-shell-boundary.md) | Accepted | 2026-08-02 |
| 0028 | [Commodity Software Precedence Over Custom Code](0028-commodity-software-precedence.md)        | Accepted                       | 2026-08-05 |
| 0029 | [Capability Manifest Is the Single Source of Runtime Truth](0029-capability-manifest-single-truth.md) | Accepted | 2026-08-05 |
| 0030 | [Repository Simplification Is a Strategic Priority](0030-repository-simplification-strategic-priority.md) | Accepted | 2026-08-05 |
| 0031 | [Architecture Migration to Open Brain/Ringer/Open Engine Is Deferred](0031-architecture-migration-deferred.md) | Accepted | 2026-08-05 |
| 0032 | [Evidence-Backed Claims — No Fabricated Success](0032-evidence-backed-claims.md)               | Accepted                       | 2026-08-05 |
| 0033 | [Open WebUI Shell Integration Boundary](0033-open-webui-shell-boundary.md)                     | Accepted                       | 2026-08-05 |
| 0034 | [Memory Policy Is a Kitty Concern — Storage Remains an Open Decision](0034-memory-policy-vs-storage.md) | Accepted | 2026-08-05 |
| 0035 | [Browser-Verified Evidence Required for UI Claims](0035-browser-verified-evidence.md)          | Accepted                       | 2026-08-05 |
| 0036 | [Builder Infrastructure Preserved — Refactored for Extraction Readiness](0036-builder-infrastructure-refactor.md) | Accepted | 2026-08-05 |

Historical decision detail remains in
[`docs/retired/DECISIONS_AND_ROADMAP.md`](../retired/DECISIONS_AND_ROADMAP.md).
