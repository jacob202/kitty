# KB payload — 2026-08-11

`~/kb` did not exist in this container at session start. It was **created and
populated before close**, so every entry below is already live under
`~/kb/wiki/`, `~/kb/corrections/`, `~/kb/metrics/`, and `~/kb/workflow-signals/`.

This file is the in-repo mirror, kept because the container is ephemeral. It is
not a pending task.

---

## Written to `~/kb/wiki/2026-08-11-ci-typecheck-installs-no-dependencies.md`

```markdown
# CI's typecheck job installs no project dependencies at all

**Source:** 2026-08-11 session, claude-code (claude-opus-5), jacob202/kitty
**Date:** 2026-08-11
**Why it matters:** Every third-party import in the repository resolves to `Any`
during CI type checking, so an entire class of error is invisible to CI while
blocking local pushes.
**Verified:** `.github/workflows/tests.yml` typecheck job runs only
`pip install mypy types-requests types-PyYAML types-python-dateutil` before
`mypy gateway/ mcp/ workers/ scripts/runpod_worker_smoke_test.py`. It never
installs `requirements.txt` or `mcp/imagen/requirements.txt`.

With `ignore_missing_imports = true`, an uninstalled package becomes `Any` and
mypy reports nothing about it. Because the job installs no project dependencies,
that applies to **fastapi, pydantic, httpx, google-genai, and everything else**
across `gateway/`, `mcp/`, and `workers/` — not just one subpackage.

Correction to an earlier claim in this same session: a venv holding only
`requirements.txt` is **not** CI-equivalent. It is closer than a full install but
still stricter than CI.

Demonstrated concretely: seven real errors in `mcp/imagen/retry.py`,
`engines/imagen4.py`, and `server.py` were invisible to CI and sat on `main`
unseen. They surfaced only through the pre-push hook added in #453, which runs on
a machine where the libraries exist — and there they blocked every push
regardless of what the change touched, including a docs-only commit.
```

Index line appended to `~/kb/INDEX.md`:

```
- 2026-08-11 — CI's typecheck job installs no project dependencies at all — wiki/2026-08-11-ci-typecheck-installs-no-dependencies.md
```

---

## Written to `~/kb/wiki/2026-08-11-reading-a-dead-actions-runner.md`

```markdown
# Telling a dead Actions runner from a real test failure

**Source:** 2026-08-11 session, claude-code (claude-opus-5), jacob202/kitty
**Date:** 2026-08-11
**Why it matters:** For four days every check was red for a reason that had
nothing to do with the code, and the repository's own status documents recorded
the outage as ongoing after it had already lifted.
**Verified:** Actions API run history for `.github/workflows/tests.yml`, read
2026-08-10 23:12Z and again 2026-08-11 08:00Z.

Runner metadata is the proof; duration is only the clue that sends you looking.
A legitimate run can also fail in seconds when an early command rejects the code,
so never conclude "outage" from timing alone.

Confirm all four before discarding a red result: `runner_id: 0`, an empty runner
name, a 404 on the log download, and empty check-run output. Those mean no
workflow line executed, so the result carries no information about the code. If
any of them is absent, the failure is real and belongs to the code.

For scale: outage runs here ended in **3–13 seconds**; a real `Tests` run takes
**200–314 seconds**.

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

## Written to `~/kb/corrections/2026-08-11-fix-it-dont-flag-it.md`

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

## Written to `~/kb/corrections/2026-08-11-dont-send-him-to-debug.md`

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

Receipt `kbr_e24216337393bb50acbb`, written to
`~/kb/metrics/kb-effectiveness.jsonl` and mirrored in-repo at
`docs/session-notes/kb-effectiveness.jsonl` (force-added past the `*.jsonl`
ignore rule so the evidence survives this container).

## Workflow signals

Written to `~/kb/workflow-signals/` and mirrored in-repo:
`parallel-lanes-duplicate-same-fix` (duplicate_work, high) and
`ci-cannot-typecheck-imagen-deps` (missing_automation, medium). Both are first
occurrences at `observe`.

Cross-store repeat detection is still imperfect: an earlier session recorded
`local-prepush-ci-divergence` for the same divergence under a different stable
key. Reconcile the keys when both stores are on one machine.
