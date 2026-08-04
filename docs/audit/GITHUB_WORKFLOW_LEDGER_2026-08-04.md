# GitHub Workflow Ledger — 2026-08-04

**Registry records:** 51 active  
**Workflow files on `main`:** 12 before this change; 11 after retiring age-based stale closure  
**GitHub-managed dynamic workflows:** 4  
**Registry-only records whose file is absent from `main`:** 35

GitHub's Actions registry retains an `active` record after a workflow file is removed. Therefore `51 active workflows` did not mean 51 runnable YAML files. This ledger separates current code, GitHub-managed workflows, and historical registry clutter.

## Current repository workflows

| ID | Path | Trigger / resource boundary | Disposition |
|---:|---|---|---|
| 293558902 | `.github/workflows/tests.yml` | Push/PR deterministic CI | **Retain; required gate candidate** |
| 320045964 | `.github/workflows/pr-agent-review.yml` | PR-triggered OpenRouter review; can consume API credits | Retain for current independent-review policy; cost remains explicit governance risk |
| 300373197 | `.github/workflows/pr-description-check.yml` | PR metadata, GitHub token only | Retain |
| 324188090 | `.github/workflows/pr-auto-label.yml` | PR metadata, GitHub token only | Retain |
| 324188091 | `.github/workflows/pr-release-evidence.yml` | PR evidence validation | Retain |
| 324188093 | `.github/workflows/pr-risk-guardrails.yml` | PR path/risk validation | Retain |
| 324188094 | `.github/workflows/pr-test-hints.yml` | PR test guidance | Retain; advisory, not a merge proof |
| 323977647 | `.github/workflows/opencode.yml` | Explicit `/oc` or `/opencode` comment; uses `OPENCODE_API_KEY` | Retain only as explicit command path; never automatic |
| 324782744 | `.github/workflows/runpod-image-build.yml` | Manual or one named feature branch; builds GHCR image, no GPU | Retain; current image infrastructure, unchanged here |
| 324261076 | `.github/workflows/runpod-james-live.yml` | Manual only; real paid GPU with hard rate/runtime limits and cleanup | Retain manual-only; never add automatic trigger without separate approval |
| 324772025 | `.github/workflows/runpod-template-diag.yml` | Manual CPU/API diagnostic; uses RunPod secret | Retain manual-only |
| 324188095 | `.github/workflows/stale.yml` | Weekday schedule; auto-closes inactive issues/PRs | **Remove in this PR** — age is not evidence of completion or irrelevance |

The three current RunPod/image workflows and all image Git history are untouched by this cleanup.

## GitHub-managed dynamic workflows

| ID | Path | Disposition |
|---:|---|---|
| 323936466 | `dynamic/agents/copilot-pull-request-reviewer` | GitHub-managed; review separately from repository YAML |
| 323905733 | `dynamic/agents/openai-code-agent` | GitHub-managed; keep disabled from autonomous merge/spend paths unless explicitly invoked |
| 323885798 | `dynamic/copilot-swe-agent/copilot` | GitHub-managed; review account-level enablement and permissions |
| 306351402 | `dynamic/dependabot/dependabot-updates` | Retain; security/dependency automation, with each PR reviewed independently |

## Registry-only historical workflows — non-image

The following records have no corresponding file on current `main`. Their triggers, permissions, secrets, and exact last meaningful run cannot be reconstructed from current code and therefore must not be treated as active capability. Disabling the registry record preserves Git history and past run logs.

