# OK-SECONDARY-01 — Every Supported Secondary Feature Has One Complete Journey

**Status:** draft candidate; not activated
**Roadmap phase:** 3 — companion completion
**Type:** integration/acceptance + bounded disposition packet

## Mission
Close the gap between “code exists” and “feature exists” for secondary Kitty surfaces without turning every historical experiment into product scope.

## Product acceptance moment
A reviewer can enumerate every currently reachable non-primary destination/capability and, for each one intended for Jacob, complete one useful end-to-end job. Anything not worth supporting is deliberately hidden/developer-only rather than left as a placeholder, dead redirect, or inert panel.

## Inventory source
Use current runtime/navigation/capability truth, not a hardcoded historical list. At minimum inspect currently registered/reachable examples such as Tutor, Research, Journal, Agents/agent sessions, todos/tasks, monitors, voice, provider/tool detail, Activity/Artifact overlays, and any legacy terminal/developer views.

## Rules
- Do not “save” a feature merely because backend code exists.
- Supported means: reachable for a product reason, one useful action/job works, state persists where claimed, one degraded path is truthful, and mobile/desktop layout is acceptable.
- Developer-only means intentionally hidden from normal navigation/search and clearly labelled when reached through an operator path.
- Retired means remove dead registration/redirect/CTA; do not leave PlaceholderView as final UI.
- If one feature needs material implementation, split it into a named child packet rather than widening this packet into a mega-PR.
- Reuse `KF-DEADEND-01` / `KT-UI-MOUNT-01` findings after revalidation.

## Verification
**Tier 1:** navigation registry/reachability tests plus focused tests for any bounded fixes made here.

**Tier 2:** desktop + iPhone-class running-app traversal of every supported secondary destination, one action per supported feature, plus direct-link/reload behavior.

**Tier 3:** independent reviewer produces a PASS/SPLIT/PARK disposition for each current secondary feature; this packet exits only when no visible placeholder/dead destination remains.

## Non-goals
- Building every archived experiment.
- Replacing primary-surface acceptance.
- One giant “fix everything secondary” change.

## Done when
Everything Jacob can discover in normal Kitty is either useful and working or intentionally not presented as a feature.
