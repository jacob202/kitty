# KittyBuilder MCP v2 Dogfood & Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the merged KittyBuilder MCP bridge operable and provable from Jacob's canonical Mac checkout with one `kitty mcp` command group, ordered non-mutating diagnostics, one real KPROOF Builder run, and fresh-session continuity evidence.

**Architecture:** Keep v1's MCP tool surface and Builder authority intact. The `kitty` shell launcher owns MCP process lifecycle; focused Python modules under `mcp/builder/` own real-protocol probing, structured status/doctor output, and proof receipt logic. The proof runner invokes existing MCP tools and a strict read-only Builder evidence helper; it never becomes a worker, approval authority, publisher, or merge engine.

**Tech Stack:** Bash launcher, Python 3.12, MCP Python SDK/FastMCP v1 (`mcp[cli]>=1.27,<2`), existing KittyBuilder SQLite/read-only projections, Git/GitHub CLI observation, pytest, existing Builder validation/review machinery, Playwright for the final KPROOF runtime journey.

## Global Constraints

- Base implementation is merged v1 commit `d54fd8966edd1f8a14802ed19e26a07917498caf`.
- KPROOF-001 remains the parent product mission and scope gate.
- Runtime behavior on Jacob's canonical Mac checkout outranks docs, unit tests, commits, MCP handshakes, and model narration.
- Do not add another orchestrator, database, queue, worker protocol, generic shell, generic filesystem mutation, model router, memory system, broad UI redesign, or new MCP tool solely for v2.
- Shell owns MCP process dispatch/lifecycle; Python owns structured status, protocol probes, doctor, and proof evaluation; KittyBuilder owns execution truth.
- `kitty mcp doctor` and `kitty mcp status` are observational: they must not install, migrate, start, recover, claim, requeue, publish, or mutate Builder state.
- MCP Streamable HTTP remains loopback-only; default host `127.0.0.1`, default port `8765`, endpoint path `/mcp`.
- Do not install dependencies implicitly. Missing MCP SDK is a diagnosed runtime failure with an explicit install command.
- Free Builder execution is the proof default. Paid execution is never authorized by `kitty mcp proof`.
- Mission approval remains explicit/version-bound. `kitty mcp proof` accepts only an already-approved durable Mission and never calls `mission_approve`.
- Publication remains separately confirmed. `kitty mcp proof` never calls `publication_prepare` and never merges.
- Exact final live KPROOF target is the already-audited Build Work recovery seam: a contextual truthful **Retry this work** action that rejects `{ok:false}`, refreshes authoritative `runtime-manifest`, and shows durable accepted → queued → running → validation → review → complete state.
- The real KPROOF Mission must include exactly one deterministic runtime-product validation command prefixed `KITTY_KPROOF_RUNTIME=1 `; this is a marker on an already-approved Builder validation command, not a new execution mechanism.
- Proof receipts live under ignored app-owned `data/kittybuilder/mcp-proof/` and are evidence caches only, never state authority.

---

## File Structure

- Modify `kitty` — add `mcp` help/dispatch and MCP-owned process lifecycle only.
- Create `mcp/builder/probe.py` — MCP v1 Streamable HTTP client session, tool contract discovery, structured tool-call decoding.
- Create `mcp/builder/operator.py` — read-only process/config/status/doctor checks in dependency order.
- Create `mcp/builder/operator_cli.py` — argparse + human/JSON rendering for `status`, `doctor`, and `proof`.
- Create `mcp/builder/proof.py` — already-approved Mission observation/start, durable evidence gating, atomic proof receipt, fresh-session comparison.
- Modify `gateway/builder_status_readonly.py` — add strict read-only validation-command evidence projection with command digests/no output tails.
- Modify `mcp/builder/context.py` — add latest durable `attempt_id` to `resume_context().current_work`.
- Create `tests/test_kitty_mcp_launcher.py` — launcher lifecycle/ownership/idempotency tests.
- Create `tests/test_mcp_builder_probe.py` — real SDK protocol initialize/list/call tests.
- Create `tests/test_mcp_builder_operator.py` — ordered doctor, short-circuit, status, external/local classification tests.
- Create `tests/test_mcp_builder_proof.py` — proof authorization/evidence/runtime-marker/receipt/continuity tests.
- Modify `tests/test_builder_status_readonly.py` — strict non-mutating attempt-validation projection tests.
- Modify `tests/test_mcp_builder_continuity.py` — latest attempt identity in fresh-chat receipt.
- Modify `.github/workflows/tests.yml` — install the MCP-specific requirements in pytest job so the real-protocol test actually runs without moving MCP into Kitty core runtime dependencies.
- Modify `docs/KITTYBUILDER_MCP.md` — v2 operator commands, runtime marker convention, proof receipt semantics, live KPROOF procedure.

