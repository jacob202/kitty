---
type: index
title: "Architecture Decision Records"
status: canonical
owner: jacob
primary_purpose: Index of all ADRs — one decision per file, numbered sequentially
derives_from:
  - docs/CONSTITUTION.md
review_cycle: as needed (updated when ADRs are added or superseded)
---

# Architecture Decision Records

This directory holds the project's ADRs — one decision per file,
numbered sequentially. Each ADR is short: **Context** (what prompted
it), **Decision** (what was chosen and why), **Consequences** (what
it rules out and what it commits to).

Use [`0000-template.md`](0000-template.md) when adding a new ADR.

## Index

| #    | Title                                                                                          | Status   | Date       |
| ---- | ---------------------------------------------------------------------------------------------- | -------- | ---------- |
| 0001 | [db.py Is The SQLite Seam For App-State Stores](0001-db-scope.md)                              | Accepted | 2026-07-02 |
| 0002 | [Local-First Single User](0002-local-first-single-user.md)                                     | Accepted | 2026-07-02 |
| 0003 | [Gateway Is The Product](0003-gateway-is-the-product.md)                                       | Accepted | 2026-07-02 |
| 0004 | [memory_graph Owns Context Reads](0004-memory-graph-owns-context-reads.md)                     | Accepted | 2026-07-02 |
| 0005 | [Keep Inbox JSONL For Capture](0005-keep-inbox-jsonl-for-capture.md)                           | Accepted | 2026-07-02 |
| 0006 | [Phase B Is Consolidation](0006-phase-b-is-consolidation.md)                                   | Accepted | 2026-07-02 |
| 0007 | [Borrow Patterns, Not Random Complexity](0007-borrow-patterns-not-random-complexity.md)        | Accepted | 2026-07-02 |
| 0008 | [StorageRouter Is A Thin Write-Side Seam, Not A Port](0008-storage-router-thin-write-seam.md)  | Accepted | 2026-07-02 |
| 0009 | [Lint Is High-Signal Only; E501 Not Enforced](0009-lint-high-signal-only-e501-not-enforced.md) | Accepted | 2026-07-02 |
| 0010 | [Kitty Is A Personal Operating Layer](0010-kitty-is-personal-operating-layer.md)               | Accepted | 2026-07-01 |
| 0011 | [Privacy Boundary In The LLM Router](0011-privacy-boundary-in-llm-router.md)                   | Accepted | 2026-07-02 |
| 0012 | [Mail Connector Uses The Gmail API, Read-Only](0012-mail-connector-gmail-readonly.md)          | Accepted | 2026-07-02 |
| 0013 | [Phone-First Delivery And The Move-In Bar](0013-phone-first-delivery-move-in-bar.md)           | Accepted | 2026-07-04 |
| 0014 | [Magic Kitty: Cross-Project Insight](0014-magic-kitty-cross-project-insight.md)                | Accepted | 2026-07-05 |
| 0015 | [The Resume Loop Is The Product; Builder Boundary](0015-resume-loop-and-builder-boundary.md)   | Accepted | 2026-07-11 |
| 0016 | [Life-First Ordering](0016-life-first-ordering.md)                                             | Accepted | 2026-07-11 |
| 0017 | [Kitty Is an Engineering Operating System](0017-kitty-is-engineering-operating-system.md)       | Accepted | 2026-07-14 |
| 0018 | [Documentation Is Architecture; Repository Governance Foundation](0018-documentation-as-architecture.md) | Accepted | 2026-07-14 |
| 0019 | [Knowledge Model Is a Foundational Prerequisite](0019-knowledge-model-prerequisite.md)          | Accepted | 2026-07-14 |

Historical decision detail remains in [`docs/retired/DECISIONS_AND_ROADMAP.md`](../retired/DECISIONS_AND_ROADMAP.md).
