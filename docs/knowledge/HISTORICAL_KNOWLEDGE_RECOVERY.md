---
type: methodology
title: "Historical Knowledge Recovery"
status: draft
owner: jacob
primary_purpose: Define the methodology for converting Kitty's historical artifacts into durable organizational knowledge
derives_from:
  - docs/VISION.md
  - docs/CONSTITUTION.md
  - docs/knowledge/KNOWLEDGE_MODEL.md
review_cycle: quarterly
---

# Historical Knowledge Recovery

## 1. Purpose

Every engineering organization possesses two forms of knowledge. **Ratified Knowledge** — reviewed, accepted, integrated (merged PRs, ADRs, architecture, postmortems). **Latent Knowledge** — exists but never formally captured (planning conversations, design discussions, AI chat logs, implementation attempts, abandoned experiments, review discussions, debugging sessions). These sources often contain the highest-value engineering insight. They are also the least trustworthy. Historical Knowledge Recovery exists to convert latent knowledge into ratified organizational knowledge.

## 2. Philosophy

The objective is not to archive conversations or summarize chats. The objective is to discover reusable engineering judgment hidden within historical work. Kitty should mine experience. Not preserve transcripts.

## 3. Guiding Principles

**Evidence Before Promotion** — Historical material is evidence, not truth. No historical statement becomes doctrine merely because it exists.
**Distill, Don't Preserve** — Conversation is transient. Judgment is durable.
**Human Ratification** — Recovered knowledge is always a candidate. Promotion requires review.
**Preserve Context** — Recovered knowledge should reference source, date, confidence, and supporting evidence.

## 4. Sources

Repository (Git history, commits, branches, PRs, code reviews, issues), Documentation (ADRs, planning documents, research, architecture, handoff notes), Conversations (AI chats, planning sessions, design discussions, implementation reviews), Runtime Evidence (Builder receipts, execution logs, verification reports, benchmarks, incidents).

## 5. Recovery Pipeline

Historical Artifact → Evidence Extraction → Observations → Candidate Findings → Knowledge Candidate → Human Review → Ratified Knowledge → Doctrine/ADR/Standard (optional). No stage may be skipped.

## 6. Extraction Targets

Architectural Decisions (what was decided, why, what alternatives existed), Engineering Patterns (recurring strategies, successful workflows), Anti-Patterns (repeated failures, misunderstandings, drift), Automation Opportunities (repeated manual work), Personal Workflow Insights (activation barriers, effective planning styles).

## 7. Anti-Goals

Historical Recovery is not intended to preserve every conversation, summarize every chat, create a searchable transcript archive, replace documentation, or generate doctrine automatically. Its purpose is to transform experience into reusable organizational capability.

## 8. Long-Term Vision

No valuable engineering lesson should need to be learned twice.