---

### Task 1: Add a Safe `kitty mcp` Process Lifecycle

**Files:**
- Modify: `kitty`
- Create: `tests/test_kitty_mcp_launcher.py`

**Interfaces:**
- Consumes: existing launcher helpers `pid_alive`, `pid_owned_by_kitty`, `pid_command`, `assert_port_available`, `$RUN_DIR`, `$LOG_DIR`, `$KITTY_ROOT`.
- Produces: shell functions `cmd_mcp_up()`, `cmd_mcp_down()`, `cmd_mcp()`, and dispatch entry `mcp) shift; cmd_mcp "$@" ;;`.
- Runtime files: `logs/.run/mcp.pid`, `logs/mcp.log`.
- Config: `KITTYBUILDER_MCP_HOST` default `127.0.0.1`; `KITTYBUILDER_MCP_PORT` default `8765`; `KITTYBUILDER_MCP_TRANSPORT=streamable-http` set by `up`.

- [ ] **Step 1: Write failing launcher lifecycle tests**

Create a temp miniature Kitty root containing the real `kitty` launcher, a minimal `gateway/lib/load_env_safe.sh`, a fake `venv/bin/python`, and a fake `lsof` earlier on `PATH`. The fake Python must stay alive for `-m mcp.builder.server` and record other module invocations.

```python
# tests/test_kitty_mcp_launcher.py
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


@pytest.fixture()
def launcher_repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "kitty"
    root.mkdir()
    shutil.copy2(Path(__file__).parents[1] / "kitty", root / "kitty")
    (root / "kitty").chmod(0o755)
    (root / "gateway" / "lib").mkdir(parents=True)
    (root / "gateway" / "lib" / "load_env_safe.sh").write_text(
        "load_env_assignments() { :; }\n", encoding="utf-8"
    )
    (root / "venv" / "bin").mkdir(parents=True)
    fake_python = root / "venv" / "bin" / "python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"${1:-} ${2:-}\" == \"-m mcp.builder.server\" ]]; then\n"
        "  trap 'exit 0' TERM INT\n"
        "  while true; do sleep 1; done\n"
        "fi\n"
        "printf '%s\\n' \"$*\" >> \"$TEST_MODULE_CALLS\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    lsof = fake_bin / "lsof"
    lsof.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \" $* \" == *\" -d cwd \"* ]]; then echo \"n$TEST_KITTY_ROOT\"; exit 0; fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    lsof.chmod(0o755)
    env = os.environ.copy()
    env.update(
        TEST_KITTY_ROOT=str(root),
        TEST_MODULE_CALLS=str(tmp_path / "module-calls.txt"),
        PATH=f"{fake_bin}:{env['PATH']}",
        KITTYBUILDER_MCP_PORT="18765",
    )
    return root, env


def test_mcp_up_is_idempotent_and_down_stops_only_owned_process(launcher_repo):
    root, env = launcher_repo
    subprocess.run([root / "kitty", "mcp", "up"], cwd=root, env=env, check=True)
    pid_file = root / "logs" / ".run" / "mcp.pid"
    first_pid = int(pid_file.read_text().strip())
    assert first_pid > 0
    subprocess.run([root / "kitty", "mcp", "up"], cwd=root, env=env, check=True)
    assert int(pid_file.read_text().strip()) == first_pid
    subprocess.run([root / "kitty", "mcp", "down"], cwd=root, env=env, check=True)
    assert not pid_file.exists()
```

Also add `test_mcp_public_bind_is_refused_before_launch()` and `test_mcp_status_doctor_proof_delegate_to_operator_cli()`.

- [ ] **Step 2: Run the narrow launcher tests and confirm RED**

Run:
```bash
python3.12 -m pytest tests/test_kitty_mcp_launcher.py -q
```
Expected: FAIL because `kitty mcp` is an unknown command.

- [ ] **Step 3: Implement the minimal shell lifecycle**

Add near existing service config:

```bash
MCP_HOST="${KITTYBUILDER_MCP_HOST:-127.0.0.1}"
MCP_PORT="${KITTYBUILDER_MCP_PORT:-8765}"
MCP_PIDFILE="$RUN_DIR/mcp.pid"
MCP_LOG="$LOG_DIR/mcp.log"
```

