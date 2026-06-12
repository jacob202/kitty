# Mobile Companion Phase 1.5

**Status:** Design only. Do not build the mobile app during Desktop Phase 1.

## Purpose

The first mobile companion should be a tiny capture surface, not Kitty chat on
a phone. Its job is to get thoughts and evidence into Kitty's inbox when Jacob
is away from the Mac.

Desktop Phase 1 must prove daily use first:

- Kitty starts after login.
- `Command+Shift+K` opens it.
- Quick Capture is dependable.
- The local inbox is useful because Kitty resurfaces captures without a manual
  review ritual.

Mobile implementation starts only after those checks pass in normal use.

## Phase 1.5 Scope

- Quick text capture
- Voice note capture
- Photo capture
- File capture
- **I'm spiraling** button
- **What am I avoiding?** button
- Authenticated inbox delivery into Kitty

## Explicitly Out

- Full chat
- Streaming AI responses
- Complex memory editing
- Agent dashboard
- Background agent control
- Push notifications
- Always-listening voice assistant mode
- App Store release work
- General cloud hosting
- TELOS, PAI, specialist, agent, or MCP expansion

## Shared Capture Contract

All clients produce the same required base fields:

```json
{
  "id": "uuid",
  "created_at": "2026-06-12T12:00:00Z",
  "source": "mobile_text_capture",
  "type": "text",
  "text": "Call the shop about the Sansui parts.",
  "processed": false,
  "project": null,
  "tags": []
}
```

Required behavior:

- The client generates the UUID before upload.
- Retry sends the same UUID.
- Kitty deduplicates imports by UUID.
- Mobile timestamps are UTC RFC 3339.
- Imported records are appended to `data/inbox.jsonl`.
- Unknown additive fields are preserved when possible.
- `data/inbox.jsonl` remains an immutable intake log.

Phase 1 desktop records use `source: "desktop_quick_capture"` and
`type: "text"`.

Future mobile sources:

- `mobile_text_capture`
- `mobile_voice_capture`
- `mobile_photo_capture`
- `mobile_file_capture`
- `mobile_distress_button`

Future attachment records may add an optional `attachments` array. That field
is not implemented in Desktop Phase 1.

The required `processed: false` value describes capture creation state. Future
processing writes status events keyed by capture ID to
`data/inbox_receipts.jsonl`; it does not rewrite the original capture line.

## Button Behavior

### I'm spiraling

Create a normal inbox record:

```json
{
  "source": "mobile_distress_button",
  "type": "text",
  "text": "I'm spiraling.",
  "tags": ["spiraling", "needs_follow_up"]
}
```

The first mobile version confirms capture. It does not start a live AI session,
send a push notification, or claim to provide emergency support.

This button is not implementation-ready until Desktop Phase 1 proves sensitive
next-open resurfacing. A distress capture that is merely stored is a broken
product contract, even if sync technically succeeds.

### What am I avoiding?

Open a one-question capture screen:

```text
What are you avoiding right now?
```

Save the answer as:

```json
{
  "source": "mobile_text_capture",
  "type": "text",
  "text": "...",
  "tags": ["avoidance_prompt"]
}
```

## Sync Shape

Do not implement sync in Desktop Phase 1. Preserve this boundary:

```text
mobile outbox
    |
    | authenticated batch upload
    v
Kitty inbox import endpoint
    |
    | deduplicate by id
    v
data/inbox.jsonl
```

The future endpoint should:

- Accept a small batch of capture records.
- Validate the shared JSON Schema.
- Return accepted, duplicate, and rejected IDs.
- Be idempotent.
- Require explicit authentication.
- Use HTTPS if traffic leaves the device.
- Use the same advisory lock as desktop capture before appending JSONL.

## Auth Assumption

Desktop Phase 1 remains loopback-only and does not expose the gateway to the
LAN. Mobile Phase 1.5 must choose its transport before implementation:

1. Same-network direct connection with explicit pairing and TLS.
2. User-controlled relay or tunnel.
3. Small hosted inbox relay containing captures only.

For a single-user first implementation, a user-controlled tunnel such as
Tailscale is the leading candidate because it avoids inventing public cloud
identity and pairing infrastructure. This is a design preference, not a Phase
1 commitment. Verify transport and threat model after desktop daily-use
acceptance. Do not add cloud auth to Desktop Phase 1 in anticipation.

## Offline Behavior

The mobile client keeps a local outbox:

- New capture is immediately saved locally.
- Upload retries later.
- Successful upload stores the server acknowledgment.
- The record is not regenerated on retry.
- The user can see pending and failed capture counts.

## Privacy

- Captures are private by default.
- Photos, files, and audio require explicit user action.
- Do not upload the broader mobile photo library, contacts, messages, or
  location history.
- Do not send capture contents to an AI provider as part of sync.

## Start Gate

Mobile implementation may begin only when:

- Desktop Kitty has passed the reboot acceptance test.
- Quick Capture has been used successfully in daily life.
- `InboxAdapter` and sensitive resurfacing behavior have proven useful for
  incoming captures.
- The sync transport and threat model have been explicitly chosen.

Until then, mobile remains planned, not built.
