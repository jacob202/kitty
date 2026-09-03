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

**Enforcement:** Required status checks on the `main` branch protection rule:
`policy-gate` and `merge-gate`. The aggregate merge gate owns the applicable
`pytest`, `lint`, `typecheck`, `kitty-chat`, and `browser-smoke` evidence; docs/Markdown-only
PRs may skip code/browser jobs. Every applicable required signal must succeed
before `merge-gate` passes. GitHub ruleset enforcement applies this at the
platform level.

Post-merge validation on `main` is scope-aware for the same reason PRs are.
The live default-branch ruleset does **not** require strict up-to-date checking
(`strict_required_status_checks_policy=false`). Required checks therefore prove
the PR head they ran on, but the platform does not itself prove a stale branch's
final combined tree after newer `main` changes. Refresh/revalidate stale branches
before merge when that distinction matters. The nightly full suite in
`.github/workflows/nightly-health.yml` remains the time-based canary for drift.

**Status:** PARTIALLY ENFORCED. Required gates and no-bypass protection are
platform-enforced; strict branch freshness is not.

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

**Enforcement:** GitHub blocks merge conflicts, but the active ruleset does not
require branches to be up to date before merge. No current CI check enforces the
48-hour freshness rule.

**Status:** DEFINED / NOT ENFORCED for freshness. Merge conflicts are blocked;
branch-age/current-base enforcement still needs an explicit mechanism if retained.

## 4. Open-PR overlap detection

**What:** When a new PR is opened, CI checks whether any other open PR touches
the same files. If so, a comment is posted naming the overlapping files and PRs.

**Enforcement:** CI workflow triggered on PR open/reopen. Compares the PR's
changed files against all other open PRs' changed files.

**Status:** DEFINED. Needs `pr-overlap-check.yml` workflow.

## 5. Required checks and independent review

**What:** Every ready PR must satisfy the scope-appropriate deterministic gate.
Sensitive changes additionally require exact-head risk approval and trusted
independent review; native UI changes require the product-acceptance contract.
Ordinary PRs do not acquire a model-review dependency merely by existing.

**Enforcement:**
- The default-branch ruleset requires the stable `policy-gate` and `merge-gate`.
- `merge-gate` requires Python/frontend/browser jobs only when the canonical
  changed-path classifier says they apply; docs-only PRs may skip code jobs.
- `policy-gate` reclassifies the live PR and requires exact-head approval plus
  trusted independent review for sensitive scope.
- Native UI source/public changes require the product-acceptance evidence block.

**Status:** ENFORCED for the current scope-aware policy. Broader independent
review of ordinary nonsensitive PRs is optional rather than a merge requirement.

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

1. **Platform-enforced (already working):** required `policy-gate` /
   `merge-gate`, pull-request and review-thread protection, deletion protection,
   non-fast-forward protection, and zero bypass actors. Strict branch
   up-to-date enforcement is **not** enabled.

2. **CI workflows to add (in order):**
   - `pr-single-lane-check.yml` — blocks second concurrent feature PR
   - `stale-draft-close.yml` — auto-closes stale drafts
   - `pr-overlap-check.yml` — detects file overlap between PRs
   - `ledger-coverage-check.yml` — verifies every planning file is in the ledger
   - `pr-model-origin-check.yml` — prevents self-review

3. **Procedural (no CI needed):**
   - Evidence requirements by type — enforced by PR review, not automation.
   - Active mission phase check — already satisfied by this roadmap.