Add `cmd_mcp_up()` that:
- refuses any host not in `127.0.0.1|localhost|::1`;
- when `$MCP_PIDFILE` is alive, requires `pid_owned_by_kitty` and `pid_command` containing `mcp.builder.server`, then returns the same PID without launching another process;
- removes a stale PID file only when the PID is no longer alive;
- calls `assert_port_available "MCP" "$MCP_PORT"` before launch;
- chooses `$KITTY_ROOT/venv/bin/python`, falling back to `python3.12`;
- starts exactly `python -m mcp.builder.server` with `PYTHONPATH=$KITTY_ROOT`, Streamable HTTP env, `nohup`, stdout/stderr to `$MCP_LOG`, and records `$!` atomically in `$MCP_PIDFILE`;
- never installs packages and never runs repair/recovery.

Add `cmd_mcp_down()` that:
- returns success if the PID file is absent/stale;
- refuses to signal a live PID unless `pid_owned_by_kitty` is true **and** `pid_command` contains `mcp.builder.server`;
- TERM-stops only that process and removes only `$MCP_PIDFILE`.

Add `cmd_mcp()`:

```bash
cmd_mcp() {
  local sub="${1:-help}"
  shift || true
  case "$sub" in
    up) cmd_mcp_up ;;
    down) cmd_mcp_down ;;
    status|doctor|proof)
      local python_bin="$KITTY_ROOT/venv/bin/python"
      [[ -x "$python_bin" ]] || python_bin="$(command -v python3.12)"
      PYTHONPATH="$KITTY_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
        KITTYBUILDER_MCP_HOST="$MCP_HOST" KITTYBUILDER_MCP_PORT="$MCP_PORT" \
        "$python_bin" -m mcp.builder.operator_cli "$sub" "$@"
      ;;
    help|--help|-h) echo "Usage: kitty mcp up|down|status|doctor|proof" ;;
    *) echo "Usage: kitty mcp up|down|status|doctor|proof" >&2; return 2 ;;
  esac
}
```

Update header/help and top-level dispatch.

- [ ] **Step 4: Run launcher tests and syntax check**

Run:
```bash
bash -n kitty
python3.12 -m pytest tests/test_kitty_mcp_launcher.py -q
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add kitty tests/test_kitty_mcp_launcher.py
git commit -m "feat(mcp): add Kitty MCP lifecycle commands"
```

---

### Task 2: Build the Real Streamable-HTTP Protocol Probe

**Files:**
- Create: `mcp/builder/probe.py`
- Create: `tests/test_mcp_builder_probe.py`
- Modify: `.github/workflows/tests.yml`

**Interfaces:**
- Produces: `EXPECTED_TOOLS: frozenset[str]` containing the 16 merged-v1 tool names.
- Produces: `FORBIDDEN_TOOLS: frozenset[str] = {"shell", "write_file", "git_push", "merge_pr", "sql"}`.
- Produces: `endpoint_url(host: str, port: int) -> str` returning `http://<host>:<port>/mcp`.
- Produces: `async open_session(endpoint: str)` async context manager yielding initialized `mcp.ClientSession`.
- Produces: `async call_tool_json(session, name: str, arguments: dict | None = None) -> dict`.
- Produces: `async probe_protocol(endpoint: str, *, call_context: bool = True) -> dict`.

- [ ] **Step 1: Write failing real-protocol tests**

Use the actual MCP SDK, an ephemeral loopback port, and a subprocess running `python -m mcp.builder.server`. Do **not** import and call server tool functions directly.

```python
@pytest.mark.asyncio
async def test_probe_initializes_lists_governed_tools_and_calls_context(mcp_server):
    result = await probe.probe_protocol(mcp_server, call_context=True)
    assert result["initialized"] is True
    assert set(result["tools"]) == probe.EXPECTED_TOOLS
    assert probe.FORBIDDEN_TOOLS.isdisjoint(result["tools"])
    assert result["context"]["operation"] == "kitty_context"
    assert isinstance(result["context"]["ok"], bool)
```

The fixture starts the server with:

```python
env.update(
    PYTHONPATH=str(REPO_ROOT),
    KITTY_REPO_ROOT=str(REPO_ROOT),
    KITTYBUILDER_MCP_TRANSPORT="streamable-http",
    KITTYBUILDER_MCP_HOST="127.0.0.1",
    KITTYBUILDER_MCP_PORT=str(port),
)
proc = subprocess.Popen(
    [sys.executable, "-m", "mcp.builder.server"],
    cwd=REPO_ROOT,
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)
```

Wait only for the TCP listener before the MCP protocol call; the protocol assertion itself proves MCP health.

- [ ] **Step 2: Make CI install only the MCP test dependency**

In the `pytest` job install block, add:

```yaml
pip install -r mcp/builder/requirements.txt
```

Do **not** add MCP to root `requirements.txt`.

- [ ] **Step 3: Run the narrow test and confirm RED**

