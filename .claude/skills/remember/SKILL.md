---
name: remember
description: Capture a durable preference from Jacob so it sticks across every future session. Triggers on "/remember <thing>", "from now on <thing>", "always <thing>", "stop <doing thing>". Writes to config/PREFERENCES.md, which is read back at the start of every session.
---

# /remember

Jacob is telling you to lock in a preference permanently. Unlike the scratchpad
(which waits for his review), this takes effect immediately.

## Steps

1. Take the preference text from the user's message. Strip the `/remember`
   prefix if present. Phrase it as a short imperative Kitty can act on later
   (e.g. "Default image gen to golden-hour lighting" not "I like golden hour").

2. Append it:

   ```bash
   python3 scripts/remember.py "<the preference, cleaned up>"
   ```

3. Confirm in one line what you stored, in Kitty's voice. Don't ceremony it.

## Notes

- One preference per call. If Jacob lists several, call once per item.
- If a new preference contradicts an existing line in `config/PREFERENCES.md`,
  say so and ask which wins before appending — don't silently stack opposites.
- This is for standing behaviour, not session state. "Where we left off" goes
  in the scratchpad, not here.
