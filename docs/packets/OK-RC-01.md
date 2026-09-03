# OK-RC-01 — Personal Release-Candidate Certification

**Status:** draft candidate; not activated
**Roadmap phase:** 6 — personal release candidate
**Type:** verification/soak gate, not a feature packet

## Mission
Freeze feature scope long enough to prove that Kitty is release-quality for Jacob as one running product.

## Hard dependencies
- `OK-PASS-01` complete on the candidate.
- Primary surface closure packets complete.
- Runtime/security/recovery blockers required by `docs/ROADMAP.md` are closed.
- No known P0/P1 blocker is deliberately deferred into this gate.

## Candidate rule
Bind the certification to one exact clean source SHA/build identity. A rebuild from dirty/unattributed source, hidden branch change, or materially different runtime invalidates the receipt and requires a new candidate.

## Certification matrix
At laptop and iPhone-class widths, independently exercise:
- Home: continue/needs-you/upcoming/active action.
- Chat: normal reply, tool use where supported, retry/interruption recovery, structured object reference.
- Work: start/control/recover/open result.
- Projects: resume/next step/related work-or-artifact/Ask Kitty.
- Image Lab: create/refine/result with authorized live provider proof where required.
- Library: ingest/find/open/use plus degraded indexing/source case.
- Automations: edit/enable/run/history/failure recovery.
- Settings: persistence and unavailable capability/integration truth.
- Supported secondary features from `OK-SECONDARY-01`.
- Backup/restore.
- Service restart and one provider/network/dependency degraded case.
- Real iPhone/Tailnet path.

## Quality bar
- Zero known P0/P1 product-trust, data-loss, security-boundary, primary-journey, or accessibility blocker.
- No dead primary control, raw server error as the primary message, unexplained unknown state, clipped/obscured primary control, or document-level horizontal overflow.
- No supported primary workflow requires a terminal/manual internal ID/manual cross-agent relay.
- No candidate-only test fixture is used to claim a real external delivery/provider/phone outcome.
- Console/page errors during acceptance are either zero or explicitly understood non-product noise with no user effect; unknown errors fail the gate.

## Dogfood soak
After independent matrix acceptance, Jacob uses the exact candidate during normal days. Bugs become bounded repair packets. Feature ideas are captured/parked and do not reopen the candidate unless they expose a missing required journey.

The soak exits when normal supported use no longer causes routine fallback to terminal/manual agent coordination and no new P0/P1 blocker appears. Do not invent a calendar duration if real use provides enough evidence sooner; do not call one staged demo a soak.

## Evidence
Record exact source/build SHA, runtime manifest/provenance, commands/checks, viewport/device, journey outcomes, degraded paths, backup/restore proof, independent reviewer identity/tool, and every remaining limitation.

## Non-goals
- Public distribution packaging/legal/compliance.
- New features during certification.
- Hiding defects to protect a release date.

## Done when
The exact candidate has independent whole-product evidence and survives real use well enough that “Kitty is ready” describes the product Jacob actually runs, not a test suite or roadmap aspiration.
