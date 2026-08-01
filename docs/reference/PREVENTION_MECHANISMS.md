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
`pytest`, `lint`, `typecheck`, `hygiene`, `kitty-chat`, `browser-smoke`. All
must be `success` before merge. GitHub branch protection rule enforces this
at the platform level.

**Status:** ENFORCED. Branch protection is configured on GitHub.

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

**Enforcement:** GitHub branch protection "Require branches to be up to date
before merging." CI check verifies the base is within 48 hours of `origin/main`.

**Status:** PARTIALLY ENFORCED. "Up to date" check is platform-level.
Freshness check needs CI workflow.

## 4. Open-PR overlap detection

**What:** When a new PR is opened, CI checks whether any other open PR touches
the same files. If so, a comment is posted naming the overlapping files and PRs.

**Enforcement:** CI workflow triggered on PR open/reopen. Compares the PR's
changed files against all other open PRs' changed files.

**Status:** DEFINED. Needs `pr-overlap-check.yml` workflow.

## 5. Required checks and independent review

**What:** Every PR must pass all six CI jobs and receive an independent review
from a model other than the author.

**Enforcement:**
- CI: branch protection requires all six jobs.
- Review: PR Agent Review (#327) posts a review. A human or second model must
  approve. For T0 (safe) work: PR Agent Review pass is sufficient. For T1 work:
  separate model approval required. For T2 work: Jacob's approval required.

**Status:** PARTIALLY ENFORCED. CI jobs enforced by branch protection. Review
policy is defined but needs enforcement workflow for model-origin checks.

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

**Enforcement:** CI check reads PR body for evidence markers. For risky scope
(`risk/high`), the `pr-risk-guardrails.yml` workflow enforces `Manual approval: YES`
in the body.

**Status:** PARTIALLY ENFORCED. Risk guardrails exist. Evidence check needs
extension for non-risk evidence types (UI, restore, cost, cleanup).

## 10. Model origin tracking

**What:** Every PR must track which model authored it (from commit author:
`claude`, `codex`, `jacob202`, `copilot`, `dependabot`). A model may not
approve its own work.

**Enforcement:**
- PR description check identifies the author model.
- PR Agent Review identifies the reviewer model.
- CI gate prevents merge if author == reviewer model for T1+ work.

**Status:** DEFINED. Needs `pr-model-origin-check.yml` workflow.

---

## Implementation priority

1. **Platform-enforced (already working):** Red-main freeze (branch protection),
   required CI checks, branch up-to-date requirement.

2. **CI workflows to add (in order):**
   - `pr-single-lane-check.yml` — blocks second concurrent feature PR
   - `stale-draft-close.yml` — auto-closes stale drafts
   - `pr-overlap-check.yml` — detects file overlap between PRs
   - `ledger-coverage-check.yml` — verifies every planning file is in the ledger
   - `pr-model-origin-check.yml` — prevents self-review

3. **Procedural (no CI needed):**
   - Evidence requirements by type — enforced by PR review, not automation.
   - Active mission phase check — already satisfied by this roadmap.
