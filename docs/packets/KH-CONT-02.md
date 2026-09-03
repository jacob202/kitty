# KH-CONT-02 — GAR becomes the only mutable interactive continuity writer

**Initiative:** none — deliberately interactive  
**Owner:** ChatGPT/Codex interactive lane after fresh collision check  
**Base authored against:** `origin/main` `70c15583a6afa4aac9a6f6eb11abf840afa377a4`  
**Depends on:** KH-CONT-01  
**Status:** packet only — no implementation/runtime mutation performed

## Why there is no Builder manifest
This packet requires Node-only frontend verification, `.claude` compatibility-file mutation, security-sensitive live network configuration, or a combination that Builder's current packet runner cannot prove safely. Per `PACKET_STANDARD.md` F9/authority rules, it stays interactive rather than carrying fake Builder gates.

## What Jacob can do after this
Jacob can finish a Kitty session with one validated GAR handoff instead of also rewriting stale `.claude/STATE.md`/`HANDOFF.md` and carrying old recommendations forward.

## Verified finding
Current main already supports GAR-first receipts and posts the final room handoff after validation, but `.agents/skills/session-end/SKILL.md` still writes legacy HANDOFF/STATE snapshots and `scripts/session_end_survey.sh` still parses carried recommendations from STATE. `docs/packets/README.md` and other current operator docs still teach checkpoint reads.

## Intended scope
- `.agents/skills/session-end/SKILL.md`
- `scripts/session_end_survey.sh`
- `docs/reference/CONTEXT_ENGINEERING.md`
- `docs/packets/README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `START_HERE.md`
- `docs/AUTHORITY_MAP.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `tests/test_session_end_audit.py`
- `tests/test_gar_continuity_migration.py`


## Plan / hardened direction
1. Treat the existing continuity archival implementation plan as authority; do not redesign GAR.
2. Remove live session-end writes to both `.claude` checkpoint files and remove STATE recommendation carry-forward. The last continuity mutation remains the already-validated GAR handoff/result.
3. Update active docs/bootloaders/packet README so interactive continuation is unread direct inbox + assignment scope; Builder workers continue to use Builder context, not GAR as a queue.
4. Ratify the authority split in current authority/architecture docs: GAR mutable continuity, Git stable architecture/mission, Builder execution, #490 interactive ownership, GitHub publication.
5. Preserve historical audits/plans/ADRs without bulk-editing old references.
6. Do not delete the checkpoint files yet; KH-CONT-03 owns archival/deletion after no-legacy cold-start proof.


## Acceptance criteria
1. Session-end no longer writes `.claude/STATE.md` or `.claude/HANDOFF.md`.
2. Session-end survey no longer reads carried recommendations/next action from legacy STATE.
3. Active boot/docs no longer instruct agents to use checkpoint files when GAR is available.
4. The final GAR handoff is still posted only after final Git/validation truth is known.
5. Builder/roadmap/#490 authorities remain explicit and GAR is not described as a task queue/backlog.
6. Historical docs remain historical evidence instead of being rewritten wholesale.


## Verification
- `python -m pytest -q tests/test_session_end_audit.py tests/test_gar_continuity_migration.py`
- Run session-end in a disposable worktree and prove neither checkpoint file changes while a scoped GAR handoff is posted
- Cold-start with GAR available and legacy files intentionally stale; continuation must come from GAR scope.


The implementation must demonstrate a RED reproduction or measured baseline before production edits, then exact-head GREEN evidence. User-facing changes require desktop + iPhone-class acceptance and an independent reviewer who did not implement the change.

## Stop condition
If an active noninteractive/Builder runtime still requires either checkpoint file as execution authority, stop and remove that reader in a separately scoped compatibility fix before retiring writers.

## Recovery / authority guard
No packet here authorizes paid provider calls, credential changes, push/PR/merge, destructive data operations, or edits to canonical while another lane owns the path. Re-read `workspace_global`, GitHub #490, current PRs/worktrees, and Builder state immediately before implementation. UNKNOWN remains UNKNOWN.
