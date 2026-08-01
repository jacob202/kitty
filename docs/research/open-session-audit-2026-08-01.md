# Open session audit — 2026-08-01

Every open session branch, where it stopped, and whether its work reached `main`.

Base: `origin/main` at `bcae5f28fcb5a11573faeea29862231a9335b7fa`.

## Method

The session container clones shallow (16 grafted roots, 264 visible commits).
Under a shallow clone `git merge-base` returns empty and every older branch looks
like it shares no history with `main` — the first pass reported 1000+ "unlanded"
commits on branches whose PRs had merged cleanly. Those numbers were artifacts.
This audit ran after `git fetch --unshallow` (1656 real commits on `main`).

Squash merges break `git cherry` the same way: the branch keeps its pre-squash
commits, so they read as unlanded forever. Landing was therefore decided on
**content**, not commit identity — for each branch, diff its files against
`merge-base`, then check whether each touched file exists on `main` and whether
the branch's specific change is present.

## Claude Code sessions (`claude/*`) — 20 branches

### Landed, safe to close (18)

Tip is already an ancestor of `main`:

| Session | PR(s) |
| --- | --- |
| `compute-governor-receipts` | #278 closed → rebased and merged as #285 |
| `kitty-builder-issues-jgwdh5` | #284 merged |
| `kitty-master-architecture-bg48z3` | #277 merged |
| `kitty-stabilization-fbydi0` | #339, #341, #343 merged |
| `pr-278-merge-conflicts-mwjsps` | #285 merged |
| `roadmap-progress-review-9el2ch` | #328, #335 merged |
| `session-end-recommendations-xsd0ss` | #276 merged |
| `token-usage-optimization-w96qq3` | #299 merged |

Squash-merged — commits differ, content verified present on `main`:

| Session | PR(s) | Verification |
| --- | --- | --- |
| `alignment-map-packet-audit-xbsbbi` | #263 merged | 23 files touched, all on `main` |
| `build-it-plugin-install-ato3if` | #337 merged | 3 files touched, 0 differ from `main` |
| `builder-52dcp7` | #340, #342, #344 merged | `builder_recovery_proof.py`, initiative + research doc all on `main` |
| `delta-014-026-xbsbbi` | #267 merged | 0 unlanded patches |
| `initiative-gate-repair-xbsbbi` | #262 merged | 6 `kx-*` initiative manifests on `main`; remaining commits are CI trigger markers |
| `kittybuilder-brain-review-xbsbbi` | #261 merged | `builder_initiative.py`, brain-v1 manifest, harvest doc, tests all on `main` |
| `ktf-002-acceptance-prose-xbsbbi` | #268 + #272 merged | `ktf-002-acceptance-prose-v1.json` on `main` |
| `ktf-002-checksum-gate-xbsbbi` | #272 merged | 0 files differ |
| `kx-combine-and-plan-xbsbbi` | #269 merged | 0 files differ |

Closed unmerged but superseded — work reached `main` another way:

| Session | Died at | Where the work is |
| --- | --- | --- |
| `fix-openai-mem0ai-pin-conflict` | #338 closed unmerged | Identical pin `openai>=1.90.0,<1.110.0` landed via #339 |

### Died with work still unlanded (2)

**`claude/pr-review-48h-aptjw0`** — PR #326 merged at `631ace0`, then the session
kept working and never opened a second PR. Eight RunPod hardening commits sit
above the merge point:

- `fix(runpod): preserve startup failure diagnostics`
- `fix(runpod): use baked ComfyUI root and stream checkpoint hash`
- `fix(runpod): declare baked ComfyUI root`
- `fix(runpod): always emit preflight container evidence`
- `fix(runpod): supervise bootstrap as PID 1 child`
- `test(runpod): lock startup diagnostic contract`
- `fix(runpod): preserve exact bootstrap error state`
- `debug(runpod): add one-command live James verification`

Missing from `main` entirely: `scripts/runpod_live_james.sh`,
`tests/test_runpod_bootstrap_contract.py`. Modified but unlanded:
`workers/comfy_worker/{Dockerfile,bootstrap.sh,entrypoint-kitty.sh}`,
`scripts/runpod_image_preflight.py` (229 insertions / 115 deletions vs `main`).
Confirmed absent: the branch's `entrypoint-kitty.sh` tracks `BOOTSTRAP_PID` for
PID-1 supervision; `main`'s version has no such variable.

**`claude/conversion-plan-xbsbbi`** — PR #266 opened as a draft and closed
unmerged. `docs/CONVERSION_PLAN.md` ("stop producing analysis, build the path")
does not exist on `main` and exists nowhere else in the tree.

## Other agent sessions — orphaned work

