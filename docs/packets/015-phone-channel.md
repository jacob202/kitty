# Packet 015 — Phone channel: Kitty reaches Jacob

- **Status:** 📋 ready — executor-ready (authored 2026-07-04, supersedes the
  planned-level draft from earlier the same day). Top of Wave 1. Jacob is
  phone-first ("the only thing that would work would be an iOS alert — I'm
  always on my phone"); he has never used Kitty and every user-facing
  feature dies without this. See D12.
- **Best executor:** Claude Code or Codex — wiring over existing seams,
  test-heavy, no new architecture.
- **Purpose:** Anything Kitty needs Jacob to see — morning brief, deadline
  alert, "needs you" summary, a screenshot for review — lands on his iPhone
  as a push, proactively. "Show me, I'm not gonna go looking for this" is
  the contract (D12).

## Decisions already made (do not reopen)

- **Channel order: iMessage-to-self first, Pushover fallback** (D12).
  Both transports already exist — `gateway/imessage.py` (AppleScript send)
  and `gateway/notify.py` (complete Pushover client). This packet adds a
  façade and wiring, not transports.
- **Push to Jacob only.** One recipient, from env. Anything resembling
  messaging other people is `bulk.outbound` — T3, structurally absent.
- **Notifications carry summaries, never private content.** Counts, titles,
  one-line previews. Mail bodies / journal / health content (D10 local-only
  classes) never appear in a push payload — both channels transit third
  parties (Apple / Pushover).
- **Pushes are logged, not queued.** They are deliveries, not actions — no
  action-queue rows, no new tier kinds. Append-only `logs/push_log.jsonl`.

## Exact scope

1. **New `gateway/push.py`** — the single façade every caller uses:
   - `push_to_jacob(message, *, kind="info", title="Kitty", url=None,
     dedupe_key=None) -> bool`.
   - Channel resolution from env: `PUSH_CHANNELS` (default
     `imessage,pushover`), `PUSH_IMESSAGE_RECIPIENT` (Jacob's own number or
     Apple ID email; unset ⇒ iMessage channel disabled, loudly logged).
     Tries channels in order; first success wins.
   - Quiet hours from `config/user_profile.json` key `quiet_hours`
     (e.g. `"23:00-08:00"`, absent ⇒ none): `kind="info"` is deferred-
     dropped with a log line; `kind="alert"` bypasses (mirrors
     `notify.send_alert` semantics).
   - Dedupe: if `dedupe_key` was successfully pushed within 24 h (checked
     against the log tail), skip and return True with a `deduped` log line.
   - Every attempt appended to `logs/push_log.jsonl`:
     `{ts, kind, title, channel, ok, dedupe_key}`. No silent failure: if
     all channels fail, log at ERROR and return False.
2. **Use the verified targeting, and fix the newline bug.** Verified live
   on Jacob's Air 2026-07-04: the existing `imessage.send()` `buddy`
   targeting **fails silently** (exit 0, no message). This works:

   ```applescript
   tell application "Messages"
       set s to 1st account whose service type = iMessage
       send "hello from kitty" to participant "+1306…" of s
   end tell
   ```

   Two conditions, both already satisfied on the Air: Messages signed in,
   and a conversation with the recipient already exists (one manual
   self-text creates it — done during Wave 0). Rewrite `imessage.send()`
   to this shape.

   Separately, `imessage.send()` escapes `\n` as the two-character
   sequence `\\n`, which AppleScript renders literally. Multi-line pushes
   (the brief!) need real linefeeds — build the AppleScript string with
   `& return &` joins, or pass the text as an `osascript` argv argument
   (`on run argv`). Add a unit test with a stubbed `subprocess.run`
   asserting the generated script for a two-line message contains no
   literal `\n` sequence and uses `participant`, not `buddy`.
3. **Wire the brief:** in `gateway/brief_scheduler.generate_and_deliver_brief`,
   replace the direct `notify.is_configured()/send_brief()` block with
   `push.push_to_jacob(text, kind="info", title="Kitty Morning Brief")`.
   Behavior with nothing configured: WARN log, brief still logged — same
   as today, but the warning must name what's missing.
4. **Manual send path:** `./kitty push "message"` launcher subcommand (and
   `--alert` flag) so Wave-0 verification is one command from the Air.
5. **Doctor check:** `push:channel` — PASS when at least one channel is
   configured and the last logged attempt (if any) succeeded; WARN when
   none configured; FAIL when the last attempt failed. Follows the existing
   `Check(level, name, detail)` pattern in `gateway/doctor.py`.
6. **Document env vars** in `hermes.env.example`: `PUSH_CHANNELS`,
   `PUSH_IMESSAGE_RECIPIENT`, existing `PUSHOVER_USER_KEY` /
   `PUSHOVER_API_TOKEN`.

## Files likely touched

- New: `gateway/push.py`, `tests/test_push.py`.
- Edits: `gateway/imessage.py` (newline fix in `send` only),
  `gateway/brief_scheduler.py` (delivery block), `gateway/doctor.py`
  (one check), `kitty` launcher (subcommand), `hermes.env.example`.

## Files not to touch

- `gateway/notify.py` (works as-is; the façade calls it),
  `gateway/llm_client.py`, `gateway/action_queue.py`,
  `config/action_tiers.json`, anything Telegram, `imessage.read_recent`
  and below (read path is out of scope).

## Steps

1. `push.py` façade with injected channel callables + quiet-hours/dedupe
   logic → unit tests (no network, no osascript — stub both transports).
2. iMessage newline fix + script-generation test.
3. Brief scheduler swap → test that a generated brief reaches the stubbed
   façade exactly once.
4. Launcher subcommand → doctor check → env docs.

## Acceptance

- With both transports stubbed: channel order respected, fallback fires on
  first-channel failure, quiet hours defer `info` and pass `alert`, dedupe
  suppresses a repeat key within 24 h, every attempt lands in
  `logs/push_log.jsonl`, all-channels-down returns False and logs ERROR.
- The two-line-message AppleScript test proves no literal `\n` reaches
  osascript.
- Full suite green: `python3.12 -m pytest tests/ -q --tb=short`.
- **Live (Jacob's Air, post-Wave-0):** `./kitty push "hello from kitty"`
  arrives on the iPhone as an iMessage; `./kitty doctor --json` shows
  `push:channel` PASS.

## Verification commands

- `python3.12 -m pytest tests/test_push.py tests/ -q --tb=short`
- `./kitty push "hello from kitty"` (on the Air)
- `./kitty doctor --json | python3.12 -m json.tool` (see `push:channel`)

## Risks

- ~~AppleScript targeting brittleness~~ **resolved 2026-07-04:** the
  `participant … of (1st account whose service type = iMessage)` form is
  verified working on Jacob's Air (see scope item 2); `buddy` fails
  silently. Pushover remains the coded fallback if macOS updates break it.
- ~~Automation permission~~ **done 2026-07-04:** osascript → Messages
  permission already granted on the Air.
- **Notification spam kills the channel.** The façade ships with only the
  brief wired. 017's escalations and needs-you summaries arrive with their
  own packets and rate rules.

## Rollback

Revert the PR. `notify.py` untouched; the brief falls back to log-only
delivery. `push_log.jsonl` is inert.

## Unlocks

004's screenshot-review-by-push, 016's B-changed pushes, 017's deadline
escalations — every D12 delivery contract.

## Too broad if

- It grows two-way command parsing over iMessage, a message-reading
  feature, any second recipient, or a notification-preferences UI.

## Jacob reviews

- First live push: right channel, right feel, quiet-hours window right?
- Confirms `PUSH_IMESSAGE_RECIPIENT` value himself (his number/Apple ID —
  never an agent guess).