Run:
```bash
python3.12 -m pip install -r mcp/builder/requirements.txt
python3.12 -m pytest tests/test_mcp_builder_probe.py -q
```
Expected: FAIL because `mcp.builder.probe` does not exist.

- [ ] **Step 4: Implement the v1 client contract**

Use the pinned-v1 imports:

```python
from contextlib import asynccontextmanager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
```

`open_session()` must execute `await session.initialize()` before yielding. `call_tool_json()` accepts `result.structuredContent` when it is a dict; otherwise it may JSON-decode a single text content block, and raises a typed `ProbeError` when no structured object can be recovered. `probe_protocol()` calls `list_tools()` and optionally `kitty_context`; protocol success must not overwrite a domain-level `{ok:false}` receipt.

- [ ] **Step 5: Run protocol + existing server tests**

Run:
```bash
python3.12 -m pytest tests/test_mcp_builder_probe.py tests/test_mcp_builder_server.py -q
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add mcp/builder/probe.py tests/test_mcp_builder_probe.py .github/workflows/tests.yml
git commit -m "feat(mcp): add real protocol health probe"
```

---

### Task 3: Add Ordered, Non-Mutating Status and Doctor

**Files:**
- Create: `mcp/builder/operator.py`
- Create: `mcp/builder/operator_cli.py`
- Create: `tests/test_mcp_builder_operator.py`

**Interfaces:**
- Produces dataclass `OperatorConfig(root: Path, host: str, port: int, pid_file: Path, log_file: Path)` with `endpoint: str` property.
- Produces: `load_config() -> OperatorConfig` from canonical repo/environment.
- Produces: `process_status(config: OperatorConfig) -> dict`.
- Produces: `status_report(config: OperatorConfig) -> dict`.
- Produces: `async doctor_report(config: OperatorConfig, *, publication_required: bool = False) -> dict`.
- Produces CLI: `python -m mcp.builder.operator_cli status [--json]`, `doctor [--json]`, `proof ...`.

- [ ] **Step 1: Write failing doctor-order tests**

Tests monkeypatch individual check functions and assert the exact order:

```python
EXPECTED_ORDER = [
    "checkout",
    "runtime",
    "process",
    "transport",
    "contract",
    "context",
    "builder",
    "repository",
    "github",
    "provider",
]
```

Add tests proving:
- a checkout `fail` blocks/skips dependent later checks and becomes `first_failure`;
- GitHub unavailable is `warn/external` when publication is not required;
- provider unavailable is reported without authorizing paid fallback;
- status/doctor never call `gateway.builder_initiative.init_db`, recovery, queue mutation, MCP `execution_start`, or publication functions;
- top-level output has exactly one non-empty `next_action` when unhealthy.

- [ ] **Step 2: Run narrow tests and confirm RED**

Run:
```bash
python3.12 -m pytest tests/test_mcp_builder_operator.py -q
```
Expected: import failure for `mcp.builder.operator`.

- [ ] **Step 3: Implement configuration/process observation**

`load_config()` resolves repo root from `mcp.builder.repo_tools.repo_root()`, default host/port from v1, and PID/log paths under existing `logs/.run` + `logs`.

`process_status()`:
- reads PID file if present;
- uses `os.kill(pid, 0)` for liveness;
- uses fixed-argv `ps -p <pid> -o command=` and `lsof -a -p <pid> -d cwd -Fn` for ownership evidence;
- uses `lsof -tiTCP:<port> -sTCP:LISTEN` for listener PIDs;
- never signals, deletes, starts, or rewrites anything.

- [ ] **Step 4: Implement dependency-ordered doctor checks**

Use small check functions returning:

```python
{
    "id": "transport.initialize",
    "boundary": "transport",
    "state": "pass|fail|blocked|warn|unknown",
    "summary": "...",
    "evidence": {},
    "next_action": None,
    "classification": "local|external",
}
```

Required checks:
- checkout: fixed-argv `git rev-parse --show-toplevel` equals configured root;
- runtime: Python >=3.12 and `importlib.metadata.version("mcp")` parses to >=1.27,<2;
- process: owned/alive PID and expected loopback listener;
- transport/contract/context: use **Task 2** `probe_protocol()`; do not duplicate HTTP logic;
- builder: call `gateway.builder_status_readonly.build_status_snapshot_readonly` only when DB exists; missing DB is explicit unavailable/next action, and no schema initialization occurs;
- repository: fixed-argv read-only `git worktree list --porcelain`, executable `kitty`, writable `.worktrees/kittybuilder` parent capability without creating it;
- GitHub: `shutil.which("gh")` and fixed-argv `gh auth status` with timeout; external/warn unless publication required;
- provider: require existing executable `scripts/kittybuilder_opencode_worker.sh`, `scripts/kittybuilder_opencode_reviewer.sh`, and `opencode` on PATH for the free proof route; never probe paid providers or credentials by making model calls.