| Branch | Died at | Missing from `main` |
| --- | --- | --- |
| `docs/builder-cockpit-boundary` | **never opened a PR**, last commit 2026-08-01 | ADRs 0024/0025/0026, `ktl-001-leverage-and-learning-v1.json`, `LEVERAGE_SYSTEMS_IMPLEMENTATION_CONTRACT.md`, `scripts/kb_effectiveness.py`, `scripts/session_learning.py`, both their test files, `.agents/skills/next/SKILL.md` — 28 commits, 10 files |
| `contract-first` | #298 closed unmerged | `scripts/dump_openapi.py`, `gen/openapi.json`, `gen/gateway-schema.d.ts`, `docs/contract-migration.md` — the OpenAPI→TS pipeline behind `response_model` on 193 routes |
| `docs/hardened-human-loop-plan-2026-07-26` | #271 closed as draft | `docs/planning/HUMAN_LOOP_HARDENED_PLAN_2026-07-26.md`, `docs/session-notes/CHATGPT_CLOSEOUT_2026-07-26.md` |
| `kittybuilder/kb_ms7thghj_51a6` | #324 closed unmerged | `docs/research/ktf-004-v4-provider-exhaustion-probe.md` (plus 2 `.omo` run-continuation blobs) |
| `jacob202/fix-description` | #293 closed unmerged (#289 merged instead) | `gateway/kitty-chat/src/components/ContextBar.tsx` |
| `docs/session-end-2026-07-26` | #275 merged | `docs/session-notes/CHATGPT_CLOSEOUT_2026-07-26.md` (same file as #271) |
| `spike/foundation-replacement-2026-07-27` | #286 merged from the `-clean` sibling | `spikes/foundation-replacement/.gitkeep` only — nothing of substance |

Branches whose every patch is on `main` and which hold nothing unique:
`cleanup/slice-0c`, `fix/builder-identity-scope-source`, `fix/claude-md-ask-rule`,
`hardening-sweep`, `mai`, `codex/review-ans-pla`, all three `copilot/*`,
`docs/ktf-001-free-exec-packets`, `feat/builder-queue-doctor`,
`feat/kittybuilder-brain-initiatives`, `feat/ktf-003-outcome6-runtime`,
`feat/runpod-image-studio-smoke`, `feature/runpod-image-studio-smoke`,
`fix/dogfood-provider-chat-shell-2026-07-28`, `fix/restore-ci-installs`.

## Open PRs — live, not dead

Merged during this audit, after review:

| PR | Disposition |
| --- | --- |
| #356 acceptance-gate loophole | Squash-merged as `febbb99d`. Docs/template only; 12/12 green |
| #355 mobile shell + fail-closed Studio | Squash-merged as `dda86249`. 14/14 green. Reviewed the `fetchImageStatus` contract change: dropping its `catch` makes a gateway outage throw instead of reporting `available: false`, which is the point — the two failures have different recoveries. All four consumers (`ImageStudio`, `StudioView`, `ProviderCenter`, `ImageGenPanel`) reach it through `useImageStatus`, and `ImageGenPanel` — the one component the PR did not touch — reads `statusQuery.data?.available ?? null`, so it degrades to unavailable rather than crashing |
| #358 builder dirty-worktree retry fix | Squash-merged as `037052b6`. Its `check-description` failure was the PR body, not the code: no bullet under `## Summary` and a `## Verification` heading where `.github/workflows/pr-description-check.yml:41-47` requires the literal `## Test plan`. Body rewritten to satisfy the gate with content preserved; the gate then passed |

Still open:

| PR | State | Why not merged |
| --- | --- | --- |
| #357 KittyBuilder paid smoke evidence | draft, `[do not merge]` | Disposable by design — close without merging |
| #359 KB learning + Builder boundary | draft | The `docs/builder-cockpit-boundary` orphan now has a PR |
| #360 this audit | draft | Self-authored |
| #361 026/027 delta reconcile | draft | — |
| #362 reviewer runs deepseek-v4-pro | draft | — |

Six Dependabot PRs (#314–#317, #319, #320) remain open; four carry
`risk/manual-approval`, and all six are based on `27deef12`, well behind `main`.
Not merged here: `CLAUDE.md` non-negotiable 6 forbids auto-merging dependency
work, and #322 in this same batch is what broke `main` for eight commits.

## What this cost

`claude/pr-review-48h-aptjw0` is the expensive one: a session merged its first
PR and then did eight more commits of real RunPod bootstrap hardening —
including PID-1 supervision and a test locking the startup diagnostic contract —
that never got a second PR. `docs/builder-cockpit-boundary` is the same failure
one step earlier: 28 commits, three ratified ADRs, two scripts with tests, and no
PR was ever opened at all.

Both are the same gap: nothing notices when a branch stops moving with commits
above its last merge.
