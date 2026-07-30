# Kitty Documentation

This directory separates current authority from planning inputs, evidence, and history. Existing does not mean current.

## Current authority

| Document | Purpose |
|---|---|
| [`AUTHORITY_MAP.md`](AUTHORITY_MAP.md) | Routes each kind of truth to its owner |
| [`NORTH_STAR.md`](NORTH_STAR.md) | Product purpose and life-first outcome |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Current runnable system and boundaries |
| [`DECISIONS.md`](DECISIONS.md) | Accepted decisions and ADR routing |
| [`ROADMAP.md`](ROADMAP.md) | Sole active delivery sequence |
| [`PROJECT_STATUS.md`](PROJECT_STATUS.md) | Verified shipped state at a stated commit |
| [`ACTIVE_MISSION.md`](ACTIVE_MISSION.md) | One approved current mission |
| [`FEATURE_REALITY_2026-07-28.md`](FEATURE_REALITY_2026-07-28.md) | Product-surface reality check |
| [`CODEBASE_MAP.md`](CODEBASE_MAP.md) | Human- and AI-readable repository map |

## Supporting material

- `adr/` — durable architectural decisions.
- `plans/` — candidate work, implementation plans, research, and preserved planning inputs. These do not override the roadmap unless explicitly absorbed.
- `packets/` — scoped execution contracts and historical packet material; verify approval and freshness before use.
- `audit/` — bounded findings and evidence.
- `reference/` — reusable technical references.
- `reference/VIBE_CODER_WORKFLOW.md` — session-first coding workflow scaffold and checklist.
- `phases/` and `planning/` — legacy organization that should be migrated or archived when touched.

## Historical material

`archive/` contains superseded documents, old handoffs, completed session plans, and retired operating material. Archived content can preserve reasoning, but it is never current instruction.

## Reading order

For a cold start, use the canonical order in [`../START_HERE.md`](../START_HERE.md). Do not browse the directory alphabetically and infer authority from filenames or recency.

## Maintenance rule

When a document becomes obsolete:

1. extract any still-valid decision, learning, or evidence into its canonical owner;
2. move the original into `archive/` without rewriting its historical claims;
3. record why it moved in the archive index or a dated manifest;
4. repair inbound links and remove it from current navigation.