Earliest local blocking failure wins `first_failure` and top-level `next_action`. Later checks that depend on it return `blocked`; unrelated external checks may be omitted once an earlier local boundary makes them meaningless.

- [ ] **Step 5: Implement status + CLI rendering**

`status_report()` returns expected root, endpoint, process/listener facts, MCP protocol result when the process is alive, Builder DB availability, overall `healthy|degraded|stopped|conflict|unavailable`, and one next action.

`operator_cli.py` uses argparse. Human mode prints only state, endpoint/PID, first problem, and next action. `--json` uses `json.dumps(..., indent=2, sort_keys=True)` and exits non-zero only for blocking local failure/conflict, not advisory external warnings.

- [ ] **Step 6: Run doctor/operator tests**

Run:
```bash
python3.12 -m pytest tests/test_mcp_builder_operator.py tests/test_mcp_builder_probe.py -q
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add mcp/builder/operator.py mcp/builder/operator_cli.py tests/test_mcp_builder_operator.py
git commit -m "feat(mcp): add ordered MCP doctor"
```

---

### Task 4: Expose Strict Read-Only Attempt Evidence and Attempt Identity

**Files:**
- Modify: `gateway/builder_status_readonly.py`
- Modify: `mcp/builder/context.py`
- Modify: `tests/test_builder_status_readonly.py`
- Modify: `tests/test_mcp_builder_continuity.py`

**Interfaces:**
- Produces: `get_attempt_validation_index_readonly(attempt_id: int, *, db_path: Path) -> dict | None`.
- Response contains identifiers, outcome, validation status, and per-command `{index, command_sha256, passed, exit_code, duration_s}`; it must never include `output_tail` or raw command text.
- Enhances `resume_context().current_work` with `attempt_id: int | None` from its latest durable attempt.

- [ ] **Step 1: Write failing strict-read tests**

Create a temporary Builder DB through existing test helpers, persist a validation result containing a command and output with a sentinel secret/path, then assert:

```python
proof = get_attempt_validation_index_readonly(attempt_id, db_path=db_path)
assert proof["validation_status"] == "passed"
assert proof["commands"][0]["passed"] is True
assert len(proof["commands"][0]["command_sha256"]) == 64
assert "command" not in proof["commands"][0]
assert "output_tail" not in json.dumps(proof)
```

Also test a missing DB remains absent after the read attempt.

Update continuity fixture expectation:

```python
assert resumed["current_work"]["attempt_id"] == 4
```

- [ ] **Step 2: Run and confirm RED**

Run:
```bash
python3.12 -m pytest tests/test_builder_status_readonly.py tests/test_mcp_builder_continuity.py -q
```
Expected: FAIL for missing helper/attempt ID.

- [ ] **Step 3: Implement the read-only projection**

Reuse `_readonly_connection()`. Query only `packet_attempts` by ID. Parse `validation_json`; for each command compute:

```python
hashlib.sha256(command["command"].encode("utf-8")).hexdigest()
```

Return no output tail and no raw command. Malformed durable JSON raises a clear `RuntimeError`; do not reinterpret corruption as missing evidence.

- [ ] **Step 4: Add latest attempt ID to continuity receipt**

In `mcp/builder/context.py`, `latest = _latest_attempt(current or {})` already exists. Add:

```python
"attempt_id": (latest or {}).get("id"),
```

to `current_work` without changing existing fields.

- [ ] **Step 5: Run tests**

Run:
```bash
python3.12 -m pytest tests/test_builder_status_readonly.py tests/test_mcp_builder_context.py tests/test_mcp_builder_continuity.py -q
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add gateway/builder_status_readonly.py mcp/builder/context.py \
  tests/test_builder_status_readonly.py tests/test_mcp_builder_continuity.py
git commit -m "feat(mcp): expose strict proof evidence identity"
```

---

### Task 5: Implement the KPROOF Evidence Runner Without New Authority

**Files:**
- Create: `mcp/builder/proof.py`
- Create: `tests/test_mcp_builder_proof.py`
- Modify: `mcp/builder/operator_cli.py`

**Interfaces:**
- Consumes: Task 2 `open_session`, `call_tool_json`; Task 3 `doctor_report`; Task 4 `get_attempt_validation_index_readonly`; existing `get_initiative_readonly`.
- Produces dataclass `ProofConfig(mission_id: str, endpoint: str, repo_root: Path, timeout_seconds: int = 3600, poll_seconds: float = 2.0, publication_required: bool = False)`.
- Produces: `async run_proof(config: ProofConfig) -> dict`.
- Produces: `write_proof_receipt(receipt: dict, *, root: Path) -> Path` using atomic temp-file + `os.replace`.
- CLI: `kitty mcp proof <mission-id> [--timeout SECONDS] [--poll SECONDS] [--require-publication] [--json]`.

