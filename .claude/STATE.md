# Session State — 2026-07-11 (Fable blueprint session wrap)

## Branch
- `docs/fable-context` @ see `git log` — contains main (`c48186b`) + context bundle + this session's commits. Nothing pushed. Uncommitted product code: none.

## Landed this session (all local commits on docs/fable-context)
1. `569608b` fix(gateway): verifier false-green (#2), duplicate route contracts (#3), fail-loud model_digest + next_step (#4) — 20 tests green. Was uncommitted work from the prior session; verified then committed.
2. `92dc9ee` docs(fable-context): the bundled "UI/mascot reference" images were the WRONG Desktop files (a subscriptions dialog + a Codex usage screen). Replaced with the real Jul-8 screenshots and wrote visual descriptions into the bundle. UI = dark cosmic Stitch dashboard; mascots = doodle line-art cats (blue-boxed: starry-eye logo head, rain-cloud cat, standing sketch cat).
3. `907c6c0` docs: `docs/BLUEPRINT.md` + ADR 0015 — the resume loop is the product; hard Kitty/Builder boundary; Orca is an adapter; failure semantics are a contract; browser QA is a UI release gate.
4. Builder initiative `trust-lane-v1` applied (5 packets, see `docs/initiatives/trust-lane-v1.json`) — first real initiative in the queue.

## Browser QA — FIRST EVER live pass (2026-07-11, in-app browser)
- Verified working: 3-step onboarding ("hey, i'm kitty" → name/theme, cosmic default → finish) with persistence across reload; home resume loop (hey Jacob; What's Next with real generated step + why + CTA; Needs You; deadlines honest-empty; 7 real projects); chat round-trip (sent "Reply with exactly: FABLE-QA-OK", model replied exactly that via LiteLLM, chat persisted, sidebar updated); truthful status bar (gateway live · routing live · 6 models · chat store ok); mobile 375px layout stacks correctly.
- Bug found+fixed live: gateway process was running pre-`14f5865` code → `/session/context` 404 → What's Next stuck on "loading…" forever. `./kitty down && ./kitty up` fixed it. Follow-ups queued as TL-01 (frontend error state) and TL-02 (doctor freshness check).
- Findings queued as packets: TL-03 Enter doesn't send in composer; TL-04 mascot overlaps sweep button at mobile width.
- Gotcha: the UI dev server MUST run from the main checkout. `.claude/launch.json` pointed at `.worktrees/fable-ux-phase`, which has no `.env`, so the proxy had no gateway secret → every proxy call 503. launch.json fixed; server now `next dev -H 127.0.0.1 -p 4000` (loopback only — do not bind 0.0.0.0, see Card A).

## T2 escalations (Codex/Jacob only — do not let workers touch)
- Card A: UI binds `0.0.0.0` in `./kitty` (cmd_start/cmd_verify_home) + proxy injects gateway secret; path-ingestion SSRF in capture/knowledge routes.
- Card B: `gateway/agent_runner.py` / `task_runner.py` can convert failures into `completed`; `stop()` unreliable.

## Next session: start here
1. Read `docs/BLUEPRINT.md` (the plan) and this file.
2. Run trust-lane-v1 packets via free workers (`./kitty builder initiative status trust-lane-v1`), independent review, operator publish.
3. Product lane P2 (real session-close consolidation record) is the next vertical slice after TL packets.
4. Decide with Jacob: merge `docs/fable-context` → `main` (fast-forward-ish) and whether to push.

---

# Session State — 2026-07-10 (wrap)

## Branch
- `main` @ `ece1480` (`origin/main`), with local UI wiring fixes uncommitted. No push or commit was performed.

## Landed this session
- **#143** mega: KittyBuilder S1–S3 stack + chat/runtime (CI unblocked then merge)
- **#144** KB-S4a: `sync-pr` / `reconcile-merges`, recovery skip for bad run rows
- **#145** KB-S4b: `queue publish` / `builder_publish.py` — operator push + PR create/update (no force, no merge)
- Local S4 hardening: `gh` token stripping (`GITHUB_TOKEN`/`GH_TOKEN`) in publish + pr-status, task-worktree/base scoping for PR commands, completed shadow-report gating, safe check/review rollups, blocked merge promotion, and JSON error exit codes.
- Local KB-S5 hardening: restart lease/run reconciliation, durable pause reasons, explicit abort/pause outcomes, kill-switch coverage, and CLI packet output fix.
- CI hardening: Ruff lint is now blocking; full Ruff, mypy, and focused Builder suites pass.

## Done definition
- S1A–S4 builder path on main complete per `docs/KITTYBUILDER_SELF_BUILDING_MVP.md`
- Shadow workers still credential-stripped; publish is operator-only

## Completed locally (KB-S5)
- `gateway/builder_run.py` `run_initiative` driver (loop next_packet -> run_packet -> publish_task)
- `builder_initiative.py`: `get/set_initiative_state`, `pause_initiative`, `resume_initiative`
- `builder_cli.py`: `initiative run` / `pause` / `resume`
- `tests/test_builder_run.py`: 7 tests pass; focused Builder suites 340 passing
- Loop processes next eligible packet per invocation; dependents advance only after merge (DONE via `reconcile-merges`). Per-initiative attempt + runtime budgets pause with reason.

## Next
- With Jacob's approval, commit/push `feat/kb-s5-run-loop` and open a thin PR; workers never push or create PRs.
- After merge, run the operator loop with explicit budgets and `--publish` only when ready; reconcile merged PRs to unlock dependents.

## Local junk (do not commit)
- `.env.bak` (sed backup of `.env`, may hold `GITHUB_TOKEN_LEGACY`) — untouched and untracked; user must remove it explicitly.

## UI swarm QA — 2026-07-10
- Branch at stop: `main` @ `ece1480` (`Merge pull request #148 from jacob202/refactor/brief-news-source-seam`); this advanced from the branch observed at session start. No code edits were made by this QA pass.
- Done: dispatched five read-only live UI tester lanes through Orca/OpenCode against `http://127.0.0.1:4000` (functional, first-run/emptiness, navigation/accessibility, responsive, whole-journey); Codex worker boots failed because CLI `0.142.5` rejects configured `gpt-5.6-luna`.
- Evidence: coordinator browser reached the page title `Kitty`, but the first viewport stayed uniformly beige; DOM snapshot was empty, body text was empty, console had no error/warn entries, and the HTML contained only the pre-hydration `height:100vh;background:var(--bg)` shell. Reload verification timed out. This is a release-blocking blank-screen finding.
- In flight/blocker: OpenCode replacements were still in browser/tool startup and had not emitted structured worker_done reports before stop. Re-run the swarm only after confirming the worker model/tooling path and the canonical branch.

## UI wiring fix pass — 2026-07-10
- Fixed the cosmic theme cascade in `gateway/kitty-chat/src/app/globals.css`; explicit `data-theme="cosmic"` no longer gets overwritten by the day-mode `:root` rule.
- Increased bounded gateway request timeouts and added short recovery refreshes for Brief, Models, Todos, Deadlines, State Changes, and State Now so cold-start latency does not become a five-minute false-offline state.
- Made Today use its own `/todos` error state; `/todos` no longer converts gateway failures into an empty list, and Brief failures no longer mark a healthy Today card offline.
- Made Image Lab truthful and actionable while ComfyUI is unavailable: status loading is explicit, setup guidance is accurate, and a `check again` control is available.
- Verification: frontend serial suite `14 files / 106 tests passed`; `npm run build` passed; live browser reload showed gateway/routing/chat store live, honest empty/baseline states, and no browser errors.
- Remaining external blockers: ComfyUI is not running/configured, Gmail token is expired, Telegram is unset, and Chroma has zero collections. These are environment/integration setup issues, not hidden as fake app success.

## Personality and feedback pass — 2026-07-11
- Current branch remains `main`; all changes are uncommitted and must be reviewed/staged deliberately with the earlier UI wiring work.
- Added mounted feedback, personality, session-context, and usage endpoints; chat ratings, editable personality, session carry-over, onboarding, and scoped accessibility fixes are wired in the UI.
- Verification: frontend suite 116 passed; targeted Python endpoint suites, Ruff, compile checks, TypeScript, and diff check passed. Production build emitted a BUILD_ID after successful compilation/typechecking; browser runtime was unavailable for live UI QA.
- Next: review the combined dirty diff, decide whether to split this from the existing UI wiring changes, then commit only with Jacob's approval. Do not reset the pre-existing skill/session/UI wiring edits.
- [claim] packet 020 github connector — orchestrator subagent
- [claim] packet 022 magic kitty — orchestrator subagent
- [claim] ui-feel-polish — orchestrator subagent
- [claim] packet 024 chat-log mine — orchestrator subagent
- [claim] packet 025 imagegen v2 — orchestrator subagent
- [done] packet 020 github connector — issues source added, 7 tests pass, PR #156 (read-only, no token log, write scopes disabled)