| ID | Historical path | Disposition |
|---:|---|---|
| 322024308 | `.github/workflows/align-agentrouter-org.yml` | Disable registry record |
| 320615768 | `.github/workflows/align-governance-tests-once.yml` | Disable registry record |
| 321993237 | `.github/workflows/diagnose-dogfood-frontend.yml` | Disable registry record |
| 320602800 | `.github/workflows/diagnose-first-pytest-failure-once.yml` | Disable registry record |
| 320619681 | `.github/workflows/diagnose-governance-pytest-once.yml` | Disable registry record |
| 320599994 | `.github/workflows/diagnose-pip-once.yml` | Disable registry record |
| 320608577 | `.github/workflows/diagnose-playwright-once.yml` | Disable registry record |
| 320601917 | `.github/workflows/diagnose-pytest-once.yml` | Disable registry record |
| 321978278 | `.github/workflows/dogfood-repair-apply.yml` | Disable registry record |
| 321980077 | `.github/workflows/dogfood-repair-run.yml` | Disable registry record |
| 321991274 | `.github/workflows/finalize-dogfood-recovery-v2.yml` | Disable registry record |
| 321994929 | `.github/workflows/finalize-dogfood-recovery-v3.yml` | Disable registry record |
| 321989913 | `.github/workflows/finalize-dogfood-recovery.yml` | Disable registry record |
| 321950493 | `.github/workflows/foundation-prototype-diagnostic.yml` | Disable registry record |
| 320599232 | `.github/workflows/regen-ci-lock-once.yml` | Disable registry record |
| 320615121 | `.github/workflows/repair-context-receipt-once.yml` | Disable registry record |
| 320616728 | `.github/workflows/restore-governance-scope-once.yml` | Disable registry record |
| 321946516 | `.github/workflows/ruff-diagnostic.yml` | Disable registry record |
| 322100866 | `.github/workflows/runtime-truth-pr-runner.yml` | Disable registry record |
| 322097889 | `.github/workflows/runtime-truth-repair.yml` | Disable registry record |
| 320612466 | `.github/workflows/sync-main-once.yml` | Disable registry record |
| 320622565 | `.github/workflows/verify-ktf-free-exec-once.yml` | Disable registry record |

## Registry-only historical workflows — RunPod/image lane

These 13 records also have no file on current `main`. They are documented but not mutated by this PR. Any later registry disable must preserve run logs and must not rewrite image Git history or remove the three current manual/bounded RunPod workflows.

| ID | Historical path | Disposition |
|---:|---|---|
| 324376069 | `.github/workflows/capture-direct-rest-patch.yml` | Registry disable candidate after image-workflow review |
| 324376740 | `.github/workflows/fix-direct-rest-patch-runner.yml` | Registry disable candidate after image-workflow review |
| 324375354 | `.github/workflows/report-direct-rest-patch.yml` | Registry disable candidate after image-workflow review |
| 324380648 | `.github/workflows/report-direct-rest-run.yml` | Registry disable candidate after image-workflow review |
| 324374735 | `.github/workflows/runpod-apply-direct-rest-fix.yml` | Registry disable candidate after image-workflow review |
| 324367167 | `.github/workflows/runpod-apply-explicit-reset-fix.yml` | Registry disable candidate after image-workflow review |
| 324365383 | `.github/workflows/runpod-apply-startup-fix-trigger.yml` | Registry disable candidate after image-workflow review |
| 324364145 | `.github/workflows/runpod-apply-startup-fix.yml` | Registry disable candidate after image-workflow review |
| 324373628 | `.github/workflows/runpod-clean-current-smoke.yml` | Registry disable candidate after image-workflow review |
| 324384644 | `.github/workflows/runpod-fix-null-template.yml` | Registry disable candidate after image-workflow review |
| 324386485 | `.github/workflows/runpod-fix-omit-template.yml` | Registry disable candidate after image-workflow review |
| 324371269 | `.github/workflows/runpod-live-probe.yml` | Registry disable candidate after image-workflow review |
| 324371939 | `.github/workflows/runpod-reset-active-smoke.yml` | Registry disable candidate after image-workflow review |

## Enforcement configuration

The stable required check names observed on current PRs are:

- `pytest`
- `lint`
- `typecheck`
- `hygiene`
- `kitty-chat`
- `browser-smoke`

`PR Description Check`, `PR Agent Review`, and risk/evidence workflows are separate policy checks. Before making any of them required, prove their trigger and result name are stable on human and Dependabot PRs.

Recommended default-branch rules:

- block deletion and force pushes;
- require the six deterministic checks above;
- require branches to be current with `main` when GitHub can provide a stable merge test;
- allow no broad administrator bypass for routine merges;
- do not require a paid/model review check until its cost, availability, and failure semantics are acceptable;
- prove enforcement with a deliberately failing PR whose merge is blocked.

## Connector limitation

The connected GitHub actions available during this pass can edit repository files but do not expose workflow-registry disablement, ruleset mutation, security-alert enablement, or branch-ref deletion. Those mutations were not falsely claimed. This ledger provides the exact IDs and configuration needed for a later admin/API operation.