- [ ] **Step 1: Write failing authorization and verdict tests**

Use fake MCP sessions and a temp Builder DB. Prove:
- `run_proof()` never calls `mission_approve`, `publication_prepare`, paid execution, delete, or merge;
- when execution is needed it calls only `execution_start` with `free=True, spend_authorized=False`;
- a paused/blocked/needs-decision Mission yields `verdict="incomplete"` with the durable blocker;
- missing validation/review/runtime marker cannot yield pass;
- `--require-publication` missing PR yields incomplete, not auto-publication.

- [ ] **Step 2: Write the runtime-marker test**

Build an initiative whose approved packet declares:

```json
"validation_commands": [
  "python3.12 -m pytest tests/test_builder_surface.py -q",
  "KITTY_KPROOF_RUNTIME=1 cd gateway/kitty-chat && npx playwright test tests/retry-work.spec.ts"
]
```

Persist corresponding deterministic validation command results. The proof runner must:
1. read the approved manifest via `get_initiative_readonly`;
2. require **exactly one** command beginning `KITTY_KPROOF_RUNTIME=1 `;
3. compute its SHA-256;
4. match that SHA to Task 4's read-only command index;
5. require that exact command result to be passed.

No runtime marker, duplicate markers, hash mismatch, or failed marker command => `incomplete`/`fail`, never pass.

- [ ] **Step 3: Write the fresh-session continuity test**

Instrument the probe session factory and assert two distinct session instances are entered. Session 1 drives/observes work. It is fully exited before session 2 is opened. Session 2 receives no previous response object and calls only:

```python
await call_tool_json(session2, "resume_context", {"mission_id": mission_id})
```

Compare exact identities:
- Mission ID + manifest SHA;
- design path/SHA;
- plan path/SHA;
- original base SHA;
- task ID;
- attempt ID when available;
- PR number/head SHA when available;
- non-empty next action;
- blockers/unknowns are not erased.

- [ ] **Step 4: Run proof tests and confirm RED**

Run:
```bash
python3.12 -m pytest tests/test_mcp_builder_proof.py -q
```
Expected: import failure for `mcp.builder.proof`.

- [ ] **Step 5: Implement the proof state machine as an evidence gate**

`run_proof()` performs only:

```text
doctor
 -> session 1 resume_context/work_status
 -> verify already-approved artifact/Mission identities
 -> execution_start(free=True, spend_authorized=False) only when eligible
 -> bounded poll of work_status
 -> work_result
 -> strict validation/runtime-marker/review checks
 -> optional already-existing publication check
 -> close session 1
 -> open session 2
 -> resume_context only
 -> exact continuity comparisons
 -> receipt verdict
```

Terminal state handling:
- completed + all required evidence + continuity => `pass`;
- deterministic validation failure or review rejection => `fail`;
- authorization gate, paused/blocked work, unavailable external dependency, timeout, missing evidence => `incomplete`.

The proof runner must not retry workers itself; Builder owns repair/retry semantics.

- [ ] **Step 6: Implement bounded atomic receipt writing**

Receipt path:

```text
data/kittybuilder/mcp-proof/<mission-id>-<UTC compact timestamp>.json
```

Receipt fields match the approved spec. Do not include MCP raw responses, worker output, validation output tails, environment variables, tokens, or raw secrets. Include the v2 Git HEAD, mission/artifact SHAs, task/attempt IDs, validation/review/runtime marker verdict, publication identity when present, continuity session count `2`, verdict, blocker/unknowns, and one next action.

- [ ] **Step 7: Wire CLI**

`operator_cli.py` parses proof args and uses `asyncio.run(run_proof(...))`. Human output is:

```text
MCP proof: PASS|FAIL|INCOMPLETE
Mission: <id>
Evidence: <receipt path>
Next: <one action>
```

`--json` prints the receipt/result object. Exit codes: 0 pass, 1 fail, 2 incomplete/authorization/external-unavailable.

- [ ] **Step 8: Run proof/operator tests**

