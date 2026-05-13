# Spec: Repo Cleanup And Archive Pruning

## Goal
To clean up the repository root and `docs/` folder by identifying, archiving, or deleting stale, generated, duplicate, and inactive files. This will improve system context efficiency and navigation for future work.

## Scope
### Allowed Files
- `docs/CLEANUP_CANDIDATES.md` (new/updated)
- `docs/archive/` (all files moved here)
- `docs/PHASE4_MERGE_GATE_RUN_*.md` (to be archived or deleted)
- `docs/AGENTCOMPANY_*.md` (to be reviewed for archiving)
- `docs/WORKSPACE_SEPARATION_*.md` (to be reviewed for archiving)

### Forbidden Files
- `src/`, `tests/`, `scripts/`, `garage-ui/`
- Any active routing, config, or execution file.
- Raw chat logs in `data/` unless explicitly approved.

## Implementation Plan
1.  **Identify:** Scan `docs/` for files with specific timestamps or operational artifacts that are no longer active (e.g., `PHASE4_MERGE_GATE_RUN_2026-04-30_*.md`).
2.  **Consolidate:** Move these files into `docs/archive/2026-04-30-phase4-runs/` to preserve history without cluttering the main docs folder.
3.  **Audit `docs/`:** Identify other outdated documents (like `WORKSPACE_SEPARATION_EXECUTION_REPORT_2026-04-29.md`) and archive them appropriately.
4.  **Update index:** Update **`docs/README.md`** (or append a cleanup report) detailing what moved/deleted so rollback paths stay discoverable.

## Acceptance Criteria
- `ls docs/` is significantly cleaner and easier to read.
- All Phase 4 merge gate runs are moved to a specific archive subfolder.
- No live system files or active documentation (like `AGENT_COORDINATION.md` or `HANDOFF.md`) are modified or moved.

## Validation
- `ls docs/` confirms removal of clutter.
- `ls docs/archive/` confirms files are preserved.
- `pytest tests/` continues to pass, ensuring no runtime files were touched.
