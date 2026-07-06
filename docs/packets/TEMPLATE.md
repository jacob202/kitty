# NNN — Packet Title

**Status:** 📋 spec authored, not built
**Activation:** `idea_seed | decision | spec_candidate | active_packet | after_move_in | parked | reject`
**Best executor:** Claude Code / Codex / strongest-model prompt / Jacob / other
**Intent:** one sentence saying what changes for Jacob or Kitty

## Intake classification

- **Class:** choose one from the activation list above
- **Why this is not just an idea:** explain why this deserves packet shape
- **Why now / why later:** explain whether it serves H1 move-in or waits
- **Activation trigger:** for parked/after-move-in work, name the trigger

## Demo contract

After this lands, Jacob can see or do this concrete thing:

- [ ] visible proof, command output, phone notification, UI card, report, or review artifact

This is the human-visible finish line. Tests are not enough by themselves.

## Why this exists

Brief context. Name the user pain, missed opportunity, or product gap.

## Product principle

The rule this packet should preserve. Example:

> Capture comes back at the right moment, without asking Jacob to go hunting.

## Scope budget

- **Expected diff size:** small / medium / large
- **Expected files touched:** N
- **Stop and split if:** name the conditions that make this packet too broad
- **Do not expand into:** list tempting but forbidden adjacent work

## Privacy / sensitivity

- **Touches sensitive content?** yes / no
- **Content classes:** `chat`, `todo`, `calendar`, `journal`, `mail_body`, `health_admin`, `benefits`, `recovery_support`, `memory`, `none`
- **Cloud allowed?** yes / no / only after redaction
- **Forbidden:** list what must not be sent, stored, surfaced, or automated

## Files likely touched

- `path/to/file.py`
- `path/to/test_file.py`

## Files not to touch

- `path/to/forbidden_area.py`

## Implementation sketch

1. Step one.
2. Step two.
3. Step three.

Keep this executor-ready, not architectural fan fiction.

## Acceptance criteria

1. A concrete behavior changes.
2. The demo contract is satisfied.
3. Tests cover the new behavior or the packet explains why tests are not applicable.
4. Existing move-in bar work is not delayed unless the activation class is `active_packet`.
5. Privacy/sensitivity rules are enforced if relevant.

## Verification commands

```bash
python3.12 -m pytest tests/path_to_test.py -q
./kitty doctor --json
```

## Review artifacts

- screenshot / log / terminal output / phone notification / PR diff note

## Jacob review questions

1. Question that only Jacob can answer.
2. Another taste/priority question if needed.
3. Remove this section if Jacob review is not required.

## One-line build instruction

Give the executor one clean sentence that says what to build, where, and what not to expand into.
