---
name: session-end
description: Compatibility-only closeout guidance. Normal Kitty work does not invoke this automatically.
---

# Session End — Suspended Compatibility Skill

Builder/GAR lifecycle closeout is suspended as of 2026-09-22.

Do not invoke this skill automatically. Normal work ends when the bounded
requested outcome has been verified, reported, and any local work claim can be
safely released.

If Jacob explicitly asks for `session end` or `wrap up`:

1. inspect live Git/worktree state;
2. state what is verified complete, incomplete, or blocked;
3. preserve exact commit/test/runtime evidence;
4. release this worktree claim only when no unfinished mutation still needs it;
5. report the next action only if work genuinely remains;
6. stop.

Do not post GAR handoffs, create lifecycle receipts, update workflow signals,
write KB-effectiveness records, or rewrite `.claude/STATE.md` /
`.claude/HANDOFF.md` as part of closeout.

Historical Builder/GAR/session-end data remains preserved for explicit audit or
rollback work.
