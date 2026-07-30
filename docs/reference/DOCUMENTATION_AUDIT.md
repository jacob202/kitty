# Documentation Audit

**Date:** 2026-07-30
**Inspected against:** `origin/main` at `fb6a0b7`
**Purpose:** classify every significant documentation file by status so cleanup can proceed safely.

## Classification key

| Status | Meaning |
|---|---|
| **Canonical** | Authoritative truth per `docs/AUTHORITY_MAP.md` |
| **Active operational** | Current, used in daily work, not canonical authority |
| **Historical** | Dated snapshot or past decision record, still referenced |
| **Generated** | Machine-produced, should not be edited manually |
| **Duplicate** | Content overlaps substantially with another current document |
| **Stale** | Contradicted by live repository, or contains outdated claims |
| **Archive candidate** | No longer current but preserved for reasoning |
| **Needs owner review** | Unclear status, or conflicts with another authority |

## Root-level documents

| File | Status | Evidence |
|---|---|---|
| `README.md` | Active operational | Current entry point. Some links and boundary descriptions need refresh (see this PR). |
| `AGENTS.md` | Canonical | Authoritative engineering doctrine per `AUTHORITY_MAP.md`. Current. |
| `CLAUDE.md` | Active operational | Claude Code instructions. Current. |
| `CODEX.md` | Active operational | Codex instructions. Current. |
| `START_HERE.md` | Canonical | Cold-start bootloader. Current. |
| `CONTRIBUTING.md` | **Stale** | References `docs/STANDUP.md` (archived), `CLAUDE.md` as primary (AGENTS.md is now primary). Overlaps substantially with `AGENTS.md`. Says "Python 3.12 path at `/opt/homebrew/bin/python3.12`" (hardcoded). |
| `TASKS.md` | Historical | Explicitly superseded 2026-07-17. Retained as historical narrative. |
| `SKILL_REGISTRY.md` | Active operational | Skill inventory. Last verified 2026-07-21. Still referenced. |
| `Makefile` | Active operational | Dev commands. Current. |
| `pyproject.toml` | Active operational | Tool configuration only (ruff, mypy, coverage). Not a package definition. |
| `pytest.ini` | Active operational | Pytest configuration. Slightly overlaps with `pyproject.toml` coverage settings. Not harmful — normal pytest config pattern. |
| `requirements.txt` | Active operational | Python dependencies. |
| `repomix.config.json` | Active operational | AI context bundle config. |
| `opencode.jsonc` | Active operational | OpenCode configuration. |
| `.pre-commit-config.yaml` | Active operational | Pre-commit hooks. |

## docs/ — root (current authority)

| File | Status | Evidence |
|---|---|---|
| `docs/README.md` | Active operational | Docs index. Current, well-structured. |
| `docs/AUTHORITY_MAP.md` | Canonical | Routes each kind of truth to its owner. Current, ratified. |
| `docs/NORTH_STAR.md` | Canonical | Product purpose and life-first outcome. Current. |
| `docs/ARCHITECTURE.md` | Canonical | Current runnable system and boundaries. Updated 2026-07-17. |
| `docs/DECISIONS.md` | Canonical | Accepted ADR index. Current, 22 decisions. |
| `docs/ROADMAP.md` | Canonical | Sole active delivery sequence. Ratified 2026-07-26. |
| `docs/ACTIVE_MISSION.md` | Canonical | One approved current mission (KTF-001). Status: running. |
| `docs/PROJECT_STATUS.md` | Canonical | Verified shipped state at a stated commit. Verified 2026-07-28. |
| `docs/ALIGNMENT_MAP.md` | Canonical | Kitty/KittyBuilder layering and authority order. Ratified 2026-07-26. |
| `docs/CONSTITUTION.md` | Canonical | Engineering principles. Current. |
| `docs/FEATURE_REALITY_2026-07-28.md` | Canonical | Product-surface capability reality check. Current. |
| `docs/LEARNINGS.md` | Active operational | Durable lessons and candidate lessons. Active — lessons added periodically. |
| `docs/JOURNEY.md` | Active operational | Running log of problems, insights, and major events. Updated regularly. |
| `docs/BLUEPRINT.md` | Active operational | Product direction from 2026-07-11. Endorsed by ADR 0017. Still referenced by NORTH_STAR.md. |
| `docs/UX_RULES.md` | Active operational | Non-negotiable design disciplines. Current. |
| `docs/PLANS.md` | Active operational | Navigation/disposition index for planning documents. Updated 2026-07-28. |
| `docs/WORKFLOW.md` | Active operational | PR review workflow and agent coordination contract. Still referenced. |
| `docs/QUICK_CAPTURE.md` | Active operational | Quick capture documentation. Current. |
| `docs/SIRI_SHORTCUT.md` | Active operational | Siri Shortcut setup. Current. |
| `docs/CAMPAIGN_PLAYBOOK.md` | Active operational | Paid-model session to Builder initiative procedure. Current. |
| `docs/FREE_MODEL_PACKET_STANDARD.md` | Active operational | Free-model packet requirements. Ratified 2026-07-26. |
| `docs/FREE_WORKERS.md` | Active operational | Token-efficient delegation guide. Current. |
| `docs/KITTYBUILDER_QUICKSTART.md` | Active operational | Supported operator commands and safety rails. Current. |
| `docs/KITTYBUILDER_ORCA_SETUP.md` | Active operational | Orca worktree setup guide. Current. |
| `docs/CODEBASE_MAP.md` | Redirect | Now points to `docs/reference/CODEBASE_MAP.md`. Retained to avoid breaking links. |
| `docs/reference/CODEBASE_MAP.md` | Active operational | **New.** Authoritative repository map (created in this PR). |

