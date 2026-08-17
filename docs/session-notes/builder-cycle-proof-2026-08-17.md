# Builder cycle proof — 2026-08-17

## What this is

An interactive-lane run through one full KittyBuilder packet cycle in a fresh
cloud container: pick a real bug, fix it, define a Builder initiative/packet
for it, and drive that packet through Builder's real queue/lease/attempt/
worker-dispatch/validation pipeline in shadow mode (no push, no PR). This
records exactly what happened, including where the cycle stopped short.

Branch: `claude/builder-cycle-proof-37nppd`, base `origin/main` @ `53024f9`.

## Baseline (before any change)

Setup:

```
$ python3.12 -m venv venv && ./venv/bin/pip install -r requirements.txt   # exit 0
$ ./venv/bin/pip install pytest pytest-asyncio ruff mypy                  # exit 0
$ export KITTY_EXPECTED_CANONICAL_CHECKOUT=$PWD
$ ./venv/bin/python -m pytest tests/ -q --tb=line
```

Result: **2 failed, 4216 passed, 2 skipped, 2 deselected**, 231s.

Failures (both pre-existing, confirmed on origin/main before any edit):

- `tests/test_builder_loop.py::TestRunPacket::test_operator_pause_between_attempts_stops_retry`
  — assert `'exhausted' == 'paused'`. Known environment-only failure, not touched.
- `tests/test_paths_builder_canonical.py::test_builder_launcher_exports_canonical_builder_data_dir`
  — `ModuleNotFoundError: No module named 'gateway'` when `./kitty builder ...`
  runs `venv/bin/python -m gateway.builder_cli` from a directory other than the
  repo root.

This matches the task brief exactly: these are the two tests already known to
fail in a container, on any commit.

## Step 1 — the bug, verified real

Reproduced directly, outside pytest:

```
$ cd /tmp && /home/user/kitty/venv/bin/python -m gateway.builder_cli initiative doctor --json
/home/user/kitty/venv/bin/python: Error while finding module specification for
'gateway.builder_cli' (ModuleNotFoundError: No module named 'gateway')
```

Cause: `cmd_builder()` in `kitty` (the bash launcher) picks
`$KITTY_ROOT/venv/bin/python` whenever `venv/` exists, then runs
`"$python_bin" -m gateway.builder_cli "$@"` with no `PYTHONPATH` set. `gateway`
is not an installed package (confirmed: `pip show gateway` → not found), so
Python only finds it when the process's current working directory happens to
be the repo root. Every other `cmd_*` in the same file that shells out to
Python has the identical gap **except** `cmd_context`, which already does the
right thing:

```bash
PYTHONPATH="$KITTY_ROOT${PYTHONPATH:+:$PYTHONPATH}" "$python_bin" -m gateway.context_receipt "$@"
```

Jacob's Mac always has `venv/`, so on his machine `./kitty builder ...` run
from anywhere but the repo root has always been broken this way — the
container's usual no-`venv/` state happened to hide it because the launcher's
fallback branch (`command -v python3.12`) doesn't have this problem in the
same way.

## Fixes made (interactive, applied directly)

1. **`kitty`** — `cmd_builder()` now exports `PYTHONPATH` the same way
   `cmd_context()` already does, before invoking `gateway.builder_cli`:

   ```bash
   PYTHONPATH="$KITTY_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
     "$python_bin" -m gateway.builder_cli "$@"
   ```

2. **`gateway/builder_cli.py`** — `_cmd_initiative_doctor` called
   `run_doctor()` with no `repo_root`, so the repo-identity check fell back to
   `Path.cwd()`. That's a second, related cwd-dependency: run `./kitty builder
   initiative doctor` from outside the checkout and the identity check
   inspects whatever git repo the shell happens to be sitting in (or fails
   outright). Fixed by passing the launcher's own known-good root:

   ```python
   from gateway.paths import ROOT
   result = run_doctor(repo_root=ROOT)
   ```

   `ROOT` is derived from `__file__`, not cwd, so this is correct both at the
   repo root and inside a Builder worker's task worktree.

Verified directly (not just by inspection):

```
$ ./venv/bin/python -m gateway.builder_cli initiative doctor --json   # from repo root
ok: True   Counter({'PASS': 12, 'WARN': 2})

