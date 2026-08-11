# Staged KB payload — 2026-08-11

`~/kb` does not exist in this GitHub-connected container, so these entries could
not be written to the cross-tool knowledge base. Copy them into `~/kb` from a
session where it is present, then append the index lines and delete this file.

Release check: `test -d ~/kb`

---

## Destination: `~/kb/wiki/2026-08-11-ci-cannot-see-imagen-type-errors.md`

```markdown
# CI cannot type-check mcp/imagen against its real dependencies

**Source:** 2026-08-11 session, claude-code (claude-opus-5), jacob202/kitty
**Date:** 2026-08-11
**Why it matters:** An entire class of type error is invisible to CI while
blocking every local push, so it looks like your machine is broken when it is
the only thing telling the truth.
**Verified:** `mypy gateway/ mcp/ workers/ scripts/runpod_worker_smoke_test.py`
run in two venvs on the same tree — "Success: no issues found in 279 source
files" with only `requirements.txt` installed, and seven errors across
`mcp/imagen/retry.py`, `engines/imagen4.py`, and `server.py` once `google-genai`
and `google-api-core` were added.

`mcp/imagen/` declares `google-genai` and `google-api-core` in
`mcp/imagen/requirements.txt`. The `Tests` workflow's `typecheck` job installs
only the root `requirements.txt`, so mypy resolves those imports to `Any` under
`ignore_missing_imports = true` and reports nothing.

Any machine with the image stack installed sees the real types and the real
errors. Seven of them sat on `main` unseen and surfaced only through the
pre-push hook added in #453, which runs where the libraries exist — and there
they blocked every push regardless of what the change touched, including a
docs-only commit.

The pattern generalizes: a subpackage with its own requirements file is
unverified by CI unless the CI job installs that file too. Check for sibling
`requirements.txt` files before trusting a green typecheck.
```

Index line for `~/kb/INDEX.md`:

```
- 2026-08-11 — CI cannot type-check mcp/imagen against its real dependencies — wiki/2026-08-11-ci-cannot-see-imagen-type-errors.md
```

---

## Destination: `~/kb/wiki/2026-08-11-reading-a-dead-actions-runner.md`

```markdown
# Telling a dead Actions runner from a real test failure

**Source:** 2026-08-11 session, claude-code (claude-opus-5), jacob202/kitty
**Date:** 2026-08-11
**Why it matters:** For four days every check was red for a reason that had
nothing to do with the code, and the repository's own status documents recorded
the outage as ongoing after it had already lifted.
**Verified:** Actions API run history for `.github/workflows/tests.yml`, read
2026-08-10 23:12Z and again 2026-08-11 08:00Z.

Duration is the tell. When the account cannot get a runner, jobs are assigned
none and end in **3–13 seconds** with `runner_id: 0`, an empty runner name, a
404 on the log download, and empty check-run output. No workflow line executes,
so the result carries no information about the code. A real run of this
repository's `Tests` workflow takes **200–314 seconds**.

The 2026-08-06 outage ended on 2026-08-10 between 23:03Z and 23:20Z. Last dead
run: `a736ee52` at 23:03:51Z. First live run: `59900f20` at 23:20:19Z. Nothing
in the repository changed; the block was account-level and cleared at the
account level.

Two consequences worth carrying: red checks from an outage window must never be
cited as code evidence, and status documents that describe an outage need an
explicit invalidation condition, or they keep asserting it after it lifts.
```

Index line for `~/kb/INDEX.md`:

```
- 2026-08-11 — Telling a dead Actions runner from a real test failure — wiki/2026-08-11-reading-a-dead-actions-runner.md
```

---

## Destination: `~/kb/corrections/2026-08-11-fix-it-dont-flag-it.md`

```markdown
# Correction: Jacob wants problems fixed, not listed

**Source:** 2026-08-11 session, claude-code (claude-opus-5)
**Date:** 2026-08-11

**Wrong assumption:** Ending a report with observations he might want to act on
("main is locked by another folder", "your skill file may be in the wrong
place") is helpful context.

**Corrected fact:** In his words — *"You weren't asking me anything but what are
these about, I don't understand, like if there's a problem fix it."* A flagged
problem with no action attached reads as a task handed back to him. He does not
code; he cannot triage a list.

**Evidence:** Two flagged items in one reply produced confusion rather than
action. One of the two was also wrong — the skill file was already in the
correct `.agents/skills/` directory, and the claim came from misreading a diff
of changed paths across several commits rather than checking the tree.

**Prevention rule:** Fix it, or say in one sentence that you cannot reach it and
give the exact command. Never end a report with a problem that has no owner and
no next action. And verify a file's location by listing the tree, not by reading
a changed-paths list.
```

---

## Destination: `~/kb/corrections/2026-08-11-dont-send-him-to-debug.md`

```markdown
# Correction: do not hand Jacob an environment to debug

**Source:** 2026-08-11 session, claude-code (claude-opus-5)
**Date:** 2026-08-11

**Wrong assumption:** Handing him a four-line venv setup would clear a blocked
push, so it was reasonable to ask him to run it and report back.

**Corrected fact:** It cleared half the problem. The failing type checks were
environment-dependent in a way the suggested fix could not address, so he ran
the commands, saw the same errors, and asked *"what's taking so long"* and
*"I don't know what he's asking me to do."*

**Evidence:** The pre-push hook reported `tests FAILED` when pytest never
started (missing `pytest-cov` plugin) and `types FAILED` on seven errors CI
structurally cannot see. Neither was caused by his change. The correct answer
was one command — `git push --no-verify` — plus fixing the seven errors myself.

**Prevention rule:** When a local tool blocks him, give the one command that
unblocks him now and take the underlying repair yourself. Do not send him into a
diagnostic loop, and never present a fix as complete before verifying it clears
the failure it targets.
```

---

## Effectiveness receipt

Recorded to the repo fallback at `docs/session-notes/kb-effectiveness.jsonl`
because `~/kb/metrics/` is unavailable. Receipt ID `kbr_e24216337393bb50acbb`.
Merge that line into `~/kb/metrics/kb-effectiveness.jsonl` when syncing.

## Workflow signals

Recorded to the repo fallback at `docs/session-notes/workflow-signals/`:
`parallel-lanes-duplicate-same-fix` (duplicate_work, high) and
`ci-cannot-typecheck-imagen-deps` (missing_automation, medium). Both are first
occurrences and sit at `observe`. Merge into `~/kb/workflow-signals/` when
syncing so repeat detection works across tools.
