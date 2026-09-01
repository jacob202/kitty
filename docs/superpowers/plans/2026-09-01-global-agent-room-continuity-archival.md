# Global Agent Room Continuity Archival Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `workspace_global` sufficient for mutable interactive continuity, then retire the tracked `.claude/STATE.md` / `.claude/HANDOFF.md` checkpoint system and its runtime/tooling burden without moving stable product or architecture authority out of Git.

**Architecture:** GAR owns mutable communication, scoped handoffs, questions, status, results, and cross-agent continuation. Git remains the authority for Constitution/ADRs/architecture/roadmap/Mission/stable operating policy; KittyBuilder remains execution/task/lease authority; GitHub issue #490 remains interactive ownership/collision authority; Git/GitHub remain publication evidence. Legacy checkpoint readers/writers are removed only after GAR can retrieve an assignment-scoped handoff deterministically.

**Tech Stack:** Python 3.12, SQLite migrations, FastAPI/Gateway domain code, Kitty CLI, MCP Agent Room server, Markdown operating contracts, pytest.

**Spec:** `docs/superpowers/specs/2026-08-31-global-agent-room-design.md`

## Global Constraints

- Canonical room id remains exactly `workspace_global`.
- Do not add an eighth MCP tool; extend the existing seven tools with optional fields only.
- `registered` means membership, never online presence.
- GAR is communication/continuity, not a task queue, scheduler, lease system, or execution state machine.
- KittyBuilder remains authoritative for engineering execution/tasks/leases.
- GitHub issue #490 remains authoritative for interactive ownership/collision markers.
- Git/GitHub remain authoritative for publication/merge evidence.
- Stable architecture, ADRs, roadmap/Mission, safety, and operating policy remain versioned in Git.
- Historical ADRs/audits/plans are preserved as historical evidence; do not rewrite history merely to remove old checkpoint references.
- Do not delete `.claude/STATE.md` or `.claude/HANDOFF.md` until the no-legacy cold-start acceptance passes with both files physically absent.

---

### Task 1: Harden GAR-first context receipts

**Files:**
- Modify: `gateway/context_receipt.py`
- Modify: `tests/test_context_receipt.py`
- Modify: `tests/test_cold_start_acceptance.py`
- Modify: `START_HERE.md`
- Modify: `CLAUDE.md`
- Modify: `.agents/skills/next/SKILL.md`

**Interfaces:**
- Consumes: existing `build_context_receipt()` / `inspect_continuity()`.
- Produces: `include_legacy_continuity: bool = True` on receipt functions plus CLI flag `--skip-legacy-continuity`.

- [ ] **Step 1: Write failing tests for a GAR-first receipt that ignores malformed legacy checkpoints**

```python
def test_receipt_can_skip_legacy_checkpoint_failures(tmp_path: Path):
    repo, _head = _repo(tmp_path)
    _write(repo / ".claude/STATE.md", "malformed\n")
    _write(repo / ".claude/HANDOFF.md", "malformed\n")

    strict = build_context_receipt(repo, expected_canonical=repo, now=NOW)
    gar_first = build_context_receipt(
        repo,
        expected_canonical=repo,
        now=NOW,
        include_legacy_continuity=False,
    )

    assert strict["ok"] is False
    assert gar_first["ok"] is True
    assert gar_first["continuity"]["state"] is None
    assert gar_first["continuity"]["handoff"] is None
    assert gar_first["next_action"] is None
    assert gar_first["blockers"] is None
    assert gar_first["recommendations"] is None
    assert gar_first["evidence"]["checkpoint_source"] == []
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `pytest -q -o addopts='' tests/test_context_receipt.py -k skip_legacy_checkpoint_failures`
Expected: FAIL because `include_legacy_continuity` does not exist.

- [ ] **Step 3: Add the opt-out without weakening strict doctor/CI callers**

```python
def inspect_continuity(..., include_legacy_continuity: bool = True) -> dict[str, Any]:
    if include_legacy_continuity:
        state, state_error = _safe_load(...)
        handoff, handoff_error = _safe_load(...)
        # existing checkpoint checks/agreement checks
    else:
        state = handoff = None
        state_error = handoff_error = None
        # omit all checkpoint FAIL/WARN checks


def build_context_receipt(..., include_legacy_continuity: bool = True) -> dict[str, Any]:
    inspection = inspect_continuity(..., include_legacy_continuity=include_legacy_continuity)
