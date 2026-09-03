# OK-COMPANION-01 — Capture → Resurface → Brief/Push Works as One Life-First Loop

**Status:** draft candidate; not activated
**Roadmap phase:** 3 — companion completion

## Mission
Prove the personal-assistant loop that matters outside the app: capture something quickly, turn it into durable useful context/action, resurface it at the right time, and deliver important output to the phone truthfully.

## Depends on
- Existing capture/inbox/state/deadline/brief/push authorities.
- `KT-DEADLINE-01` and `KT-AUTO-01` where their delivery truth fixes remain current.
- Phone access/push channels must be current-runtime verified.

## Product acceptance moment
Capture a real note/photo/file from the phone path, see it enter the right durable place, have a deadline/next action extracted when appropriate, see it resurface in Home/Chat/brief at the right time, and receive the important notification/brief on the phone. Healthy “nothing urgent” and delivery unavailable are both truthful.

## Required behavior
- Capture receipt says what was accepted and where it went; no silent drop.
- Extraction/enrichment failure preserves the original capture and remains recoverable.
- Deadlines/actions are created only through existing governed authorities and are inspectable/correctable.
- Resurfacing is relevance/time based and avoids duplicate nagging.
- Brief/push marks delivery only when a configured channel actually accepted it.
- Quiet hours/dedupe/approval rules remain intact.
- A phone-originated item can be opened/continued from the canonical desktop/iPhone product surface without copying IDs.

## Verification
**Tier 1:** capture/inbox/deadline/brief/push tests including enrichment failure and delivery-unavailable cases.

**Tier 2:** live phone + desktop/iPhone-class product proof where practical; hermetic delivery fixtures may support development but cannot prove the actual phone-delivery claim.

**Tier 3:** independent reviewer validates capture persistence/resurfacing and current phone delivery on exact runtime evidence; paid provider calls require separate authorization.

## Non-goals
- A new notification service.
- Always-on surveillance/context collection.
- Adding more channels merely for coverage.

## Done when
Kitty reliably closes the loop from “I threw something at it” to “it came back when useful,” with delivery truth that Jacob does not have to second-guess.
