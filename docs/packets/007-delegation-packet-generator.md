# Packet 007 — Delegation packet generator

- **Status:** ready — unblocked (003 action queue + 012 privacy boundary
  shipped; the template below is authored, which was the "strongest model"
  half of this packet).
- **Best executor:** Codex or Claude Code — this is now plumbing: a renderer,
  a T1 action kind, a CLI subcommand, golden-file tests.
- **Purpose:** Turn an approved action into an executor-ready packet file.
  Kitty starts producing the same artifacts that drive her own development —
  the full loop: signal → triage → action → approval → delegated
  implementation → PR → state change she reports back.

## Decisions already made (do not reopen)

- **Output is a file, nothing more.** `docs/packets/NNN-slug.md`. No process
  spawning, no API calls to executors, no GitHub posts. Jacob (or a session
  he starts) carries the packet.
- **New action kind `packet.delegate`, tier T1** (a draft artifact on disk —
  same risk class as `note.draft`). Added to `config/action_tiers.json`;
  the tier sheet is signed, so this addition is explicitly on Jacob's review
  list below.
- **Template is fixed** (below). The renderer fills slots; it does not
  invent sections. Golden-file tests pin the output byte-for-byte.
- **No LLM call in v1.** The renderer composes purely from the source
  action's fields. Slots the action can't fill render as an explicit
  `<!-- EXECUTOR: unfilled — packet author must complete -->` marker, never
  silently empty. (Resume-context enrichment via LLM is a later packet —
  project resume shipped in #71 can feed it then.)

## The template (renderer output, exactly this shape)

````markdown
# Packet {NNN} — {title}

- **Status:** draft (generated {YYYY-MM-DD} from action {action_id})
- **Best executor:** {executor_type}
- **Purpose:** {purpose}

## Exact scope

{scope}

## Files likely touched

{files_touched}

## Files not to touch

{files_not_to_touch}

## Steps

{steps}

## Acceptance criteria

{acceptance}

## Verification

```bash
{verification_commands}
```

## Risks / rollback

{risks}

## Too broad if

{too_broad_if}

## Jacob reviews

{jacob_reviews}
````

## Exact scope

1. **New `gateway/delegation.py`:**
   - `render_packet(action: dict) -> str` — pure function, action in,
     markdown out per the template. Payload keys map 1:1 to slots
     (`title`, `executor_type`, `purpose`, `scope`, `files_touched`,
     `files_not_to_touch`, `steps`, `acceptance`,
     `verification_commands`, `risks`, `too_broad_if`, `jacob_reviews`).
     Missing keys → the explicit unfilled marker.
   - `next_packet_number() -> int` — scan `docs/packets/*.md` filenames for
     the max `NNN` prefix, return max+1 (zero-padded to 3).
   - `write_packet(action) -> Path` — render + write
     `docs/packets/{NNN}-{slug}.md` (slug from title: lowercase,
     non-alphanumeric → `-`). Refuse to overwrite an existing file — fail
     loud, never clobber.
   - Registry update: append a row to the table in `docs/packets/README.md`
     with status `✏️ draft (generated)`. If the table can't be parsed,
     fail loud with the path — do not write a half-updated README.
2. **Action kind registration:** add `"packet.delegate": "T1"` to
   `config/action_tiers.json`. Executor function in `gateway/action_queue.py`
   following the existing `note.draft` executor pattern: calls
   `delegation.write_packet`, records `"packet written to {path}"` as the
   result.
3. **CLI:** `./kitty delegate <action-id>` — new case in the `kitty` bash
   launcher's existing `case "${1:-help}"` dispatch, calling
   `"$PYTHON_BIN" -m gateway.delegation "$2"` (a small `__main__` that loads
   the action by id and executes the write path, printing the output file).
   Add the one-line usage entry to the header comment block.

## Files likely touched

- `gateway/delegation.py` (new), `gateway/action_queue.py` (one executor),
  `config/action_tiers.json` (one line), `kitty` launcher (one case +
  usage line), `docs/packets/README.md` (registry row on generation),
  `tests/test_delegation.py` (new).

## Files not to touch

- Executor tier logic in `action_queue.py` — register a kind, don't touch
  enforcement.
- Anything that could invoke an external agent, post to GitHub, or spawn a
  process. The output is markdown; full stop.
- Existing packet files.

## Acceptance criteria

- **Golden-file test:** a fully-populated fixture action renders
  byte-identical to a checked-in golden file
  (`tests/golden/packet_delegate_full.md`); a sparse action renders with
  the explicit unfilled markers (second golden file). Any template drift
  breaks the test — that is the point.
- Numbering test: with fixture packet files `001`, `003`, next number is
  `004` — actually verify max+1 (`004`), not gap-filling.
- Overwrite refusal test: existing target path → raises, file untouched.
- `packet.delegate` proposes as T1 and executes from proposed
  (mirror `test_t1_note_draft_writes_local_file_from_proposed`).
- Registry row appears after generation; README still parses (run the
  renderer twice in a test — two rows, no corruption).
- `./kitty delegate <id>` prints the created path (manual check).
- Full suite green: `python3.12 -m pytest tests/ -q --tb=short`.

## Verification

```bash
python3.12 -m pytest tests/test_delegation.py tests/ -q --tb=short
# manual: propose a packet.delegate action via /actions, approve-execute,
# then eyeball the generated file against a hand-written packet.
```

## Risks / rollback

- **Packets too vague to execute:** golden tests pin required sections; the
  unfilled markers make gaps visible instead of silent. The real quality
  bar is Jacob's side-by-side review (below).
- **Rollback:** revert PR; generated markdown is inert; remove the tier line.

## Too broad if

It spawns agents, calls any external API, posts to GitHub, adds an LLM call,
or manages executor sessions.

## Jacob reviews

- The `packet.delegate` T1 addition to the signed tier sheet (one line, but
  it's his signature).
- The first generated packet, side by side with a hand-written one (e.g.
  packet 014) — does it pass the same bar?
