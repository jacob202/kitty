# ADR 0043 — Suspend Builder And GAR As Defaults

**Status:** Accepted — operational suspension experiment
**Date:** 2026-09-22

## Context

Builder and the Global Agent Room (GAR) solved real execution, recovery, and
coordination problems. They also accumulated mandatory startup, recall,
closeout, supervision, and coordination behavior whose current operating cost
exceeds its demonstrated marginal value.

This decision is deliberately narrower than retiring Builder, GAR, or Kitty.
The systems and their historical evidence remain preserved.

## Decision

1. **Builder is suspended as Kitty's default executor.** Normal interactive
   work does not schedule, supervise, drain, repair, or depend on Builder.
   Builder may still be inspected or run when Jacob explicitly requests
   Builder work, rollback, or compatibility testing.
2. **GAR is suspended as mandatory lifecycle and recall infrastructure.**
   Normal startup, continuation, handoff, and completion do not require room
   briefing, room posts, GAR receipts, SessionEnd outboxes, or GAR state.
3. **Ordinary continuity starts from the current assignment plus live
   Git/GitHub/runtime evidence.** Legacy `.claude/STATE.md` and
   `.claude/HANDOFF.md` remain historical compatibility snapshots only.
4. **Interactive mutation ownership uses the smallest local mechanism that
   works.** `scripts/work_claim.py` stores explicit path claims under the Git
   common directory shared by linked worktrees. Claims are local, expiring,
   atomic, and do not introduce a service, database, daemon, or network
   protocol.
5. **Remote publication protection remains GitHub-owned.** Existing PR,
   required-check, review-thread, deletion, and non-fast-forward rules remain
   the publication safety boundary.
6. **Non-safety completion ceremony is suspended.** The Build-It Stop
   completion blocker and automatic session-end bookkeeping are not part of
   normal completion. Safety hooks and outcome-level verification remain.

## Effect On Earlier Decisions

This ADR is a temporary operational amendment, not a historical rewrite.

- ADR 0017 remains the Builder control-plane contract **when Builder is
  explicitly invoked**; it no longer makes Builder the ordinary execution
  route.
- ADR 0018 remains applicable to explicitly authorized Builder publication;
  it does not activate Builder by default.
- ADR 0021's proactive/default Builder execution is suspended for the duration
  of this experiment.
- ADR 0023's automatic session-end carry-forward behavior is suspended for
  ordinary sessions.
- ADR 0024's independent Builder operator surface is preserved compatibility
  infrastructure, not a required daily control surface.
- ADR 0026's single-owner requirement remains in force. For ordinary
  interactive linked-worktree changes, ownership is represented by the local
  work claim rather than mandatory Builder/GAR state.
- ADRs 0036 and 0038 continue to require preservation of Builder code, data,
  and recovery semantics; preservation does not imply automatic activation.

Later accepted ADRs win if any older text conflicts with this suspension.

## Scope Boundaries

This ADR does **not**:

- amend the Constitution;
- retire Kitty as a product or platform;
- delete Builder or GAR code/data/history;
- adopt Jacob Core;
- redesign memory, Discord, providers, UI, or the broader Kitty architecture;
- make GAR or Builder incapable of explicit use;
- decide Kitty's future product thesis.

The broader retirement proposal at local commit `21951c5` remains historical
evidence and is not adopted by this ADR.

## Validation And Exit

The suspension is successful only if normal work can start, execute, coordinate,
and finish without mandatory Builder/GAR machinery while preserving safe
publication and practical concurrency.

The local ownership substitute must demonstrate:

- visible rejection of overlapping scopes;
- legitimate non-overlapping parallel work;
- atomic scope growth without releasing existing ownership;
- visible stale ownership and bounded expiry;
- safe recovery after an unclean owner stop;
- staged-path enforcement, including file type changes and initial commits.

If these properties fail, add only the smallest behavior demonstrated missing.
Do not recreate GAR by default.

Rollback or further retirement requires a separate explicit decision. Re-enabling
Builder requires restoring its launchd activation and any intentionally suspended
hooks; preserved code/history alone does not reactivate it.
