# Builder execution map (issue mission Outcome B, slice B1)

What each `builder_*` module actually is: on the live path, reachable only from
tests, or dead. Every classification below names the call site that proves it.
Nothing here is inferred from a module's name or docstring.

**Method.** Every `.py` file in the repo outside `.venv/` and `node_modules/`
was scanned for references to each module. A reference counts as *production*
only when the importing file is not under `tests/` and not named `test_*`.
Prose-only mentions (a module named in a comment or docstring) were discarded
by hand; they are noted where they were the only hit, because a comment is not
a call site.

**Scope.** This slice changes no code. Decision D5 blocks B2–B10 until it lands.

## The one traced invocation

`./kitty builder initiative run-packet --id <initiative> --packet <packet>`

| # | Step | Proof |
|---|------|-------|
| 1 | Shell launcher dispatches the `builder` subcommand | `kitty:809` → `cmd_builder` at `kitty:513` |
| 2 | Launcher execs the Python CLI module | `kitty:518` — `"$python_bin" -m gateway.builder_cli "$@"` |
| 3 | Argument parser routes to the packet-run handler | `gateway/builder_cli.py:1894` → `_cmd_initiative_run_packet` at `gateway/builder_cli.py:1409` |
| 4 | Handler imports and calls the bounded repair loop | `gateway/builder_cli.py:1411` (import), `gateway/builder_cli.py:1427` (call) |
| 5 | Loop resolves the packet's isolated worktree | `gateway/builder_loop.py:1148` — `worktree_path(task_id, repo_root=repo_root)` |
| 6 | Loop dispatches the worker | `gateway/builder_loop.py:1173` — `run_worker(...)`, imported at `gateway/builder_loop.py:44` |
| 7 | Runner spawns the real process | `gateway/builder_runner.py:856` `run_worker` → `subprocess.Popen` at `gateway/builder_runner.py:1138` |

Step 4 is where the important negative result lives. `_cmd_initiative_run_packet`
calls `run_packet` with `worker_command=`, and never with `worker_session=`
(`gateway/builder_cli.py:1427-1438`). That single omission is what makes the
whole `WorkerSession` adapter layer unreachable in production — see below.

## Classification

### On the live path (26 of 27)

| Module | Proving production call site |
|---|---|
| `builder_attempt` | `gateway/builder_loop.py:38`, `gateway/builder_status.py:18`, `gateway/builder_cli.py:1309` |
| `builder_brief` | `gateway/builder_loop.py:42`, `gateway/builder_runner.py:44`, `gateway/builder_cli.py:579` |
| `builder_cli` | `kitty:518` — `python -m gateway.builder_cli`; the process entry point |
| `builder_commands` | `gateway/routes/builder.py:21` — `COMMAND_HANDLERS` |
| `builder_context` | `gateway/builder_loop.py:43` — `build_context_manifest`, `write_run_manifest` |
| `builder_contract` | `gateway/builder_cli.py:139` — `load_contract`, `run_contract` |
| `builder_control` (`gateway/routes/`) | `gateway/routes/register.py:13` (import), `:71` (router registration) |
| `builder_doctor` | `gateway/builder_cli.py:1538` — `run_doctor` |
| `builder_events` | `gateway/builder_commands.py:20`, `gateway/routes/builder.py:22` |
| `builder_identity` | `gateway/builder_loop.py:39` |
| `builder_initiative` | `gateway/builder_attempt.py:29`, `gateway/builder_commands.py:21`, `gateway/builder_cli.py:1055` |
| `builder_isc` | `gateway/builder.py:356` — `from gateway.builder_isc import (...)`; `gateway/builder.py` is itself live via `gateway/routes/integrations.py:198` |
| `builder_loop` | `gateway/builder_cli.py:1411`, `gateway/builder_run.py:30` |
| `builder_publish` | `gateway/builder_cli.py:721`, `gateway/builder_run.py:31` |
| `builder_queue` | 25 production importers; nearest `gateway/builder_attempt.py:30`, `gateway/builder_status.py:20` |
| `builder_queue_branch_leases` | `gateway/builder_queue.py:39` (re-export) |
| `builder_queue_db` | `gateway/builder_queue.py:37`, `gateway/builder_queue_leases.py:38`, `gateway/builder_queue_runs.py:166` |
| `builder_queue_leases` | `gateway/builder_queue.py:67`, `gateway/builder_commands.py:28` — `operator_release_task` |
| `builder_queue_runs` | `gateway/builder_queue.py:76` (re-export) |
| `builder_report` | `gateway/builder_cli.py:1293` — `generate_report` |
| `builder_run` | `gateway/builder_cli.py:1465` — `run_initiative` |
| `builder_runner` | `gateway/builder_loop.py:44`, `gateway/builder_attempt.py:984`, `gateway/builder_adapters.py:76` |
| `builder_scope` | `gateway/builder_identity.py:16`, `gateway/builder_runner.py:43` |
| `builder_status` | `gateway/context_receipt.py:1395`, `gateway/builder_runtime.py:55` |
| `builder_worker_session` | `gateway/builder_loop.py:57`, `gateway/builder_events.py:19`, `gateway/builder_runtime.py:22`, `gateway/builder_adapters.py:24` |

`builder_runtime` is live through `gateway/runtime_manifest.py:22`, which is
itself live via `gateway/routes/completions.py:28`.

### Implemented but unwired — reachable only from tests (1)

**`builder_adapters`** — `ShellWorkerSession` (`gateway/builder_adapters.py:44`)
and `OpenCodeServerSession` (`gateway/builder_adapters.py:305`) are complete
implementations of the `WorkerSession` interface. Nothing in production
constructs either one. The only importers are
`tests/test_builder_adapters.py:1` and `tests/test_worker_session_contract.py:18`.

The seam that would activate them exists and is tested: `run_packet` accepts
`worker_session=` (`gateway/builder_loop.py:803`), validates that exactly one of
`worker_command`/`worker_session` is supplied (`gateway/builder_loop.py:823-831`),
and routes to `_run_via_session` (`gateway/builder_loop.py:699`, called at
`gateway/builder_loop.py:1152`). The CLI simply never passes it.

This is the specced-versus-built gap in its purest form: the adapter layer, the
interface, the loop branch, and the contract tests all exist, and no user can
reach any of it. It is not dead code — deleting it would discard a working
seam — but "KittyBuilder supports pluggable worker backends" is false today at
the CLI.

### Dead (0)

No `builder_*` module is unreferenced by both production and tests.

## What this map does not establish

- **It is static.** References were resolved by reading imports and call sites,
  not by running the Builder. A module that is imported may still never execute
  on any real run. Only the traced invocation above was followed to a real
  `subprocess.Popen`.
- **One path, not all paths.** `builder_run.run_initiative`
  (`gateway/builder_cli.py:1465`) and the HTTP control plane
  (`gateway/routes/builder_control.py`) are separate entry points that this
  slice did not trace.
- **No runtime execution.** No packet was queued, no worker ran, no PR was
  opened. B8–B10 need a real runtime and remain out of reach here.

## Consequence for B2–B10

B2 is "eliminate contradictory launchers and dead entry points". This map says
the honest B2 finding is narrower and sharper than expected: there are no dead
`builder_*` modules to delete. There is one unwired adapter layer, and the fix
is a decision — wire `worker_session` through the CLI, or state plainly that
subprocess dispatch is the only supported backend and mark the adapters as an
unshipped seam. Doing neither is what leaves the docs describing a capability
the product does not have.
