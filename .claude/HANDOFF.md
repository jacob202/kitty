# Handoff — 2026-07-11 (Fable final session: life-first)

## TL;DR
Kitty's purpose is now written down where no session can lose it: `docs/NORTH_STAR.md` + ADR 0016. Life projects outrank code projects everywhere Kitty suggests; the daily path must run on the free/cheap routes (verified real: `kitty-default` = DeepSeek flash, `kitty-default-or` = free Gemini). Initiative `life-first-v1` (4 packets) is applied to the Builder queue alongside `trust-lane-v1` (5 packets). The life-first preference is also live immediately via `config/PREFERENCES.md`, which next_step reads today. Any capable free worker can now continue: read NORTH_STAR §4, take one packet, stay bounded, stay honest.

---

# Handoff — 2026-07-11 (Fable blueprint session)

## TL;DR
Blueprint written (`docs/BLUEPRINT.md`, ADR 0015). Codex-blocker fixes verified and committed (`569608b`). Visual references corrected (`92dc9ee` — the bundle had the wrong images entirely). First-ever live browser QA passed: onboarding, home resume loop, real chat round-trip, mobile layout all verified working; findings converted into Builder initiative `trust-lane-v1` (5 packets, queued). Branch `docs/fable-context`, nothing pushed, no uncommitted product code.

## Resume in one command
`./kitty builder initiative status trust-lane-v1` — then dispatch TL packets to free workers per the standing rules below. Read `docs/BLUEPRINT.md` §7 for lane order. Full detail in `.claude/STATE.md` (2026-07-11 section).

## Watch out
- Gateway serving stale code looks healthy (doctor passes) but 404s new routes — restart after pulling code until TL-02 lands.
- UI dev server must run from the main checkout on loopback (`node node_modules/next/dist/bin/next dev -H 127.0.0.1 -p 4000` in `gateway/kitty-chat`); worktree checkouts lack `.env` → proxy 503s.
- T2 stays with Codex/Jacob: Card A (0.0.0.0 bind + SSRF), Card B (false-completed runner states).

---

# Handoff — 2026-07-10

## Context
Jacob authorized merge of mega PR #143 (after CI fix), then dealer's-choice follow-ups. Agent stood down after S4 complete.

## On main
1. Builder initiative/queue/runner/loop (S1–S3) + chat lifecycle/artifacts/runtime (bundled in #143)
2. Merge detection + PR sync (#144)
3. Operator publish: `./kitty builder queue publish <task_id>` (#145)

## Operator surface (S4)
```
./kitty builder queue publish <id> [--remote origin] [--base main] [--title ...] [--dry-run]
./kitty builder queue sync-pr
./kitty builder queue reconcile-merges
```
Never auto-merges. Workers do not get GitHub tokens.

## Resume here
KB-S5 is implemented and audited locally on `feat/kb-s5-run-loop` (not pushed):
```
./kitty builder initiative run <id> --worker-command '["opencode","run"]' [--publish] [--max-attempts N] [--max-runtime S]
./kitty builder initiative pause <id> [--reason ...]
./kitty builder initiative resume <id>
```
Loop drives next eligible packet (S2/S3) then optional KB-S4b publish; repeats until no packet eligible or budget/pause halts. Restart reconciles stale leases/runs; PR-merge `reconcile-merges` advances dependency packets to DONE. Publish and queue reconciliation now strip ambient GitHub tokens, scope `gh` to the task worktree/base, gate on final shadow reports, and fail on non-success check rollups.

Verification: focused Builder suites 340 passed; full Ruff and touched-file mypy pass. The lint job is now blocking in `.github/workflows/tests.yml`.

## Do not
- Reverse-split #143
- Let workers push/PR (publish is operator-gated; `gh` runs token-stripped)
- Push or open the PR without Jacob's explicit approval.
- Resume without reading this + STATE

## UI swarm QA handoff — 2026-07-10
- Request: hostile live UI swarm focused on bugs, empty/thin states, and the whole user experience.
- Target: local UI at `http://127.0.0.1:4000`; gateway was listening on `127.0.0.1:8000`.
- Five read-only lanes were dispatched through Orca/OpenCode. The first Codex wave failed before testing because installed Codex `0.142.5` rejects configured model `gpt-5.6-luna`; OpenCode replacements started but remained in browser/tool startup and produced no structured reports yet.
- Coordinator evidence is decisive: `Kitty` title loads, but the visible viewport is a uniform beige blank; DOM snapshot and body text are empty; no error/warn console logs were captured; page HTML contains the pre-hydration shell `<div style="height:100vh;background:var(--bg)"></div>` and no interactive UI. A reload attempt timed out. Treat this as P0/release-blocking until reproduced/fixed.
- Working tree remained code-clean except the pre-existing staged modification to `.agents/skills/engineering/improve-codebase-architecture/SKILL.md`. Do not reset or alter it. The checkout advanced to `main` @ `ece1480` during the run; verify branch before resuming.
- Next: fix or investigate the hydration/blank-screen failure first, then rerun the five lanes with a worker path that can emit reports and capture screenshots/repro steps. Do not claim the broader UX review is complete from the blank-screen baseline alone.

## UI wiring fix handoff — 2026-07-10
- The blank-screen finding was reproduced as a stale frontend dev-server/cache process. After killing the stale process and starting a clean `npm run dev -H 127.0.0.1 -p 4000`, the app hydrated and rendered normally.
- Source fixes are currently uncommitted on `main`: theme selector cascade, gateway timeout/recovery policy, honest `/todos` errors, Today query ownership, state-query retries, and Image Lab loading/retry copy. Plan: `docs/plans/fix-kitty-ui-wiring.md`.
- Live evidence after reload: `gateway live`, `routing live · 6 models`, `chat store ok · 2 saved`; What Changed shows `no snapshot yet — POST /state/snapshot to create a baseline`; Today shows `nothing on the list`; browser errors are empty.
- Verification passed: `npm test -- --run --maxWorkers=1` (106 tests) and `npm run build`. Targeted gateway/HomeState tests also passed.
- The dev server is still running in the current terminal session on `127.0.0.1:4000`; gateway/LiteLLM are up via `./kitty up` state. Do not stop them unless restarting the live UI.
- Remaining work is broader feature hardening, not a reproduced blank shell: many gateway mutation/read helpers still intentionally return fallback `[]`/`null` on errors, and external services remain unavailable (ComfyUI, expired Gmail refresh, no Telegram, empty Chroma). Address those in a separate scoped pass rather than expanding this fix silently.

## Personality and feedback pass — 2026-07-11
- Uncommitted additions: `gateway/routes/personality.py`, `session_context.py`, and `usage.py`, mounted in `gateway/routes/register.py`; the pre-existing feedback route is now mounted too.
- UI: assistant thumbs up/down with visible error state; Settings personality/model/voice/usage sections; What's Next session context; first-run onboarding; targeted a11y repairs in Capture, Documents, TopBar, and ChatMessage.
- Verification evidence: frontend `npm test -- --maxWorkers=1` = 116 passed; targeted endpoint tests pass; Ruff, compile, TypeScript, and `git diff --check` pass. A production `.next/BUILD_ID` exists after `next build`; in-app browser was unavailable, so visual QA remains unproven.
- Keep existing local UI wiring changes and `.agents/skills/.../improve-codebase-architecture/SKILL.md` untouched; no commit/push was made.