Run:
```bash
python3.12 -m pytest tests/test_mcp_builder_proof.py tests/test_mcp_builder_operator.py \
  tests/test_mcp_builder_probe.py tests/test_mcp_builder_continuity.py -q
```
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add mcp/builder/proof.py mcp/builder/operator_cli.py tests/test_mcp_builder_proof.py
git commit -m "feat(mcp): add KPROOF evidence runner"
```

---

### Task 6: Document the Operational Contract and Run Repository Gates

**Files:**
- Modify: `docs/KITTYBUILDER_MCP.md`

**Interfaces:**
- Documents exact `kitty mcp up|down|status|doctor|proof` commands.
- Documents no-auto-install/no-auto-repair behavior and exit semantics.
- Documents `KITTY_KPROOF_RUNTIME=1 ` validation marker and why it is evidence tagging, not shell exposure.
- Documents proof receipt path and the fresh-session invariant.

- [ ] **Step 1: Update operating docs**

Add a v2 section with copy-paste commands:

```bash
./kitty mcp up
./kitty mcp status --json
./kitty mcp doctor --json
./kitty mcp proof <approved-mission-id> --json
./kitty mcp down
```

Missing MCP dependency remediation is explicit:

```bash
python3.12 -m pip install -r mcp/builder/requirements.txt
```

State clearly that `doctor` never runs that command automatically.

- [ ] **Step 2: Run focused v2 suite**

Run:
```bash
python3.12 -m pytest \
  tests/test_kitty_mcp_launcher.py \
  tests/test_mcp_builder_server.py \
  tests/test_mcp_builder_probe.py \
  tests/test_mcp_builder_operator.py \
  tests/test_mcp_builder_proof.py \
  tests/test_mcp_builder_context.py \
  tests/test_mcp_builder_continuity.py \
  tests/test_builder_status_readonly.py -q
```
Expected: PASS.

- [ ] **Step 3: Run lint/typecheck**

Run:
```bash
./venv/bin/ruff check gateway/ tests/ mcp/ workers/ scripts/runpod_worker_smoke_test.py
python3.12 -m mypy gateway/ mcp/ workers/ scripts/runpod_worker_smoke_test.py
```
Expected: PASS.

- [ ] **Step 4: Run full backend suite**

Run:
```bash
python3.12 -m pytest tests/ -q --tb=short \
  --cov=gateway --cov-report=term-missing --cov-fail-under=73
