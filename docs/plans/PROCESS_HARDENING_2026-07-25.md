# Process hardening — engineering plan (2026-07-25)

**Status: proposal. Not implemented, not scheduled, not authoritative.** Roadmap authority
remains the file named by `docs/AUTHORITY_MAP.md`. This plan describes six process changes and
stops there; nothing here has been built.

**Why these six, together.** They share one failure mode: *state that several actors write, with
no record of who wrote it or what it looked like when someone read it.* Concurrent sessions
clobber `.claude/STATE.md`. A review approves a SHA the branch has already moved past. A
continuity document self-invalidates and nothing notices until a test fails. Each item below
closes one leak; item 5 is the one that keeps the others closed.

Sequencing note: 3 → 4 → 5 is a real dependency chain. 1, 2 and 6 are independent.

---

## 1 · `review_freeze.sh`

**Problem.** A review reads a working tree that can change under it. "Reviewed and approved"
names no artifact, so it cannot be checked later or reproduced.

**Shape.** One script that resolves the review target to an immutable SHA, records it, and
refuses to run against a dirty tree.

- Resolve `HEAD` (or an explicit ref) to a full SHA; abort on uncommitted changes unless
  `--allow-dirty`, which stamps the record as unreproducible.
- Emit a freeze record: SHA, branch, timestamp, base SHA, changed-file list.
- Print the record path so downstream steps consume the SHA, not the branch name.

**Smallest check.** One test: freeze, commit something new, and assert the frozen SHA still
resolves to the original tree.

**Open question.** Where the freeze record lives — alongside the receipts from item 3 is the
obvious answer, which is why item 3 should land first if both are done.

**Explicitly not in scope.** Running the review. This produces the frozen input; what consumes it
is item 2.

---

## 2 · Review-by-SHA / owned-scope workflow

**Problem.** Two coupled gaps. Reviews are addressed to a branch, which moves. And nothing
declares which paths a given actor owns, so two sessions can edit the same file with each
believing it holds the scope.

**Shape.**

- Every review names a frozen SHA (item 1) and an owned path set.
- Findings carry `file:line @ SHA`, so a finding can be resolved to the exact text reviewed even
  after the file moves.
- A scope check compares the diff's touched paths against the declared owned set and fails on
  anything outside it. `gateway/builder_scope.py` already does scope work for Builder; this is
  the same idea applied to interactive review rather than a new mechanism.

**Smallest check.** One test: a diff touching an unowned path fails the scope check; the same
diff with that path declared passes.

**Open question.** Whether owned scope is declared per review or derived from an existing
manifest. Deriving is better if a manifest already covers the case — worth checking before
building a second declaration format.

---

## 3 · Immutable session receipts (`CURRENT.json` + per-session receipts)

**Problem.** `.claude/STATE.md` and `.claude/HANDOFF.md` are single mutable files that multiple
concurrent sessions write. Last writer wins, the loser's context is gone, and there is no history
to recover it from. `CLAUDE.md` already warns about this in prose — prose is not a mechanism.

**Shape.** Split the one mutable file into many immutable ones plus a pointer.

- **Per-session receipt:** one append-only JSON file per session, named by session id, never
  rewritten after close. Contains what STATE.md holds today — head SHA, branch, mission, next
  action — plus the session id and open/close timestamps.
- **`CURRENT.json`:** a small pointer file listing the *active* session ids and which receipt is
  the latest per branch. This is the only mutable file, and it is a pointer, not narrative.
- Writes to `CURRENT.json` go through one function that does read-modify-write under a lock, so
  a second session adds itself rather than replacing the first.

`gateway/context_receipt.py` already builds a read-side projection over git and the canonical
documents. This extends that idea to the write side rather than inventing a parallel one.

**Smallest check.** One test: two sessions open concurrently, both appear in `CURRENT.json`,
and neither receipt is modified by the other.