## docs/ — dated analysis, plans, and history

| File | Status | Evidence |
|---|---|---|
| `docs/OPERATOR_STRATEGY.md` | **Archive candidate** | 918 lines, dated 2026-07-01. Product archaeology + 30-day plan. Significant content but its forward-looking recommendations are absorbed by ROADMAP.md and ACTIVE_MISSION.md. The architectural analysis portion is duplicated in ARCHITECTURE.md and ALIGNMENT_MAP.md. Large document with many claims that may not reflect current state. |
| `docs/KITTY_PRODUCT_ARCHITECTURE.md` | **Archive candidate** | 972 lines, dated 2026-07-10. "Definitive product architecture and execution plan." Very large. ADR 0017 amended the control plane boundary; ARCHITECTURE.md now owns the current runnable system. This document's execution plan was aspirational at the time; much has been built or superseded since. The architecture content is substantially duplicated by ARCHITECTURE.md + ALIGNMENT_MAP.md + ROADMAP.md. |
| `docs/SESSION_META_2026-07-24.md` | **Archive candidate** | 327 lines. Session meta-analysis from 2026-07-24. Feeds into INITIATIVES_OPTIMIZED_2026-07-24.md. Dated analysis — its recommendations have been absorbed or superseded. |
| `docs/INITIATIVES_OPTIMIZED_2026-07-24.md` | **Archive candidate** | 222 lines. Feature sequencing from 2026-07-24. Explicitly says it owns feature sequencing, but ADR 0020 making ROADMAP.md the sole canonical roadmap post-dates this file. Content is superseded by ROADMAP.md. |
| `docs/DECISION_REVIEW_2026-07-26.md` | Historical | Review of all ADRs against current repository. Completed — decisions now live in `adr/`. Worth keeping as a record of the review pass. |
| `docs/CONSTITUTION.md` | Canonical | Classified above. |
| `docs/BLUEPRINT.md` | Active operational | Classified above — still referenced by NORTH_STAR.md. |

## docs/ directories

### adr/
**Status:** Canonical. 22 architecture decision records. The definitive decision history and supersession chain. Each ADR is a single record. Index at `docs/adr/README.md`.

### archive/
**Status:** Historical (intentionally). 34 files. Contains superseded handoffs, old session plans, retired operating material, and historical reference files. Maintained with its own README. Not current instruction.

### retired/
**Status:** Historical (intentionally). 9 files. Retired operating material including old architecture docs, code audit snapshots, and superseded plans. Separate from archive — these are explicitly retired rather than archived.

### research/
**Status:** Active operational. 6 files. Research notes and studies. Includes architecture corrections, reliability reconciliations, and adaptation studies. Active — new research added as work progresses.

### plans/
**Status:** Active operational. 7 files. Candidate work, architecture audits, and implementation plans. Inputs to the roadmap, not authority. Current per `docs/PLANS.md`.

### planning/
**Status:** **Archive candidate.** 7 files. Legacy planning documents (agent prompts, feature maps, vision analysis, builder redesign). `docs/README.md` already says "legacy organization that should be migrated or archived when touched." No doc appears actively maintained. This PR touches them — recommended to archive.

### phases/
**Status:** **Archive candidate.** 12 files. Legacy phase planning (Companion Voice, Context Engineering, Desktop Slice, MemPalace, Storage Migration, Voice Corpus, Phase B/C/C3 plans). `docs/README.md` says "legacy organization that should be migrated or archived when touched." Historical phase documents for work that has been completed or superseded.

