# Prevention Mechanisms

**Status:** Active authority
**Ratified:** 2026-07-31
**Owner:** Jacob

This file defines enforceable prevention mechanisms for the Kitty repository.
Each mechanism must have a CI check or procedural gate that enforces it;
prose alone is insufficient.

## 1. Red-main freeze

**What:** `main` must never be red. A push that breaks CI is rolled back or
immediately fixed.

**Enforcement:** Required status checks on the active `main` GitHub ruleset:
`policy-gate` and `merge-gate`. The aggregate merge gate owns the applicable
`pytest`, `lint`, `typecheck`, `kitty-chat`, and `browser-smoke` evidence; docs/Markdown-only
PRs may skip code/browser jobs. Every applicable required signal must succeed
before `merge-gate` passes. GitHub ruleset enforcement applies this at the
platform level.

Post-merge validation on `main` is scope-aware for the same reason PRs are. The
active ruleset has zero bypass actors for its required protections, but strict
up-to-date checking is **not** enabled (`strict_required_status_checks_policy=false`).
A PR-head check therefore does not prove the final integration tree is identical
to that head when `main` advanced meanwhile. Docs-only merges still skip code
jobs because their own diff contains no code; code-bearing merges retain
red-main detection, and the nightly full suite in
`.github/workflows/nightly-health.yml` remains the time-based canary.

**Status:** ENFORCED. The default-branch ruleset is active on GitHub.

## 2. One active implementation lane

**What:** At most one non-Dependabot feature PR may be open against `main`
at any time. This prevents the collision of #306, #308, #327, #328, #330
that required reconciliation.

**Enforcement:** CI check on PR open. If another non-Dependabot PR is already
open against `main`, the check fails with a comment naming the blocking PR.
Dependabot PRs are exempt.

**Status:** DEFINED. Needs `pr-single-lane-check.yml` workflow.

## 3. Branch freshness and conflict checks

**What:** A PR branch must be based on a recent `main` commit (within 48 hours).
A branch with merge conflicts is blocked from merge.

**Enforcement:** GitHub pull-request protection blocks conflicted merges, but the
active ruleset does **not** require a branch to be updated to latest `main`. A
separate CI/procedural freshness check is therefore required for the 48-hour
policy.

**Status:** PARTIALLY ENFORCED. Conflict protection is platform-level; strict
up-to-date/freshness is not. The 48-hour freshness check still needs an
enforceable workflow or an explicitly retained procedural gate.

## 4. Open-PR overlap detection

**What:** When a new PR is opened, CI checks whether any other open PR touches
the same files. If so, a comment is posted naming the overlapping files and PRs.

**Enforcement:** CI workflow triggered on PR open/reopen. Compares the PR's
changed files against all other open PRs' changed files.

**Status:** DEFINED. Needs `pr-overlap-check.yml` workflow.

## 5. Required checks and independent review

**What:** Every PR must satisfy the two stable required gates; deterministic
code/browser jobs are selected by scope. Sensitive changes additionally require
trusted independent exact-head review evidence and the applicable approval
boundary.

**Enforcement:**
- CI: the ruleset requires `policy-gate` and `merge-gate`. `merge-gate` aggregates
  applicable `pytest`, `lint`, `typecheck`, `kitty-chat`, and `browser-smoke`
  jobs; docs-only PRs may skip code/browser jobs.
- Review: PR Agent Review may produce advisory review on ordinary owner PRs.
  `policy-gate` requires trusted exact-head independent review for sensitive
  scope; ordinary docs/code changes do not become blocked merely because the
  external review model is unavailable.

**Status:** ENFORCED for the current scope-aware gate and sensitive-review
contract. Model-origin metadata remains a separate improvement area.

## 6. Stale-draft policy

**What:** Draft PRs unchanged for 7 days are auto-closed with a comment.

**Enforcement:** GitHub Actions scheduled workflow runs daily. Closes drafts
where `updated_at < 7 days ago`.

**Status:** DEFINED. Needs `stale-draft-close.yml` workflow. GitHub's
`actions/stale` can handle this, but it's currently pinned at v9 in #312.

## 7. Roadmap inventory coverage check

**What:** Every file under `docs/plans/`, `docs/planning/`, `docs/packets/`,
`docs/initiatives/` must appear in `docs/DISPOSITION_LEDGER.md`. A new file
added without a ledger row fails CI.

**Enforcement:** CI check on push to `main`. Scans the four directories,
verifies every file has a row in the ledger. New files fail the check.

**Status:** DEFINED. Needs `ledger-coverage-check.yml` workflow (or a
`scripts/check_ledger_coverage.sh` called from CI).

## 8. Active mission phase must exist in the roadmap

**What:** `docs/ACTIVE_MISSION.md` declares a phase (extracted from the
mission title or `kitty-mission` JSON block). That phase must have a section
in `docs/ROADMAP.md`.

**Enforcement:** CI check on PRs that modify `docs/ACTIVE_MISSION.md`.

**Status:** ENFORCED by this roadmap rewrite. Phase 2 now exists in the
roadmap and KLF-001 sits within it.

## 9. Evidence requirements by type

**What:** Certain change types require specific evidence before merge:

| Change type | Required evidence |
|---|---|
| UI change | `browser-smoke` pass + screenshot of changed views |
| Restore/backup change | test suite proving identical pre/post state |
| Cost-incurring change | cost estimate + cleanup confirmation |
| Cleanup/destructive change | confirmation that cleanup completed without side effects |
| Auth/secrets/env change | Jacob's explicit approval + evidence of correct operation |

**Enforcement:** `policy-gate` derives sensitive and native-UI scope from the
actual changed paths, through the one canonical classifier in
`scripts/pr_scope.py` that also selects required CI jobs. Sensitive scope requires `risk/approved`, an exact-head
Risk approval receipt, and trusted independent review. Native UI source/public
changes require the product-acceptance evidence block. `merge-gate` requires
code checks only for code-bearing PRs and browser smoke only for non-documentation
frontend changes.

**Status:** PARTIALLY ENFORCED. Sensitive-scope and native-UI evidence are
enforced; restore/cost/cleanup evidence remains change-specific rather than a
generic PR-body parser.

## 10. Model origin tracking

**What:** Every PR must track which model authored it (from commit author:
`claude`, `codex`, `jacob202`, `copilot`, `dependabot`). A model may not
approve its own work.

**Enforcement:**
- PR metadata/Builder evidence may identify the author model.
- PR Agent Review identifies the reviewer model.
- `policy-gate` accepts only trusted exact-head independent review evidence for sensitive scope.

**Status:** DEFINED. Needs `pr-model-origin-check.yml` workflow.

---

## Implementation priority

1. **Platform-enforced (already working):** pull-request/deletion/non-fast-forward
   protection plus required `policy-gate` and `merge-gate` checks. Strict branch
   up-to-date enforcement is **not** enabled and must not be listed as a platform
   guarantee.

2. **CI workflows to add (in order):**
   - `pr-single-lane-check.yml` — blocks second concurrent feature PR
   - `stale-draft-close.yml` — auto-closes stale drafts
   - `pr-overlap-check.yml` — detects file overlap between PRs
   - `ledger-coverage-check.yml` — verifies every planning file is in the ledger
   - `pr-model-origin-check.yml` — prevents self-review

3. **Procedural (no CI needed):**
   - Evidence requirements by type — enforced by PR review, not automation.
   - Active mission phase check — already satisfied by this roadmap.
