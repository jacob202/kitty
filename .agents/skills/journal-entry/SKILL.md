---
name: journal-entry
description: Run a guided journal interview and save the synthesized entry. Use when the user wants to log a thought, feeling, or event.
---

This is a conversation, not a single store call — `gateway/routes/journal.py`
has no fixed-format "save this entry" endpoint.

## Flow

1. `GET /journal/prompt?theme=<optional>` — get an opening writing prompt.
2. `POST /journal/start?theme=<optional>` — returns `{opener, system_prompt, theme}`.
3. Loop `POST /journal/chat` with `{messages, system_prompt}` as the user talks; append each turn.
4. When the user's done, `POST /journal/synthesize` with `{messages, theme, session_id}` —
   the gateway calls the LLM itself to write the first-person entry and saves it
   via `gateway.journal.save_journal_entry`. Returns `{entry}`.

No client-side mood/topic extraction — synthesis happens server-side in step 4.