### packets/
**Status:** Active operational. 30 files. Scoped execution contracts and historical packet material. Includes audit, template, README, and delta records. Some packets are historical records of completed work; verify approval and freshness before use.

### initiatives/
**Status:** Active operational. 34 files. Initiative manifests (JSON and markdown), evidence files, verification scripts, and human-gate READMEs. Some completed (`builder-test-hardening-v1`, `chat-recovery-v1`), some current (`ktf-001-free-exec-v1`, `ktf-004-current-main-reliability-proof-v1`). Active work product.

### audit/
**Status:** Active operational. 2 files. Bounded audit findings (architecture honesty, backend-frontend gap). Current evidence.

### codemap/
**Status:** **Stale / archive candidate.** 6 files. Generated/stale codemaps from a previous documentation generation pass. Their accuracy against the current tree has not been verified. If they reflect the current tree, they duplicate `docs/reference/CODEBASE_MAP.md` and `docs/ARCHITECTURE.md`. If stale, they are misleading.

### reference/
**Status:** Active operational. Now contains `CODEBASE_MAP.md` (new, this PR), `DOCUMENTATION_AUDIT.md` (new, this PR), plus existing `aider-repomap-study.md` and `hatchet-patterns.md`.

### examples/
**Status:** Active operational. 1 file: `kitty_alpha_initiative.example.json`. Template for initiative manifests.

### superpowers/
**Status:** Unknown. Contains `plans/` and `specs/` subdirectories. Not inspected in depth. Likely legacy planning.

### recon/
**Status:** Not inspected. May contain reconnaissance or research findings.

## docs/ — specific to review

| File | Status | Evidence |
|---|---|---|
| `docs/CODEBASE_MAP.md` | **Redirect** | Updated in this PR to point to `docs/reference/CODEBASE_MAP.md`. |
| `docs/codemap/` | **Archive candidate** | 6 generated docs. Unverified accuracy against current tree. Likely stale since repo has changed significantly. Recommend: verify or archive. |
| `docs/planning/` | **Archive candidate** | Per `docs/README.md`, already marked for migration/archival. This PR touches them; archiving is appropriate. |
| `docs/phases/` | **Archive candidate** | Per `docs/README.md`, already marked for migration/archival. Historical phase documents. |
| `docs/OPERATOR_STRATEGY.md` | **Archive candidate** | Very large (918 lines). Superseded by ROADMAP.md + ARCHITECTURE.md + ALIGNMENT_MAP.md. Contains architectural archaeology that's now in canonical docs. |
| `docs/KITTY_PRODUCT_ARCHITECTURE.md` | **Archive candidate** | Very large (972 lines). ADR 0017 amended the boundary; ARCHITECTURE.md owns current state. Significant duplication. |
| `docs/SESSION_META_2026-07-24.md` | **Archive candidate** | Dated session analysis. Absorbed or superseded. |
| `docs/INITIATIVES_OPTIMIZED_2026-07-24.md` | **Archive candidate** | Claims feature sequencing authority that ADR 0020 gives to ROADMAP.md. |
| `CONTRIBUTING.md` | **Stale** | References archived `docs/STANDUP.md`, hardcodes Python path, overlaps with AGENTS.md. Recommend: update or retire. |
| `docs/superpowers/` | **Needs owner review** | Not inspected. Unknown content. |

## Summary

| Classification | Count |
|---|---|
| Canonical | 12 |
| Active operational | 28 |
| Historical | 3 (intentionally retained) |
| Archive candidate | 10 (files/directories recommended for archival) |
| Stale | 2 (`CONTRIBUTING.md`, `docs/codemap/`) |
| Needs owner review | 1 (`docs/superpowers/`) |
| Redirect | 1 (`docs/CODEBASE_MAP.md`) |

## Recommended dispositions

1. **Archive now (safe, clear-cut):** `docs/planning/`, `docs/phases/` — already marked as legacy by `docs/README.md`.
2. **Archive after owner confirms:** `docs/OPERATOR_STRATEGY.md`, `docs/KITTY_PRODUCT_ARCHITECTURE.md`, `docs/SESSION_META_2026-07-24.md`, `docs/INITIATIVES_OPTIMIZED_2026-07-24.md` — large documents superseded by canonical docs.
3. **Verify or archive:** `docs/codemap/` — check accuracy, then either update or archive.
4. **Update or retire:** `CONTRIBUTING.md` — fix stale references or fold into AGENTS.md.
5. **Investigate:** `docs/superpowers/` — check content and classify.

**This audit does not move or delete any files.** It provides the evidence needed for later, safe cleanup.
