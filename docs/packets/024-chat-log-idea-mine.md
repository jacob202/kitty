# 024 — Chat Log Idea Mine

> Renumbered from 022 on 2026-07-05: that number was already assigned by the
> registry to Magic Kitty (D13). The README registry table owns packet
> numbering — check it before naming a new packet file.

**Status:** 📋 spec authored, not built
**Best executor:** strongest-model prompt + Claude Code/Codex for implementation
**Intent:** turn Jacob’s long chat history into an organized idea/project mine without turning every emotional trace into permanent personality memory.

## Why this exists

Jacob realized the chat log is a gold mine: unfinished projects, half-built ideas, product decisions, prompts, job directions, creative sparks, aesthetic preferences, names, plans, constraints, and “wait, that was actually good” moments are scattered across conversation history.

This packet turns that mess into a controlled extraction pipeline.

The goal is not to memorize Jacob’s entire past. The goal is to recover useful threads.

## Product principle

Chat history should become:

- an **idea archive**
- a **project continuation map**
- a **decision recovery system**
- a **creative spark library**
- a **prompt/workflow library**
- a **parking lot for maybe-later ideas**

It should not become:

- a psych profile
- a recovery surveillance log
- a pile of stale facts surfaced forever
- a shame archive
- a reason Kitty keeps pulling Jacob backward

The key distinction:

> Memory is for continuity in the present. The chat-log mine is for recovering useful threads from the past.

## Relationship to packet 023 (memory taste)

Packet 023 defines the memory taste policy: continuity, not surveillance.

This packet depends conceptually on 023 but does not require all 023 code to exist first if implemented as an offline/manual import tool.

If 023 is not built yet, this packet must still obey its design rules:

- sensitive/recovery material is quiet by default
- extracted items need categories and review states
- nothing gets injected into always-on memory without Jacob approval
- creative/project/opportunity threads are preferred over emotional repetition

## Inputs

Possible sources:

1. exported ChatGPT conversations
2. Claude/Codex/OpenCode transcript folders
3. repo session logs and handoff docs
4. manually pasted long chat sections
5. future Kitty chat logs once Kitty is in daily use

No cloud upload should be required for local transcripts unless Jacob explicitly chooses it.

## Output objects

Create an extraction schema with these object types:

### `project_thread`

A concrete project Jacob has returned to or may want to continue.

Fields:

- `title`
- `one_line`
- `status`: `active`, `parked`, `someday`, `stale`, `done`, `unknown`
- `domain`: `kitty`, `career`, `creative`, `health`, `home`, `vehicle`, `audio`, `ai_image`, `recovery_support`, `admin`, `learning`, `other`
- `why_it_matters`
- `last_known_state`
- `next_small_move`
- `evidence_refs`
- `sensitivity`: `normal`, `personal`, `sensitive`, `quiet`
- `user_review`: `unreviewed`, `approved`, `edited`, `rejected`, `keep_quiet`

### `idea_seed`

A loose spark that is not yet a project.

Fields:

- `title`
- `spark`
- `possible_use`
- `domain`
- `energy`: `high`, `medium`, `low`, `unknown`
- `risk`: `rabbit_hole`, `money`, `emotional`, `technical`, `none`
- `next_small_move`
- `evidence_refs`
- `user_review`

### `decision_recovered`

A decision Jacob already made that should not be re-litigated forever.

Fields:

- `decision`
- `context`
- `why`
- `date_or_period`
- `applies_to`
- `reopen_condition`
- `evidence_refs`
- `user_review`

### `preference_or_taste`

A stable preference that improves future help.

Fields:

- `preference`
- `applies_to`
- `strength`: `strong`, `medium`, `weak`, `experimental`
- `avoid`
- `examples`
- `evidence_refs`
- `user_review`

### `prompt_or_workflow`

Reusable prompt, workflow, checklist, or tool pattern.

Fields:

- `name`
- `purpose`
- `template`
- `when_to_use`
- `inputs_needed`
- `output_expected`
- `evidence_refs`
- `user_review`

## Extraction rules

1. Extract useful continuity, not every fact.
2. Prefer projects, decisions, prompts, workflows, taste, constraints, and next moves.
3. Treat recovery/mental-health/personal pain as sensitive by default.
4. Do not generate psychological interpretations unless Jacob explicitly asked for that in the source.
5. Every extracted item must include evidence refs to source transcript/file/date if available.
6. Every extracted item starts as `unreviewed`.
7. No extracted item becomes always-on memory until Jacob reviews or explicitly approves it.
8. Stale project threads should be preserved as `parked` or `someday`, not surfaced as current obligations.
9. If an idea is exciting but dangerous for focus, label the risk honestly.
10. Keep weird creative sparks weird. Do not sanitize them into bland productivity notes.

## Review UX

The first useful UI does not need to be fancy. It can be a simple review queue:

- “Keep active”
- “Park it”
- “Someday”
- “Reject”
- “Merge with...”
- “Keep quiet”
- “Turn into next step”

