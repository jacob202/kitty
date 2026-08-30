# ADR 0035: Browser-Verified Evidence Required for UI Claims

**Date:** 2026-08-05
**Status:** Accepted

## Context

The BLUEPRINT.md (2026-07-11) established that "UI work isn't done until it's
seen working in a browser. No exceptions." The architecture honesty audit
(2026-07-24) found that the frontend had 9 of 16 views as PlaceholderView,
and that the documented UI architecture was "aspirational" rather than observed.

The feature reality audit (2026-07-28) formalized three states: Working (Jacob
can complete the intended workflow through the supported UI), Partial (code
exists but setup/UX blocks normal use), Planned (no end-to-end usable
implementation). This taxonomy was a correction to the earlier practice of
calling features shipped because backend code existed.

Multiple PRs were merged without browser verification, and the open-session
audit (2026-08-01) documented branches with 28 commits and 3 ratified ADRs that
never opened a PR — structural failures traceable to the gap between code
existence and browser evidence.

## Decision

No Kitty user-facing claim is accepted as true without independent browser
verification. The rule applies to:

- UI components: Must be observed rendering correctly in a browser (screenshot,
  Playwright trace, or live demo evidence). Code inspection is not sufficient.
- Product features: Must be verified through the supported UI end-to-end at
  least once before being marked Working in FEATURE_REALITY.md.
- Builder results: Artifact claims (generated file, PR opened, review passed)
  require independent cross-referencing against Git, GitHub, and Builder
  evidence, not just the worker's self-report.

Automated testing is encouraged (Playwright, vitest, browser-use) but does not
replace live verification of the integration. A Playwright test that passes
in CI does not prove the running app works on Jacob's Mac.

## Alternatives considered

**Code review is sufficient for UI changes:** Rejected. The BLUEPRINT's honesty
ledger proved that UI code can compile, pass tests, and still be a PlaceholderView
or render incorrect state. Browser observation is the only reliable verification.

**Only verify after merging:** Rejected. The pattern documented in open-session
audit (2026-08-01) showed that PRs merged without browser verification, then
subsequent work built on unverified assumptions. Verification must happen before
merge for user-facing changes.

## Evidence

- BLUEPRINT.md §7 (2026-07-11): "Each slice ships browser-verified or it
  isn't shipped."
- Architecture honesty audit (2026-07-24): "The documented UI architecture
  was aspirational."
- Feature reality audit (2026-07-28): Three-state taxonomy established.
- Open-session audit (2026-08-01): 28 commits, 3 ADRs on `docs/builder-
  cockpit-boundary` — never opened a PR. 8 RunPod commits on `claude/
  pr-review-48h-aptjw0` above the merge point — never opened a second PR.
- Open WebUI onboarding (2026-08-02): Live host execution revealed 4 defects
  that code review did not catch (PYTHONPATH contamination, pending-account
  trap, SSE smoke ambiguity, auth-disabled configuration drift).

## Consequences

- **Positive:** Reliable product. No shipped feature with hidden breakage.
  Clear acceptance criteria for every PR.
- **Negative:** Slower iteration. Browser verification takes time. Some
  features may remain Partial longer because full browser verification
  requires infrastructure (e.g., RunPod credentials for image generation).
- **Open question:** Should browser verification be a CI gate (blocking
  merge) or a review gate (required evidence in PR description)? The current
  approach is review gate; preventing merge without browser evidence would
  require a CI check.

## Risks

- The requirement becomes a bottleneck: Mitigated by prioritizing automated
  Playwright tests for regression coverage while requiring live verification
  only for new features and significant changes.

## Follow-up work

- Tag every route/component/test with its verification status (Working,
  Partial, Planned).
- Add browser-verification evidence section to PR template.
- Evaluate browser-use + Playwright for automated UI verification in CI.

## Related ADRs

- ADR 0032: Evidence-backed claims — no fabricated success
- ADR 0027/0033: Open WebUI shell boundary
