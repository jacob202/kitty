# Handoff — 2026-07-24 — main

<!-- kitty-handoff
{
  "schema_version": 1,
  "updated_at": "2026-07-25T03:09:22Z",
  "head_sha": "10bebdde1f7ab94f43d072cb8c40cf59252f8e97",
  "branch": "main",
  "worktree": ".",
  "status": "in_progress",
  "completed_items": [
    "4 feature branches merged: builder-upgrade, companion-personality, life-awareness, image-system-v2",
    "Auto PR agent review live (GitHub Action + OpenRouter, secret set)",
    "Builder control actions wired to the CLI — the UI buttons were no-ops before",
    "Dogfood fixes + AGENTS.md workflow rules + QUICKSTART.md",
    "Tooling audit session (e3d84e2): dead symlinks, venv, MemoryError contract, search route, soul/ restore, suite green, v0.1 tagged"
  ],
  "blockers": [],
  "next_action": "Start the two queued KX-06 packets: KX-06-01 (signals feed on Home, priority 8) then KX-06-02 (plain-English deadline/phone/what-changed cards). The Builder Run button works now, so they can be started from the UI or with ./kitty builder initiative run kx-06-proactive-feed-v1 --free --gate manual.",
  "invalidation_conditions": [
    "HEAD changes beyond 10bebdde1f7ab94f43d072cb8c40cf59252f8e97",
    "either queued KX-06 packet is claimed or completed"
  ],
  "active_mission": "docs/ACTIVE_MISSION.md",
  "pull_request": null
}
-->

## Goal

Ship 4 merged feature branches + wire CI automation (auto PR review, dogfood) + fix dead
builder buttons.

## State

- **Done:** 4 feature branches merged (builder / personality / life-awareness /
  image-system). Auto PR agent review live (GitHub Action + OpenRouter, secret set).
  Builder control actions wired to the CLI (no longer no-ops). Dogfood script + sidebar
  home fix + gateway.ts fix. AGENTS.md no-tests-mid-session rule + QUICKSTART.md.
- **In flight:** nothing
- **Untouched:** task 2–5 follow-up scope (see `docs/planning/agent-prompts-2026-07-24.md`),
  pre-commit hook (not installed), mempalace migration status (unknown)

## Gotchas

- `git push` blocked by OpenCode permission rules — Jacob pushes from terminal
- Tests only run on `/qg` request or on CI — never mid-session
- Builder control actions now call `./kitty builder ...` via subprocess — changing the CLI
  could break the action queue
- A tier in `config/action_tiers.json` with no matching executor gives you a button that
  returns HTTP 200 and does nothing. That is exactly how the builder buttons were dead.
  `tests/test_builder_control_actions.py` guards both halves now.

## Queued and ready

Two packets, both user-facing, both reusing one card component:

- **KX-06-01** (priority 8) — signals feed on Home + "anything to flag?" in chat, with
  dismiss/snooze.
- **KX-06-02** (priority 7) — replace the three developer-jargon Home cards (deadlines,
  phone access, what changed) with plain-English actionable cards.

Note: 23 of 59 queue tasks are cancelled vs 34 done. Worth understanding that scrap rate
once these two land — the runner being broken is a likely cause.

## Next step

`catch me up` — check what's next from agent-prompts and pick a task.