$ cd /tmp && /home/user/kitty/kitty builder initiative doctor --json  # from /tmp
ok: True   Counter({'PASS': 12, 'WARN': 2})
```

Both pass now; before the fix the second one crashed with the
`ModuleNotFoundError` above. This is the real bug, genuinely fixed, from any
directory, with or without `venv/`.

## Where the fix and the test disagree

`tests/test_paths_builder_canonical.py` still fails after both fixes — for a
**different** reason than before:

```
FileNotFoundError: [Errno 2] No such file or directory: PosixPath('/tmp/canonical-kitty/.git')
```

Cause, confirmed by reading the test: it fakes both `git` and `python3.12` on
`PATH`. The fake `git` always prints the literal string
`/tmp/canonical-kitty/.git` no matter what subcommand is passed. That's fine
for the *one* real git call the bash launcher makes (`git rev-parse
--git-common-dir`, used to compute `KITTY_BUILDER_DATA_DIR`). It breaks any
second git call, because `_check_repo_identity()` in
`gateway/builder_doctor.py` then runs `git config --get remote.origin.url`
with `cwd` set to that same fake, nonexistent path, and `subprocess.run`
can't set `cwd` to a directory that isn't there.

The test's fake `python3.12` binary only works at all when `venv/` is absent —
it just echoes `KITTY_BUILDER_DATA_DIR` and exits, never touching real Python.
`cmd_builder()` always prefers `venv/bin/python` over `PATH` when `venv/`
exists (correctly — that's the whole point of pinning a venv), so once
`venv/` exists, the real doctor code runs for real and the fake `git`'s
single-call design can't keep up.

Confirmed this is inherent to the test, not to the fix, by removing `venv/`
entirely and re-running: the test passes cleanly with no code changes,
because the launcher then uses the fake `python3.12` and never calls the real
doctor at all.

Per the task brief, this test is one of the two known environment-only
failures and was explicitly out of scope to edit. It is not fixed. The real
bug it was meant to catch (module import breaking under `venv/` + foreign
cwd) is fixed and independently verified above by direct reproduction outside
pytest.

## Pass/fail counts, before vs after

Both runs: `./venv/bin/python -m pytest tests/ -q --tb=line`, same container,
same `venv/`.

| | before | after |
|---|---|---|
| passed | 4216 | 4216 |
| failed | 2 | 2 |
| skipped | 2 | 2 |
| deselected | 2 | 2 |

Same two tests fail before and after: `test_operator_pause_between_attempts_stops_retry`
(untouched, pre-existing) and `test_paths_builder_canonical.py` (same test,
different underlying line — see above). No regressions. No new failures.

## Step 2 — initiative manifest

Wrote `data/kittybuilder/manifests/builder-cycle-proof.json` (one initiative,
one packet, `launcher-cwd-fix`, `max_attempts: 2`,
`allowed_paths: ["kitty", "gateway/builder_cli.py", "gateway/paths.py", "tests/"]`,
`validation_commands: ["./venv/bin/python -m pytest tests/test_paths_builder_canonical.py -q"]`).

Note: `data/` is entirely gitignored in this repo (`data/*` in `.gitignore`,
only `data/.gitkeep` tracked) — that's the existing convention for
KittyBuilder's runtime state, and this manifest follows it. It is not
committed; this note is the durable record of its contents.

```
$ ./venv/bin/python -m gateway.builder_cli initiative validate data/kittybuilder/manifests/builder-cycle-proof.json
warning: manifest looks prototype-shaped (T2: allowed_paths span >= 2 subsystems) but no packet id ends in '-proto'
OK: initiative 'builder-cycle-proof', 1 packet(s), sha256 ea5c8e7e8758…
exit: 0
```

(Advisory lint warning only — allowed_paths spans `kitty`/`gateway`/`tests`,
which is accurate for this fix; did not rename the packet id to chase the
lint.)

```
$ ./venv/bin/python -m gateway.builder_cli initiative apply data/kittybuilder/manifests/builder-cycle-proof.json
created: initiative 'builder-cycle-proof' (1 packet(s), sha256 ea5c8e7e8758…)
  launcher-cwd-fix -> kb_mswkpquu_3908
exit: 0
```

## Step 3 — driving the packet through Builder

The literal command from the task brief doesn't run as given:

```
$ ./venv/bin/python -m gateway.builder_cli initiative run-packet builder-cycle-proof launcher-cwd-fix --json
error: provide --free, --paid, or a non-empty --worker-command JSON array
exit: 1
```

`run-packet` requires naming a worker. `--free` and `--paid` both route
through a real model provider — explicitly out of scope here (no provider API
keys exist in this container and none can be added). Used
`--worker-command '["true"]'` instead: a deterministic, zero-API worker
command, already an established pattern in this repo's own test suite
(`tests/test_builder_cli.py`, `tests/test_builder_loop.py` both use `true`
and `false` this way) for exercising the pipeline without a real
implementation.

```
$ ./venv/bin/python -m gateway.builder_cli initiative run-packet builder-cycle-proof launcher-cwd-fix --worker-command '["true"]' --json
```

Result: `outcome: "exhausted"`, both attempts `outcome: "failed"`, reason:
`"builder-cycle-proof/launcher-cwd-fix has used 2/2 attempts; operator
intervention required"`. Full JSON preserved at
`data/kittybuilder/attempts/kb_mswkpquu_3908/{1,2}/run-manifest.json` (local,
gitignored per the `data/` convention above).

## Step 4 — what actually happened, honestly

The pipeline ran for real and stopped at a real, identifiable step. It did
**not** complete a validated cycle. Here is exactly how far it got and where
it stopped:

1. **Queue + lease** — worked. `queue list --json` shows task
   `kb_mswkpquu_3908`, `bridge_source: "initiative"`,
   `bridge_external_id: "builder-cycle-proof/launcher-cwd-fix"`.
2. **Worktree provisioning** — worked. Builder created
   `.worktrees/kittybuilder/kb_mswkpquu_3908` on branch
   `kittybuilder/kb_mswkpquu_3908`, cut from clean, up-to-date `main` (this
   container's `origin/main`, i.e. **without** the two fixes above — Builder
   always branches from `main`/`origin/main`, not from the interactive
   session's in-progress feature branch).
3. **Brief generation** — worked. `data/kittybuilder/runs/run_mswkrrsy_cfdf/brief.md`
   has the correct title, objective, acceptance criteria, and allowed-paths
   fence pulled straight from the manifest.
4. **Worker dispatch** — worked mechanically: `true` ran, exited 0, made no
   changes (`"changed_paths": []`, `"dirty_files": []`).
5. **Attempt finalization — this is where it stopped.** Both attempts failed
   with: `"worker did not write a implementation result to
   .../implementation.json"`. Builder requires every worker to write a
   structured implementation report; a no-op `true` command never does, so
   there is nothing for Builder to validate against. **Validation never ran**
   — `validation_json` is `null` on both attempt rows. This is not a
   validation failure; it's a worker-contract failure, one step earlier.
6. **Exhaustion** — after 2/2 attempts (the packet's own `max_attempts`
   policy), the packet moved to `blocked` (`blocked_reason:
   "shadow_run_complete"` — Builder's own label, confirming it correctly
   recognized this as a no-push shadow run), and the initiative moved to
   `failed`, needing operator review. `initiative report` wrote
   `data/kittybuilder/reports/builder-cycle-proof-20260817T014852Z.md`
   confirming the same state.

**Why it stopped there, in plain terms:** getting further — an attempt that
actually writes code and clears validation — needs a worker that can think
(an AI coding agent, via `--free` or `--paid`). This container has no
provider credentials and the task brief marks that explicitly out of scope.
So the honest ceiling for this proof, in this environment, is: queue → lease
→ worktree → brief → worker dispatch → attempt exhaustion → operator-review
handoff. That is six of Builder's mechanics genuinely exercised end to end.
Validation, independent review, recovery, and publication were not reached
because no attempt produced an implementation to validate.

## Step 5 — status

Not merged. Draft PR opened against `main` from
`claude/builder-cycle-proof-37nppd`; CI being driven green; PR not merged per
task instructions.

## Cleanup notes

- `data/kittybuilder/manifests/`, `attempts/`, `runs/`, `reports/` — all
  gitignored (`data/*`), left in place as local evidence; not committed.
- `.worktrees/kittybuilder/kb_mswkpquu_3908` — gitignored (`.worktrees/`),
  left in place; Builder owns cleanup of its own worktrees.
- Builder queue now has one `blocked` task (`kb_mswkpquu_3908`) and one
  `failed` initiative (`builder-cycle-proof`) sitting in
  `data/kittybuilder/builder_queue.db`, awaiting operator decision (repair,
  cancel, or leave as the recorded proof artifact). No further action taken
  on it — deciding whether to clean up the queue entry is Jacob's call, not
  something this task should silently resolve.