**Open question.** Retention. Receipts accumulate forever by design; whether old ones are pruned,
and by what rule, is undecided. Defaulting to "never prune" is fine until it isn't.

**Migration.** `.claude/STATE.md` and `.claude/HANDOFF.md` stay as generated views for a period,
so the cold-start procedure in `CLAUDE.md` keeps working while the receipts become the source.
Deleting them is a separate decision with its own owner.

---

## 4 · Live vs snapshot authority API

**Problem.** Consumers cannot tell whether they are reading current truth or a point-in-time
record, so a stale snapshot gets treated as live. That is exactly how a continuity document ends
up asserting a SHA five commits behind while a session bootstraps from it.

**Shape.** Two explicitly named read paths over the same data.

- `live()` — reads current state, and is allowed to be slow (it may shell out to git).
- `snapshot(at)` — reads a receipt from item 3 and is guaranteed immutable.
- Every returned object carries its own provenance: which mode produced it, at what SHA, at what
  time. A consumer that renders truth without rendering provenance is the bug this prevents.
- `live()` is the default only where freshness genuinely matters; review tooling (items 1–2)
  should be on `snapshot`.

**Smallest check.** One test: `snapshot(sha)` returns identical output before and after new
commits land; `live()` changes.

**Open question.** Whether the existing receipt projection becomes `live()` directly or is
wrapped. Wrapping is cheaper and reversible; prefer it absent a reason.

---

## 5 · Direct-state-write enforcement and architectural test

**Problem.** Items 3 and 4 only hold if nothing bypasses them. `grep` currently finds several
modules writing state paths directly. Convention alone will not keep that at zero — this repo
already has a documented case of a reasonable cleanup silently breaking a live path.

**Shape.**

- One writer module owns all state writes. Everything else calls it.
- An architectural test asserts that no module outside that writer references the state paths
  directly — same shape as the existing `test_memory_graph_contract.py` and
  `test_builder_contract.py`, which is the pattern to copy rather than invent.
- Known exceptions live in an explicit allowlist in the test, each with a reason. An empty
  allowlist is the goal; a silent exception is the failure.

**Smallest check.** The architectural test *is* the check. Verify it by adding a direct write and
watching it go red.

**Open question.** Whether shell scripts are in scope. `scripts/kittybuilder_opencode_worker.sh`
writes state and a Python AST check will not see it. Either the test greps shell too, or shell
writers are routed through the CLI. Routing is cleaner; grepping is cheaper.

**Order matters.** This lands *after* 3 and 4, or it enforces a contract that does not exist yet.

---

## 6 · Builder transition hardening

**Problem.** Builder has real transition machinery — `transition_task`, `worker_transition_task`,
`_validate_run_transition`, and a `find_silent_transitions` helper whose existence implies silent
transitions have happened. Validation is spread across several call sites, which is how a path
ends up unvalidated.

**Shape.**

- One transition table: `(from_state, to_state) → allowed`, declared once as data, not as
  branching logic in each caller.
- Every transition goes through one guarded function that consults the table, records who
  requested it, and refuses an undeclared pair loudly. No silent no-op on a rejected transition —
  that is the current failure dressed as success.
- `find_silent_transitions` becomes an assertion rather than a diagnostic: if it can still find
  one, the guard has a hole.

**Smallest check.** One test: an undeclared transition raises rather than returning; a declared
one succeeds and is recorded.

**Open question.** Whether existing transition paths are already a strict subset of the table, or
whether writing the table down will reveal pairs that happen in practice and are not supposed to.
Assume the latter and budget for reconciling it — that discovery is most of the value here.

---

## What this plan does not do

- No implementation. No files were changed for any of the six items.
- No priority order across the six, beyond the 3 → 4 → 5 dependency.
- No effort estimates. Earlier documents in this repo attached day-counts to work nobody had
  scoped, and several of those estimates named things that already existed.
- No ownership. Who does any of this, and whether it is worth doing at all, is not this
  document's call.
