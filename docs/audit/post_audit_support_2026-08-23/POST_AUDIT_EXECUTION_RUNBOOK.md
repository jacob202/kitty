# Kitty Post-Audit Execution Runbook

Purpose: operational checklist for implementing the completed audit without stale work, accidental scope growth, or false-green verification.

This runbook records current CI commands as of the repository state inspected on 2026-08-22. Re-read `.github/workflows/tests.yml` before executing future work because CI remains authoritative.

## 0. Preflight

From repository root:

```bash
pwd
git status --short --branch
git rev-parse HEAD
git log -8 --oneline --decorate
git fetch origin --prune
git status --short --branch
```

Then inspect relevant GitHub open PRs/issues and recent merges before choosing a finding.

Record:
- audit finding IDs;
- current HEAD;
- current branch/worktree;
- collision classification;
- exact target files;
- authoritative subsystem;
- original failure reproduction.

Do not begin edits while the target is IN FLIGHT elsewhere.

## 1. Reproduce first

Use the smallest deterministic reproduction possible.

For a High/Critical finding, preserve a regression test or executable reproduction that fails before the fix whenever feasible.
## 2. Current Python gates

Focused tests first, then the relevant broader gates.

Full CI-equivalent test suite:

```bash
python -m pytest tests/ -q --tb=short \
  --cov=gateway --cov-report=term-missing --cov-fail-under=73
```

Lint:

```bash
ruff check gateway/ tests/ mcp/ workers/ scripts/runpod_worker_smoke_test.py
```

Typecheck:

```bash
mypy gateway/ mcp/ workers/ scripts/runpod_worker_smoke_test.py
```

Do not blindly install/upgrade packages just to make a local environment match CI. If dependencies are missing, record the environment limitation or use the project's established environment.

## 3. Current native frontend gates

From `gateway/kitty-chat`:

```bash
npm ci
./node_modules/.bin/vitest run
node node_modules/next/dist/bin/next build
```

For vulnerability evidence:

```bash
npm audit --audit-level=high
```

Current CI treats this audit as advisory; changing that is an audit/remediation decision, not a runbook decision.
## 4. Browser / real-Gateway seam

Current CI runs Playwright after a production frontend build, then a hermetic browser → real Gateway → temporary DB seam.

Use the repository's current Playwright configs rather than recreating them manually.

Representative commands from current CI:

```bash
npx playwright test
npx playwright test --config playwright.hermetic.config.ts
```

The hermetic seam is especially important for findings where mocked frontend tests and backend unit tests could both pass while the contract between them is broken.

## 5. Hygiene evidence

Current CI also checks:

```bash
vulture gateway/ --min-confidence 80 --exclude gateway/kitty-chat/
deptry .
pip-audit
bandit -c pyproject.toml -r gateway/
```

At the inspected state, deptry, pip-audit, and Bandit are advisory in CI. Do not claim they are release gates unless remediation explicitly changes that.

TypeScript dead-code detection is not currently represented by the Python vulture gate; any future tool choice belongs to the completed audit's remediation plan.

## 6. Acceptance proof

After code-level gates, run the smallest applicable journey from:
`POST_AUDIT_ACCEPTANCE_AND_FAILURE_INJECTION_SPEC.md`.

For state-machine/restart fixes, unit tests alone are not sufficient. Include the relevant process/restart/failure-injection proof.
## 7. Pre-PR / pre-merge current-main check

Immediately before declaring the chunk ready:

```bash
git fetch origin --prune
git rev-parse HEAD
git rev-parse origin/main
git merge-base HEAD origin/main
git log --oneline --decorate HEAD..origin/main
git status --short
```

Inspect any new PR/issue touching the same semantics. If main changed the target behavior, rerun the original reproduction before rebasing/merging.

## 8. Evidence packet

For each chunk preserve:
- finding IDs;
- before SHA;
- after SHA;
- original failure output;
- regression test path;
- commands and results;
- acceptance journey/failure-injection result;
- relevant logs/screenshots/state snapshots;
- collision check result;
- rollback instructions;
- residual risk.

## 9. Rollback rule

Rollback should normally be a clean revert of one coherent implementation chunk. If rollback requires hand-editing durable state, the patch is too risky unless Chunk 11 explicitly justifies it and includes a tested migration rollback.

Database/schema changes need forward/backward compatibility or an explicit safe migration strategy before merge.

## 10. Completion rule

A chunk is complete only when the verified failure is removed AND the proof that would catch recurrence is preserved.

Passing unrelated tests is not evidence that the target defect is fixed. A green PR with an unverified product journey remains incomplete when the finding concerns product behavior.