Review cards should show:

- title
- one-line summary
- why it might matter
- evidence snippet/source
- suggested next tiny move
- risk label if any

## Storage approach

Do not create a new memory substrate.

Use a new SQLite-backed module or existing knowledge/collections path, depending on current packet 008 remainder state.

Preferred eventual table/module:

- `gateway/idea_mine_store.py`
- table: `idea_mine_items`
- rows include `object_type`, `payload_json`, `source_ref`, `user_review`, `created_at`, `updated_at`

This should emit signals only after review or when an item is explicitly marked active.

## Implementation sketch

### Phase 1 — Offline extractor

Add a script that can ingest transcript text/JSON/Markdown files and produce `idea_mine_items.jsonl`.

Possible path:

- `scripts/curation/extract_chat_goldmine.py`

The script should:

1. read one or more transcript files
2. chunk by conversation/session
3. ask local/approved model to extract structured objects
4. write JSONL to `data/imports/chat_goldmine/YYYY-MM-DD/items.jsonl`
5. never auto-write to long-term memory

### Phase 2 — Review import

Add a route or CLI to import reviewed items into SQLite.

Possible command:

```bash
./kitty idea-mine import data/imports/chat_goldmine/2026-07-04/items.jsonl
```

or route:

```http
POST /idea-mine/import
GET /idea-mine/review
PATCH /idea-mine/{id}/review
```

### Phase 3 — Use reviewed items in project/context surfaces

Approved active items can enrich:

- project resume
- morning brief
- “what’s B?” navigator
- creative mode
- knowledge search

But they should not all enter chat context by default.

## Files likely touched

- new `docs/packets/024-chat-log-idea-mine.md`
- new `scripts/curation/extract_chat_goldmine.py`
- new `gateway/idea_mine_store.py`
- possibly `gateway/routes/idea_mine.py`
- possibly `gateway/context_assembler.py` only after review-state filtering exists
- tests under `tests/`

## Files not to touch

- core memory consolidation unless implementing 023 at the same time
- LLM provider routing except for privacy tags
- action execution tiers
- Gmail/mail connector
- phone delivery packet 015
- current move-in bar packets unless Jacob explicitly reprioritizes

## Privacy and safety rules

- Local transcripts are private by default.
- Transcript extraction should default to `privacy_tier="local"` if using an LLM.
- Sensitive support/recovery material should be extractable only as reviewable support preference, not always-on identity memory.
- No “Jacob is...” psych labels.
- No unreviewed extracted item should be sent to a cloud model by default.
- No unreviewed extracted item should be used for proactive nudging.

## Acceptance criteria

1. Given a sample transcript containing 3 projects, 2 preferences, 1 prompt, and 1 sensitive recovery discussion, the extractor outputs structured JSONL with correct object types.
2. The sensitive recovery discussion is marked `sensitivity="sensitive"` or `quiet` and `user_review="unreviewed"`.
3. No extraction result writes directly to mem0/long-term memory.
4. Review state controls whether an item can appear in future context.
5. Stale or half-formed ideas can be parked without being lost.
6. A creative idea preserves its original weirdness/taste in the summary.
7. Tests prove rejected/keep_quiet items do not surface.
8. The implementation does not delay the H1 move-in bar unless Jacob explicitly says this packet is active.

## Example extracted items

### project_thread

```json
{
  "object_type": "project_thread",
  "title": "Kitty as attention-repair assistant",
  "one_line": "Kitty holds the thread: what mattered, what was decided, and the next small move.",
  "status": "active",
  "domain": "kitty",
  "why_it_matters": "This connects memory, daily briefing, creative work, and project navigation into one product thesis.",
  "last_known_state": "Packet 023 authored to encode memory taste and creative continuity.",
  "next_small_move": "Review packet 023 language and decide whether 'creative_thread' is the right term.",
  "sensitivity": "normal",
  "user_review": "unreviewed"
}
```

### preference_or_taste

```json
{
  "object_type": "preference_or_taste",
  "preference": "Memory should feel like continuity, not surveillance or a recovery case file.",
  "applies_to": "Kitty memory, SOUL, context assembly, morning brief",
  "strength": "strong",
  "avoid": "Defaulting every future answer to spirals/recovery/backstory.",
  "examples": ["surface decisions and next steps before painful context", "sensitive support context quiet unless relevant"],
  "user_review": "unreviewed"
}
```

## Jacob review questions before build

1. Which transcript sources should be mined first: ChatGPT export, Claude projects folder, repo logs, or current chat only?
2. Should extracted items land in a review queue on the phone or a local web UI first?
3. What labels do you want: `active/parked/someday`, or something less project-management-y?
4. Should the first pass be creative/project only, excluding recovery/support entirely?
5. Do you want this before or after move-in day?

## One-line build instruction

Build a local-first chat-log mining pipeline that extracts unfinished projects, ideas, decisions, preferences, prompts, and creative sparks into a reviewable archive, without auto-injecting sensitive history into Kitty’s personality or daily context.
