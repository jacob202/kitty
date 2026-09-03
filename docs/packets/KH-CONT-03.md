# KH-CONT-03 — Legacy checkpoint files are archived and absent from cold start

**Initiative:** none — deliberately interactive  
**Owner:** ChatGPT/Codex interactive lane after fresh collision check  
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`  
**Depends on:** KH-CONT-02  
**Status:** packet only — no implementation/runtime mutation performed

## Why there is no Builder manifest
This packet requires Node-only frontend verification, `.claude` compatibility-file mutation, security-sensitive live network configuration, or a combination that Builder's current packet runner cannot prove safely. Per `PACKET_STANDARD.md` F9/authority rules, it stays interactive rather than carrying fake Builder gates.

## What Jacob can do after this
Jacob can cold-start Kitty agents with `.claude/STATE.md` and `.claude/HANDOFF.md` physically absent and still recover the correct scoped continuation.

## Verified finding
The existing archival plan deliberately postponed deletion until GAR could prove deterministic scoped retrieval. After KH-CONT-01/02, keeping tracked stale checkpoint files would continue to create false confidence and doctor noise.

## Intended scope
- `.claude/STATE.md`
- `.claude/HANDOFF.md`
- `docs/archive/continuity/2026-09-03-legacy-checkpoints/`
- `gateway/context_receipt.py`
- `gateway/doctor.py`
- `scripts/check_continuity_state.py`
- `tests/test_cold_start_acceptance.py`
- `tests/test_doctor.py`
- `tests/test_gar_continuity_migration.py`


## Plan / hardened direction
1. Copy the final historical checkpoint contents into a dated archive with a README explaining supersession; preserve Git history as the ultimate record.
2. Delete the tracked live `.claude/STATE.md`/`HANDOFF.md` files.
3. Remove or demote doctor/continuity checks whose only purpose was checkpoint agreement; absence after migration is PASS/expected, not WARN.
4. Keep explicit legacy parsing only where a historical artifact reader genuinely needs it; it must not participate in current next-action selection.
5. Run no-legacy cold-start acceptance using `workspace_global` scoped handoff, Git/mission, Builder, and #490 authorities.
6. Search active non-historical docs/scripts/tests for live-path references and eliminate only current operational dependencies.


## Acceptance criteria
1. Both live checkpoint files are absent from the final tree and their last contents are archived with supersession context.
2. Cold-start acceptance succeeds with both files physically absent.
3. Doctor does not award PASS points for two stale files agreeing with each other and does not warn merely because retired files are absent.
4. No current next-action/recommendation path reads legacy checkpoints.
5. Historical evidence remains accessible through Git/archive without creating a second mutable continuity system.


## Verification
- `python -m pytest -q tests/test_cold_start_acceptance.py tests/test_doctor.py tests/test_gar_continuity_migration.py`
- Fresh detached-worktree cold start with no checkpoint files; scoped GAR handoff must be recovered
- Repository search proving remaining `.claude/STATE.md`/`HANDOFF.md` mentions are historical/archival only.


The implementation must demonstrate a RED reproduction or measured baseline before production edits, then exact-head GREEN evidence. User-facing changes require desktop + iPhone-class acceptance and an independent reviewer who did not implement the change.

## Stop condition
If the no-legacy cold-start cannot deterministically identify the assignment after KH-CONT-01/02, do not delete the files; fix scoped retrieval first.

## Recovery / authority guard
No packet here authorizes paid provider calls, credential changes, push/PR/merge, destructive data operations, or edits to canonical while another lane owns the path. Re-read `workspace_global`, GitHub #490, current PRs/worktrees, and Builder state immediately before implementation. UNKNOWN remains UNKNOWN.