```

Add CLI parsing:

```python
parser.add_argument(
    "--skip-legacy-continuity",
    action="store_true",
    help="exclude .claude checkpoint state after Global Agent Room continuity is available",
)
receipt = build_context_receipt(
    ROOT,
    include_builder=not args.skip_builder,
    include_legacy_continuity=not args.skip_legacy_continuity,
)
```

- [ ] **Step 4: Make GAR-success startup use the new receipt mode**

`START_HERE.md`, `CLAUDE.md`, and `next` must say: first prove Agent Room access; when it succeeds run `./kitty context --agent --skip-legacy-continuity`; when the room is unavailable, report that and use the strict legacy-compatible receipt instead.

- [ ] **Step 5: Update cold-start acceptance**

The GAR-first cold-start acceptance must assert the receipt does not export a legacy `next_action`; the next action comes from a scoped GAR handoff/thread. Keep the strict legacy receipt tests separately for compatibility until Task 7.

- [ ] **Step 6: Verify and commit**

Run:
`pytest -q -o addopts='' tests/test_context_receipt.py tests/test_cold_start_acceptance.py tests/test_kitty_launcher.py`

Commit: `fix(agent-room): isolate legacy continuity from GAR startup`

---

### Task 2: Publish handoffs only after final validation

**Files:**
- Modify: `.agents/skills/session-end/SKILL.md`
- Modify: `tests/test_session_end_audit.py`
- Modify: `docs/reference/CONTEXT_ENGINEERING.md`

**Interfaces:**
- Consumes: existing compatibility checkpoint writer/validator sequence.
- Produces: final validated GAR result/handoff as the last state-changing continuity action.

- [ ] **Step 1: Add a failing content-contract test**

```python
def test_session_end_posts_room_handoff_after_final_validation():
    text = SESSION_END_SKILL.read_text(encoding="utf-8")
    validate_at = text.index("check_continuity_state.py")
    final_post_at = text.index("Post the final Global Agent Room handoff")
    assert validate_at < final_post_at
    assert "If validation fails" in text
    assert "blocked" in text or "failed" in text
```

- [ ] **Step 2: Verify RED**

Run: `pytest -q tests/test_session_end_audit.py -k room_handoff_after_final_validation`
Expected: FAIL because the current skill posts before compatibility writes/validation.

- [ ] **Step 3: Reorder the workflow**

Session-end sequence becomes:
1. survey/reconcile evidence;
2. prepare handoff content but do not publish it;
3. write compatibility snapshots while they still exist;
4. run `check_continuity_state.py`, context receipt, and final Git inspection;
5. post one final `handoff`/`result` containing the actual final SHA, dirty-path inventory, verification, blockers, and next action;
6. if validation failed, post a truthful `blocked`/`failed` result rather than the pre-validation success draft.

- [ ] **Step 4: Restore the verified-delivery compaction wording contract**

`docs/reference/CONTEXT_ENGINEERING.md` must retain these exact concepts/phrases while pointing at GAR: `outcome contract and non-goals`, `accepted decisions and their authority`, `branch/worktree, and SHA`, `exact verification commands and results`, `unresolved failures and blockers`, `one concrete next action`.

- [ ] **Step 5: Verify and commit**

Run: `pytest -q tests/test_session_end_audit.py tests/test_verified_delivery_skill.py`

Commit: `fix(agent-room): publish only validated final handoffs`

---

### Task 3: Add assignment-scoped retrieval without adding another MCP tool

**Files:**
- Create: `gateway/migrations/053_agent_workspace_scope_key.sql`
- Modify: `gateway/agent_workspace.py`
- Modify: `gateway/routes/agent_workspace.py`
- Modify: `gateway/agent_room_cli.py`
- Modify: `mcp/agent_room/server.py` and its existing schema module(s)
- Modify: focused Agent Room tests under `tests/` / `mcp/agent_room/tests/`

**Interfaces:**
- Produces: optional `scope_key: str | None` on existing message post/reply/list/inbox operations.
- Existing seven MCP tool names remain unchanged.

- [ ] **Step 1: Write failing domain tests for scoped retrieval beyond the global recent window**

```python
def test_scope_filter_finds_handoff_older_than_global_recent_window(tmp_path):
    old = post_global_message(
        sender_id="chatgpt",
        content="handoff for PR 759",
        message_kind="handoff",
        scope_key="github:pr:759",
    )
    for index in range(150):
        post_global_message(sender_id="kitty", content=f"noise {index}")

    scoped = list_messages(GLOBAL_WORKSPACE_ID, scope_key="github:pr:759", limit=20)
    assert [message["id"] for message in scoped] == [old["id"]]
