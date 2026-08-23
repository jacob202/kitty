# KB payload — 2026-08-23 (scheduling session)

PR #616 owns `docs/session-notes/2026-08-23-kb-payload.md` for the same date.
This file is the scheduling session's separate payload.

`~/kb` was absent in this container, so these entries are staged here per
`.agents/skills/session-end/SKILL.md` step 4. Copy them into `~/kb/wiki/` and
append to `~/kb/INDEX.md` from a session running on the Mac.

Release check: `test -d ~/kb`

---

## wiki/2026-08-23-scheduled-sessions-have-no-guaranteed-mcp.md

**Source:** 2026-08-23 interactive session, Claude Code (session_01BBGNHiF82b1HDG849RkVT3)
**Date:** 2026-08-23
**Why it matters:** A scheduled Routine that assumes GitHub access will silently
produce a partial result instead of failing, and there is no HTTP escape hatch.
**Verified:** `create_trigger` returned "this trigger stores no MCP connectors,
so the sessions it fires will run without connector tools". A forced run
(`session_01RoYfbWhyoNNLXjHKTux1wi`, 11:30–11:35Z, $1.0765718, served
`claude-sonnet-5`) completed without creating its target issue. In the parent
session, `curl -H "Authorization: Bearer $GITHUB_TOKEN"
https://api.github.com/repos/jacob202/kitty/pulls` returned HTTP 403 with
`GitHub access is not enabled for this session`.

Sessions fired by a Routine cannot be assumed to hold `mcp__github__*` or the
claude-code-remote tools, and the ambient `GITHUB_TOKEN`/`GH_TOKEN` do not work
against `api.github.com` — the agent proxy rejects them. Git over HTTPS to the
session's own repo does work.

Compounding this: MCP servers drop and reconnect mid-session. Over roughly three
hours the `github` and `claude-code-remote` servers each disappeared and
returned several times, and a tool call made during a gap fails with
`No such tool available`. A capability probe that runs once, at session start,
will therefore misreport a transient disconnect as a permanent absence.

Rule: a scheduled prompt that depends on an MCP tool must re-probe via
ToolSearch after a wait before declaring a fallback, and must state in its
output which mode it ran in.

---

## wiki/2026-08-23-routine-model-cannot-be-changed-from-a-session.md

**Source:** 2026-08-23 interactive session, Claude Code
**Date:** 2026-08-23
**Why it matters:** A Routine created from a session inherits an expensive model
and cannot be made cheaper without the web UI, so cost has to be planned before
creation, not corrected after.
**Verified:** Six `update_trigger` calls carrying `model`
(`claude-haiku-4-5-20251001` and `claude-haiku-4-5`) each returned
`failed to update trigger: the service is temporarily unavailable`. The same
tool, same trigger, same minute, succeeded when the call carried only `prompt`.
`create_trigger` and `create_session` accept no working model override from this
environment either — `create_session` failed identically three times.

The `model` field on `update_trigger` is not usable here; the failure is
specific to that field, not to the service. A Routine's model is effectively
fixed at creation, and the only observed way to change it is the Routines UI on
claude.ai.
