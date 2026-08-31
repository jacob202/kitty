# Kitty Opens-the-Doors — unattended handoff

Date: 2026-08-31
Branch: `docs/kitty-opens-doors-compiler-20260831`
PR: #740 — `docs(packets): compile Kitty opens-the-doors slate`

## Operating mode

- Do not manually babysit packet progress.
- `com.kitty.builder.supervisor` is loaded under launchd and ticks every 900 seconds.
- Supervisor dispatch is bounded to at most two canonical free runs per tick.
- `config/compute_governor.json` remains the spend authority; current weekly ceiling is CAD 6.
- Never duplicate-launch work that has an active Builder run.
- Never create a second queue/scheduler/orchestrator for this campaign.
- Publication, merge, extra retry budget, scope/identity releases, and product-judgment holds remain explicit operator decisions.

## Current verified execution state at session end

- `KF-WHY-01` merged as PR #738.
- `KF-SEARCH-01` has open PR #739.
- Unsafe PR #737 is closed.
- Corrective backend `KF-UNDO-02` is the active run under v6, worker `opencode-free`.
- `KF-COPY-01` ended interrupted and is at operator-review state; do not restart blindly.
- `KF-GLANCE-01` remains recovery-needed; preserve its existing worktree/evidence.
- `KF-LIFE-01`, `KF-NUDGE-01`, and `KF-DEFAULT-01` have implementation/review evidence and need reconciliation rather than fresh implementation.
## Collision-held work

- `KF-SCHEDULE-01`: wait for the active `gateway/app.py` owners to clear, then refresh the packet against current main before applying.
- `KF-COUNCIL-01`: wait for PR #732/completions ownership to clear, then refresh before applying.
- Interactive v7/v8 companions are manifest-less by design; each document names its release condition and Tier 1/2/3 proof.
- `KF-MAGIC-01` must verify PR #733 first and close as superseded if #733 already satisfies acceptance.
- `KF-RESUME-BE-01` is the required backend prerequisite for reload-mid-reply; do not try to solve resume with browser storage alone.

## Monitoring

ChatGPT automation `Kitty Opens Doors Watch` is enabled hourly in condition-watch mode.
It stays silent during ordinary progress and only surfaces a genuine operator decision, a cleared collision hold, supervisor failure, substantive CI/review defect, or merge-ready compiler PR.

## Resume protocol

1. Read this file and `docs/session-notes/2026-08-31-kitty-opens-doors-compiler-outcome-contract.md`.
2. Run `./kitty builder supervisor status --json` and inspect only `kitty-opens-the-doors-20260831-*` plus active runs.
3. Check PRs #725, #726, #729, #731, #732, #733, #735, #739, #740 and any newer Builder PRs.
4. If safe work is active/queued, leave it alone; launchd owns continuation.
5. Act only on the smallest verified operator-only blocker. Do not restart the audit or recompile the slate.
