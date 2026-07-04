# Packet 015 — Phone channel: Kitty reaches Jacob

- **Status:** 🧭 planned — needs an executor-ready authoring pass before
  hand-off. Highest priority of the new wave: Jacob decided 2026-07-04 that
  he is phone-first ("the only thing that would work would be an iOS alert —
  I'm always on my phone"). Telegram is dead (he never opens it), email gets
  buried. Every user-facing feature in this plan dies without this packet.
- **Best executor:** Claude Code / Codex — mostly wiring; the seams exist.
- **Purpose:** Anything Kitty needs Jacob to see — morning brief, deadline
  alert, "needs you" approval, a screenshot for review — lands on his iPhone
  as a push, proactively. He never has to go looking. "Show me, I'm not
  gonna go looking for this" is the contract.

## What already exists (do not rebuild)

- `gateway/notify.py` — working Pushover client (`send`, `send_brief`,
  `send_alert`, `is_configured`; env `PUSHOVER_USER_KEY` /
  `PUSHOVER_API_TOKEN`).
- `gateway/imessage.py` — iMessage send/read via AppleScript
  (`send(phone_or_email, message)`).
- `gateway/brief_scheduler.py` — already calls `notify.send_brief` when
  configured.

## Channel decision (Jacob confirms at authoring time)

Two viable paths, both already coded at the transport level:

1. **iMessage-to-self** (recommended first try): free, native blue bubble,
   works from the headless Mac if Messages is signed in. Risk: AppleScript
   brittleness, and macOS may need one-time Automation permissions granted
   with a screen attached (do this before the Air goes headless).
2. **Pushover**: already integrated, very reliable, ~US$5 one-time for the
   iOS app. If iMessage-to-self fights back for more than an hour, spend
   the five bucks. Budget is math.

## Scope sketch (for the authoring pass)

- One façade: `push_to_jacob(text, kind, url=None)` that routes to the
  configured channel (iMessage → Pushover fallback), logs every push, and
  fails loud into doctor when neither channel works.
- Wire the callers: brief scheduler (exists), deadline alerts (packet 017),
  "needs you" queue summaries (counts + top item, never full private
  content in a notification), and review-artifact delivery (e.g. the 004
  screenshot goes TO him as a message, replacing "Jacob goes looking").
- Quiet hours + dedupe (no double-push of the same signal).
- Doctor check: channel configured and last push succeeded.
- **Inbound half (Jacob setup task, agent verifies):** Tailscale on the Mac
  + iPhone (free, ~15 min) so the Siri shortcut capture path
  (`docs/SIRI_SHORTCUT.md`) reaches the home gateway from anywhere. Capture
  from phone is what makes "capture that comes back" real for a phone-first
  user.

## Dependencies

None on other open packets. Wave 0 (the Air online via ethernet) must be
done for pushes to originate from home.

## Acceptance sketch

- Morning brief arrives on the iPhone unprompted.
- A test deadline signal produces a push within one cron cycle.
- With both channels unconfigured, doctor goes red and the failure is
  logged — no silent nothing.

## Jacob reviews

- Channel choice (iMessage vs Pushover) after the first live test.
- Quiet hours and what classes of events warrant a push vs waiting for the
  brief.

## Too broad if

- It grows two-way command parsing over iMessage, per-contact messaging, or
  any outbound to anyone who isn't Jacob (that's `bulk.outbound`, T3,
  structurally absent).