```
Expected: PASS.

- [ ] **Step 5: Run retained UI gates**

Run:
```bash
cd gateway/kitty-chat && ./node_modules/.bin/vitest run
cd gateway/kitty-chat && node node_modules/next/dist/bin/next build
```
Expected: PASS.

- [ ] **Step 6: Commit docs**

```bash
git add docs/KITTYBUILDER_MCP.md
git commit -m "docs(mcp): add v2 dogfood operating guide"
```

---

### Task 7: Canonical-Mac v2 Runtime Verification

**Files:**
- No committed product code required unless verification exposes a defect.
- Runtime evidence only: `data/kittybuilder/mcp-proof/` and existing logs.

**Interfaces:**
- Uses merged v2 checkout, not a mocked server.
- Produces operator evidence proving lifecycle + protocol + doctor before KPROOF dogfood.

- [ ] **Step 1: Verify exact checkout before services**

Run on Jacob's canonical Mac:

```bash
cd ~/Projects/kitty
git status --short --branch
git rev-parse HEAD
./kitty mcp down
```

Record exact SHA and do not overwrite unrelated dirty work.

- [ ] **Step 2: Start and verify v2 lifecycle**

Run:
```bash
./kitty mcp up
./kitty mcp up
./kitty mcp status --json
./kitty mcp doctor --json
```

Acceptance:
- same PID after repeated `up`;
- loopback endpoint only;
- real MCP initialize/list/call passes;
- governed tool list matches v1;
- no local blocking doctor failure;
- external warnings remain classified separately.

- [ ] **Step 3: Prove clean shutdown ownership**

Run:
```bash
./kitty mcp down
./kitty mcp status --json
```
Expected: MCP state `stopped`; unrelated listeners/processes untouched.

- [ ] **Step 4: Re-start for dogfood**

Run:
```bash
./kitty mcp up
./kitty mcp doctor --json
```
Expected: ready for an approved real Mission.

- [ ] **Step 5: Record verification checkpoint**

Do not call v2 complete yet. Runtime operator layer is verified; KPROOF product proof remains Task 8.

---

### Task 8: Dogfood the Real KPROOF Build Work Repair Through MCP → Builder

**Files:**
- The exact feature files are intentionally determined by the approved Mission created through the conversation; expected current seam is `gateway/kitty-chat/src/components/BuilderSurface.tsx` plus its existing Builder query/action tests and any minimal backend error-semantic file proven necessary by live evidence.
- Runtime evidence: `data/kittybuilder/mcp-proof/`.

**Interfaces:**
- User-visible target from `docs/proof/TWO_WEEK_PROOF_AUDIT.md`: contextual **Retry this work** action for selected failed/stale work; truthful approval preview; action-queue mutation; `{ok:false}` rejected as error; immediate `runtime-manifest` refresh; accepted → queued → running → validation → review → complete durable states; no completion from mutation response alone.
- Must enter Builder as a new exact approved Mission using v1 MCP `save_design`, `save_plan`, `mission_prepare`, `mission_approve`.

- [ ] **Step 1: Use the conversational MCP path to inspect the live broken seam**

From a compatible MCP client/session:
- call `kitty_context()`;
- use `repo_search`/`repo_read` for Build Work source/tests;
- reproduce the dead interaction in the launched app before defining the Mission;
- keep runtime evidence separate from historical audit claims.

- [ ] **Step 2: Save the exact design and plan through MCP**

Call `save_design(...)`, receive the design commit SHA, then `save_plan(...)` with the design dependency. The plan must include one runtime Playwright validation command prefixed exactly:

```text
KITTY_KPROOF_RUNTIME=1 
```

Example shape (exact test path chosen from implemented journey):

```text
KITTY_KPROOF_RUNTIME=1 cd gateway/kitty-chat && npx playwright test tests/<retry-work-journey>.spec.ts
```

- [ ] **Step 3: Prepare the immutable Mission and stop for exact human approval**

Call `mission_prepare(...)`. Present Jacob the exact Mission ID, base/design/plan SHAs, allowed paths, acceptance criteria, validation commands, free/paid policy, and returned approval binding. Do **not** approve from old/general consent.

Expected: `state="prepared"`; no queue task yet.

- [ ] **Step 4: After exact approval, accept the Mission once through MCP**

Call `mission_approve(...)` with the exact prepared manifest/base/nonce. Confirm durable task IDs. Replaying the identical request must be harmless/idempotent.

- [ ] **Step 5: Run v2 proof**

Run:
```bash
./kitty mcp proof <mission-id> --json
```

The proof runner may start free Builder execution. It must not approve, spend, publish, merge, or coordinate workers itself.

- [ ] **Step 6: Require Builder-owned repair loop and running-product evidence**

Builder must:
- edit in its isolated worktree;
- run deterministic tests;
- run the runtime-marked Playwright journey against the launched product;
- obtain required independent reviewer verdict;
- repair findings through Builder attempts when necessary.

If the proof stops at a decision/authorization gate, resolve that gate explicitly and re-run proof; do not bypass it.

- [ ] **Step 7: Publication only after separate explicit confirmation**

If Jacob authorizes publication, invoke v1 `publication_prepare` separately from the proof command. Do not merge automatically. Re-run:

```bash
./kitty mcp proof <mission-id> --require-publication --json
```

Expected: PR identity/head/check evidence captured.

- [ ] **Step 8: Require fresh-session continuity PASS**

The proof runner must close its first MCP session, open a new initialized session, call only `resume_context(mission_id=...)`, and match exact durable identities without pasted transcript. Receipt must record `continuity.sessions=2` (or equivalent explicit field) and pass all equality invariants.

- [ ] **Step 9: Final KPROOF verdict**

Only report v2/KPROOF success if:
- operator lifecycle works on Mac;
- real MCP protocol works;
- no manual agent coordination was required;
- Builder implemented the real Retry interaction;
- deterministic validation + runtime-marked journey pass;
- independent review passes after repairs;
- fresh-session continuity passes;
- proof receipt verdict is `pass`;
- any publication evidence required by explicit authorization is present.

Otherwise report the exact failed boundary and preserve the evidence. Do not lower the pass condition.

---

## Plan Self-Review Notes

- **Spec coverage:** lifecycle, status, ordered non-mutating doctor, real protocol, exact KPROOF runtime evidence, proof receipt, fresh-session continuity, authorization boundaries, external-dependency classification, docs, deterministic gates, and canonical-Mac live acceptance are each assigned to a task.
- **No new authority:** no task adds queue/state ownership to MCP v2; the only new runtime file is an evidence receipt recomputable from Builder/Git/GitHub.
- **No new MCP tool:** v2 reuses the 16 merged-v1 tools. Attempt validation detail needed for proof is a local strict read-only Builder projection, not exposed as a conversational mutation surface.
- **Runtime evidence ambiguity resolved:** exactly one approved validation command carries the `KITTY_KPROOF_RUNTIME=1 ` marker; proof matches its SHA to durable deterministic validation results and requires that exact command to pass.
- **Continuity identity gap resolved:** v2 adds `attempt_id` to the existing `resume_context` receipt rather than inventing a second handoff format.
- **Dependency isolation preserved:** MCP stays out of root runtime requirements; CI's pytest job installs `mcp/builder/requirements.txt` specifically so the required real-protocol test is not silently skipped.
