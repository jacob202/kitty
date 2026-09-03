# OK-SETTINGS-01 — Settings Actually Controls Kitty

**Status:** draft candidate; not activated
**Roadmap phase:** 2 — primary surfaces

## Mission
Make Settings a coherent control surface where every exposed preference/integration changes the real owning subsystem, persists when promised, and explains unavailable capability without operator jargon.

## Depends on
- `KH-CAPABILITY-01` for unified capability health where applicable.
- `KF-TELOS-01` for editable identity/mission context where still current.
- `KT-BACKUP-UI-01` may live in or link from Settings once its restore dependency is safe.

## Product acceptance moment
Change the settings Jacob actually cares about—theme/display, model/provider preference, personalization/TELOS, relevant integration/capability state—and see the effect persist after reload/restart. A missing credential/service shows a plain-language unavailable state and one real next action instead of a green toggle or raw environment name.

## Required behavior
- Every editable setting has one authoritative persistence path; no decorative toggles.
- Saved model/provider preference affects the actual picker/routing path and reflects unavailable selections honestly.
- Theme/accessibility display preferences update immediately and persist according to their contract.
- Personalization/TELOS edits are inspectable and bounded; sensitive context is not surfaced merely because Settings is open.
- Integrations/capabilities use installed/configured/available/launchable/degraded truth rather than “plugin exists” guesses.
- Settings that require terminal/env/credential work explain the concrete user action without exposing secret values.
- Backup/restore, diagnostics, and advanced operator controls are grouped as advanced/maintenance, not mixed into normal personalization.
- Unknown is not rendered as off/healthy.

## Verification
**Tier 1:** Settings/component/client tests plus changed backend preference tests; TypeScript and focused persistence regressions.

**Tier 2:** desktop + iPhone-class running app: change and reload/restart one preference in each supported category; exercise one unavailable integration/capability state.

**Tier 3:** independent reviewer confirms that visible settings all have observable effects or explicit unsupported/unavailable semantics.

## Non-goals
- A generic public-user onboarding wizard.
- Building account/multi-user administration.
- Exposing raw `.env` editing.

## Done when
Settings contains no control whose effect Jacob has to guess, and normal personalization/provider/integration decisions can be understood and changed without terminal knowledge.
