# ADR 0028: Commodity Software Precedence over Custom Code

**Date:** 2026-08-05
**Status:** Accepted

## Context

Kitty's repository contains substantial custom infrastructure that duplicates
functionality available in mature open-source software. Examples identified in
the architecure migration analysis (2026-08-05) and repository simplification
audit (2026-08-05) include:

- Custom shell scripts for service management (`start_all.sh`, `stop_all.sh`,
  `status_all.sh`, `doctor.sh`) duplicated by the `./kitty` launcher.
- Custom chat UI (60+ components in `kitty-chat`) where Open WebUI already
  provides a mature chat shell with model selection, attachments, mobile, and
  persistence.
- Custom launchd plists duplicated by the `./kitty` launcher's service
  management.
- A task state machine (`builder_queue_db.py`, 470 lines) solving a problem
  that durable execution engines are designed for.
- Custom worktree isolation and worker lifecycle management where emerging
  projects (Ringer) target the same concern.

The BLUEPRINT.md (2026-07-11) and FOUNDATION_REPLACEMENT_STUDY (2026-07-27)
both identified this tension but did not codify a binding decision rule.

## Decision

When choosing between building custom code and adopting existing open-source
software for infrastructure concerns, Kitty applies this precedence:

1. **Adopt mature OSS as a dependency or replaceable shell** when it provides
   the capability without requiring Kitty to surrender authority over product
   decisions (memory policy, routing, personality, project ontology).

2. **Build custom code only when** the capability is Kitty's unique product
   differentiation (context assembly, capability manifest, resume loop,
   personality, life-first ordering) and no mature OSS provides it.

3. **A candidate is disqualified** if adopting it requires Kitty to maintain
   two competing sources of truth for the same concern (e.g., routing,
   memory, permissions, project state).

Already applied:
- Open WebUI as replaceable chat shell (ADR 0027).
- LiteLLM as provider abstraction (kept, never rebuilt).
- `./kitty` launcher superseding scattered shell scripts.
- `assistant-ui` as component foundation rather than building a chat widget
  from scratch.

## Alternatives considered

**Build all infrastructure from scratch:** Rejected. The foundation replacement
study demonstrated that full-app plumbing (auth, files, providers, agents,
settings, mobile) would require years of maintenance without proportional user
value.

**Adopt any OSS regardless of license or authority conflict:** Rejected.
Open WebUI's custom license prevents forking but not shell use. A candidate
that demands competing memory, routing, or project authority is rejected
regardless of feature completeness (LibreChat and AnythingLLM remain unevaluated
for this reason in the spike).

## Evidence

- FOUNDATION_REPLACEMENT_STUDY_2026-07-27.md: Evaluated 3 candidate shells
  against 7 real-workflow criteria.
- Architecture migration analysis (2026-08-05): Identified ~11,400 lines of
  custom code duplicating solved infrastructure problems.
- Repository simplification audit (2026-08-05): Identified 43 dead files
  that were custom code superseded by `./kitty` or never wired.
- ADR 0027: Established Open WebUI as replaceable shell with clear boundaries.
- REPO_SCOUTING_2026-07-24.md: Catalogued existing OSS for news, monitoring,
  browser testing, iMessage, email.

## Consequences

- **Positive:** Lower maintenance burden. Faster feature delivery. Upstream
  improvements inherited automatically. Smaller codebase.
- **Negative:** Dependency risk (upstream can change or abandon).
  Open WebUI's custom license means version pinning is essential. Some
  integrations remain one-way (Open WebUI receives Kitty models/tools; Kitty
  doesn't receive Open WebUI state).
- **Open question:** When Open Brain, Ringer, and Open Engine mature, whether
  to migrate infrastructure to them or keep current implementations.

## Risks

- Open WebUI license changes or project abandonment: mitigated by the ADR 0027
  replaceable-shell boundary. Kitty Console (Next.js) remains as fallback.
- Open Brain/Ringer/Open Engine never mature: mitigated by never having
  deleted working infrastructure in anticipation.

## Follow-up work

- Complete Open WebUI onboarding baseline (PR #384: PYTHONPATH sanitization,
  pending-account fix, SSE smoke repair).
- Evaluate Open Brain/Ringer/Open Engine maturity annually.

## Related ADRs

- ADR 0027: Open WebUI as replaceable daily-driver shell
- ADR 0003: Gateway is the product
- ADR 0017: Kitty → Mission → KittyBuilder control plane