```

- [ ] **Step 2: Verify RED**

Run the focused Agent Room domain suite; expect failure because messages have no `scope_key` and list functions cannot filter it.

- [ ] **Step 3: Add additive schema/index**

Migration adds nullable `scope_key TEXT` and an index covering `(workspace_id, scope_key, created_at)`; existing messages remain valid with `NULL` scope.

- [ ] **Step 4: Extend existing seven-tool interfaces**

`room_recent`, `room_inbox`, `room_post`, and `room_reply` accept optional `scope_key`; replies inherit the parent message scope when omitted. `room_thread` continues to use message id and needs no new tool.

CLI adds `--scope <scope_key>` to `recent`, `inbox`, `post`, and `reply`.

- [ ] **Step 5: Define stable scope keys**

Use evidence-derived keys only:
- PR work: `github:pr:<number>`
- issue-owned lane before PR: `github:issue:490:<lane-id>`
- branch-only interactive work: `git:branch:<branch>`
- unscoped shared announcements: `NULL`

Do not encode task status, owner, lease, priority, or scheduling state into the key.

- [ ] **Step 6: Verify and commit**

Run the full focused core/CLI/MCP Agent Room suite plus migration tests.

Commit: `feat(agent-room): add scoped handoff retrieval`

---

### Task 4: Make interactive consumers use GAR scope; make Builder workers stop reading interactive checkpoints

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `START_HERE.md`
- Modify: `.agents/skills/next/SKILL.md`
- Modify: `.agents/skills/orca-orchestration/SKILL.md`
- Modify: `scripts/kittybuilder_claude_adapter.py`
- Modify: `scripts/kittybuilder_codex_adapter.py`
- Modify: `scripts/kittybuilder_opencode_worker.sh`
- Modify: `mcp/builder/context.py`
- Modify: matching tests

**Interfaces:**
- Interactive agents discover continuation from unread direct inbox plus assignment `scope_key`.
- Builder-launched workers use their packet bundle/Builder projections and do not load interactive GAR handoffs or `.claude` checkpoints unless a packet explicitly requests a historical artifact.

- [ ] **Step 1: Add tests that adapters no longer instruct workers to read `.claude/STATE.md` / `.claude/HANDOFF.md`**
- [ ] **Step 2: Verify RED against current adapter prompt text**
- [ ] **Step 3: Replace interactive boot instructions with `room_inbox --unread --scope ...` / scoped MCP equivalents**
- [ ] **Step 4: Remove checkpoint reads from Builder worker prompts**
- [ ] **Step 5: Verify all adapter/context tests and commit**

Commit: `refactor(agent-room): route continuity by execution lane`

---

### Task 5: Remove legacy writers and recommendation carry-forward

**Files:**
- Modify: `.agents/skills/session-end/SKILL.md`
- Modify: `scripts/session_end_survey.sh`
- Modify: `~/kb/NOW.md` procedure references only through repo docs/skills (do not mutate unrelated KB content in this packet)
- Modify: tests for session-end survey/skills

**Interfaces:**
- GAR scoped handoff owns one concrete interactive next action.
- Real scheduled/owned engineering work belongs in Builder/roadmap/#490 as appropriate; GAR does not become a backlog.

- [ ] **Step 1: Add tests proving session-end does not write either `.claude` file and does not read carried recommendations from STATE**
- [ ] **Step 2: Verify RED**
- [ ] **Step 3: Remove compatibility writes and `STATE.md` recommendation parsing from `session_end_survey.sh`**
- [ ] **Step 4: Keep workflow-signal and KB-effectiveness receipts as evidence history, not next-step queues**
- [ ] **Step 5: Verify and commit**

Commit: `refactor(agent-room): retire legacy continuity writers`

---

### Task 6: Ratify GAR continuity authority and thin the bootloaders

**Files:**
- Create: `docs/adr/0041-global-agent-room-continuity.md`
- Modify: `docs/adr/README.md`
- Modify: `docs/DECISIONS.md`
- Modify: `docs/AUTHORITY_MAP.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/reference/CODEBASE_MAP.md`
- Modify: `docs/BLUEPRINT.md`
- Modify: `docs/WORKFLOW.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Authority map replaces `session_checkpoint` / `continuation` as live authorities with one interactive-continuity entry naming `workspace_global`.
- Historical ADRs 0023/0025 remain historical; ADR 0041 explicitly supersedes only their checkpoint-file continuation mechanics, not their learning/no-second-backlog principles.

- [ ] **Step 1: Write ADR 0041 with explicit supersession boundaries**
- [ ] **Step 2: Update the authority map and architecture references**
- [ ] **Step 3: Thin `CLAUDE.md` by removing rules already owned by `AGENTS.md`/`START_HERE.md`; keep only Claude-specific bootloader/tool differences**
- [ ] **Step 4: Keep `AGENTS.md` compact; do not move stable policy into GAR**
- [ ] **Step 5: Add docs-contract tests and commit**

Commit: `docs(agent-room): ratify GAR continuity authority`

---

### Task 7: Archive and delete the checkpoint compatibility system

**Files:**
- Create: `docs/archive/continuity/2026-09-01-legacy-checkpoints/README.md`
- Create: `docs/archive/continuity/2026-09-01-legacy-checkpoints/STATE.md`
- Create: `docs/archive/continuity/2026-09-01-legacy-checkpoints/HANDOFF.md`
- Delete: `.claude/STATE.md`
- Delete: `.claude/HANDOFF.md`
- Delete: `scripts/check_continuity_state.py`
- Delete: `scripts/sanitize_builder_state.sh`
- Modify: `gateway/context_receipt.py`
- Modify: `gateway/doctor.py`
- Modify: `scripts/preflight.sh`
- Modify: `.gitattributes`
- Delete/modify: checkpoint-specific tests (`tests/test_check_continuity_state.py`, `tests/test_sanitize_builder_state.py`, checkpoint-only cases in `tests/test_context_receipt.py`)

**Interfaces:**
- `build_context_receipt()` no longer emits `continuity.state`, `continuity.handoff`, `blockers`, `next_action`, `recommendations`, or checkpoint evidence.
- Doctor no longer treats deleted interactive checkpoint files as repository health.

- [ ] **Step 1: Copy the final exact legacy files into the archive with provenance**

Archive README records source paths, final Git SHA containing them, retirement ADR 0041, and states that the copies are historical evidence only.

- [ ] **Step 2: Add a failing no-legacy acceptance test before deletion**

```python
def test_cold_start_and_session_end_do_not_require_legacy_checkpoint_files(tmp_path):
    # fixture intentionally contains no .claude/STATE.md or HANDOFF.md
    receipt = build_context_receipt(tmp_path, include_legacy_continuity=False)
    assert receipt["ok"] is True
```

Also add a repository contract that no current runtime/script/skill outside `docs/archive/` references those two paths.

- [ ] **Step 3: Delete the tracked checkpoint files and dedicated tooling**
- [ ] **Step 4: Remove merge-driver/preflight compatibility hooks**
- [ ] **Step 5: Simplify context receipt/doctor and remove obsolete tests**
- [ ] **Step 6: Verify and commit**

Commit: `refactor(agent-room): archive legacy checkpoint system`

---

### Task 8: Final acceptance and anti-regression gate

**Files:**
- Create or modify: one focused repository contract test such as `tests/test_agent_continuity_authority.py`
- Modify: `docs/reference/MULTI_AGENT_COORDINATION.md`

**Interfaces:**
- Proves GAR is sufficient before legacy deletion is accepted.

- [ ] **Step 1: Prove scoped retrieval survives >100 unrelated room messages**
- [ ] **Step 2: Prove malformed/missing legacy files cannot block GAR-first startup**
- [ ] **Step 3: Prove final room handoff is published after final validation evidence**
- [ ] **Step 4: Prove no active runtime/script/skill reads or writes `.claude/STATE.md` / `.claude/HANDOFF.md`**
- [ ] **Step 5: Prove Builder workers rely on Builder packet/control-plane truth, not interactive GAR continuity**
- [ ] **Step 6: Prove product Home/session UI cannot surface developer checkpoint text**
- [ ] **Step 7: Run focused suites, then normal CI/independent review; archive is complete only on the exact reviewed SHA**

Commit: `test(agent-room): lock continuity authority to GAR`

---

## Disposition Summary

**Move to GAR:** mutable current handoffs, cross-agent questions, review requests, verified results, blockers, temporary status, and one concrete next interactive action.

**Keep in Git permanently:** Constitution, North Star, architecture, ADRs, roadmap/Mission, stable safety/review/Git policy, Builder contracts, product status at stated SHAs, and historical evidence.

**Compatibility-hold until Tasks 1–4 are green:** `.claude/STATE.md`, `.claude/HANDOFF.md`, strict checkpoint validation in `gateway/context_receipt.py`, `scripts/check_continuity_state.py`, session-end compatibility writers, carried recommendation parsing, merge-driver/preflight hooks.

**Archive/delete after Task 8 acceptance:** the two tracked checkpoint files and tooling whose only purpose is maintaining/validating/sanitizing those files.

**Leave historical references alone:** archived audits, old plans, old ADR text, mission evidence, and Git history. They describe what was true at the time and should not be mass-rewritten.

## Self-Review

- Spec coverage: preserves the original GAR boundary (communication only), stable room, seven MCP tools, registered-not-online semantics, Builder authority, and #490 collision authority.
- Retrieval gap: explicitly blocked from full archival until assignment-scoped retrieval exists and is proven beyond the global recent window.
- Validation ordering gap: final room result is deliberately after compatibility writes and final verification.
- Legacy-receipt gap: GAR-first startup has an explicit no-legacy receipt mode before strict checkpoint validation is removed globally.
- No placeholders: every retirement step has a named file set, acceptance condition, verification command class, and commit boundary.
