# KittyBuilder MCP v2 Dogfood & Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make merged KittyBuilder MCP v1 operable and provable from Jacob's canonical Mac checkout with one `kitty mcp` command group, ordered non-mutating diagnostics, one real KPROOF Builder run, and fresh-session continuity evidence.

**Architecture:** Keep the merged v1 MCP tool surface and KittyBuilder authority unchanged. The `kitty` shell launcher owns only process lifecycle; focused Python modules under `mcp/builder/` own real-protocol probing, structured status/doctor output, and proof evaluation. The proof runner calls existing MCP tools and strict read-only Builder evidence projections; it never becomes a worker, approval authority, publisher, or merge engine.

**Tech Stack:** Bash, Python 3.12, MCP Python SDK/FastMCP v1 (`mcp[cli]>=1.27,<2`), existing KittyBuilder SQLite/read-only projections, Git/GitHub CLI observation, pytest, Vitest, Next.js build, Playwright.

## Global Constraints

- Base implementation is merged v1 commit `d54fd8966edd1f8a14802ed19e26a07917498caf`.
- KPROOF-001 remains the parent product mission and scope gate.
- Runtime behavior on Jacob's canonical Mac checkout outranks docs, unit tests, commits, MCP handshakes, and model narration.
- Do not add another orchestrator, database, queue, worker protocol, generic shell, generic filesystem mutation, model router, memory system, broad UI redesign, or new MCP tool solely for v2.
- Shell owns MCP process lifecycle; Python owns status/protocol/doctor/proof evaluation; KittyBuilder owns execution truth.
- `kitty mcp status` and `kitty mcp doctor` are observational. They must not install, migrate, start, recover, claim, requeue, publish, or mutate Builder state.
- MCP Streamable HTTP remains loopback-only: default host `127.0.0.1`, default port `8765`, endpoint `/mcp`.
- Do not install dependencies implicitly. Missing MCP SDK is a diagnosed runtime failure with one explicit install command.
- Free Builder execution is the proof default. `kitty mcp proof` never authorizes paid execution.
- Mission approval remains explicit and version-bound. `kitty mcp proof` accepts only an already-approved durable Mission and never calls `mission_approve`.
- Publication remains separately confirmed. `kitty mcp proof` never calls `publication_prepare` and never merges.
- Final KPROOF target is the audited Build Work recovery seam: contextual truthful **Retry this work**, reject `{ok:false}`, immediately refresh authoritative `runtime-manifest`, and display durable accepted → queued → running → validation → review → complete state.
- The later real KPROOF Mission uses exactly these product paths unless a newly prepared/approved Mission explicitly adds another path:
  - `gateway/kitty-chat/src/components/BuilderSurface.tsx`
  - `gateway/kitty-chat/src/lib/queries.ts`
  - `gateway/kitty-chat/tests/BuilderSurface.test.tsx`
  - `gateway/kitty-chat/tests/smoke/retry-work.spec.ts`
- The real KPROOF Mission includes exactly one deterministic runtime-product validation command prefixed `KITTY_KPROOF_RUNTIME=1 `:
  `KITTY_KPROOF_RUNTIME=1 cd gateway/kitty-chat && npx playwright test tests/smoke/retry-work.spec.ts`
- That marker labels an already-approved Builder validation command. It is not a new executor or permission boundary.
- Proof receipts live under ignored app-owned `data/kittybuilder/mcp-proof/` and are evidence caches only, never state authority.

---

## File Structure

- Modify `kitty` — add `mcp` help/dispatch and MCP-owned process lifecycle only.
- Create `mcp/builder/probe.py` — real MCP v1 Streamable HTTP client session and bounded tool-call decoding.
- Create `mcp/builder/operator.py` — non-mutating process/config/status/doctor checks in dependency order.
- Create `mcp/builder/operator_cli.py` — argparse + human/JSON rendering for status/doctor/proof.
- Create `mcp/builder/proof.py` — already-approved Mission observation/start, evidence gating, receipt writing, fresh-session comparison.
- Modify `gateway/builder_status_readonly.py` — strict read-only validation-command evidence index using command digests and no output tails.
- Modify `mcp/builder/context.py` — include latest durable `attempt_id` in `resume_context().current_work`.
- Create `tests/test_kitty_mcp_launcher.py`.
- Create `tests/test_mcp_builder_probe.py`.
- Create `tests/test_mcp_builder_operator.py`.
- Create `tests/test_mcp_builder_proof.py`.
- Modify `tests/test_builder_status_readonly.py`.
- Modify `tests/test_mcp_builder_continuity.py`.
- Modify `.github/workflows/tests.yml` — install MCP-specific requirements in pytest job without moving MCP into root runtime requirements.
- Modify `docs/KITTYBUILDER_MCP.md`.

---

### Task 1: Safe `kitty mcp` Process Lifecycle

**Files:**
- Modify: `kitty`
- Create: `tests/test_kitty_mcp_launcher.py`

**Interfaces:**
- Consumes existing launcher helpers: `pid_alive`, `pid_owned_by_kitty`, `pid_command`, `assert_port_available`, `$RUN_DIR`, `$LOG_DIR`, `$KITTY_ROOT`.
- Produces shell functions `cmd_mcp_up()`, `cmd_mcp_down()`, `cmd_mcp()`.
- Produces dispatch entry `mcp) shift; cmd_mcp "$@" ;;`.
- Runtime files: `logs/.run/mcp.pid`, `logs/mcp.log`.

- [ ] **Step 1: Write the failing lifecycle tests**

Create a miniature temp Kitty root using the real launcher, a fake `gateway/lib/load_env_safe.sh`, fake `venv/bin/python`, and fake `lsof`. The fake Python stays alive only for `-m mcp.builder.server`.

```python
# tests/test_kitty_mcp_launcher.py
from __future__ import annotations

import os
import shutil
import subprocess
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
        " trap 'exit 0' TERM INT; while true; do sleep 1; done\n"
        "fi\n"
        "printf '%s\\n' \"$*\" >> \"$TEST_MODULE_CALLS\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "lsof").write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \" $* \" == *\" -d cwd \"* ]]; then echo \"n$TEST_KITTY_ROOT\"; exit 0; fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    (fake_bin / "lsof").chmod(0o755)
    env = os.environ.copy()
    env.update(
        TEST_KITTY_ROOT=str(root),
        TEST_MODULE_CALLS=str(tmp_path / "calls.txt"),
        PATH=f"{fake_bin}:{env['PATH']}",
        KITTYBUILDER_MCP_PORT="18765",
    )
    return root, env


def test_mcp_up_is_idempotent_and_down_stops_only_owned_process(launcher_repo):
    root, env = launcher_repo
    subprocess.run([root / "kitty", "mcp", "up"], cwd=root, env=env, check=True)
    pid_file = root / "logs" / ".run" / "mcp.pid"
    first_pid = int(pid_file.read_text().strip())
    subprocess.run([root / "kitty", "mcp", "up"], cwd=root, env=env, check=True)
    assert int(pid_file.read_text().strip()) == first_pid
    subprocess.run([root / "kitty", "mcp", "down"], cwd=root, env=env, check=True)
    assert not pid_file.exists()
```

Also add tests that a non-loopback host is refused before launch, an unrelated live PID is never killed, and `status|doctor|proof` delegate to `mcp.builder.operator_cli`.

- [ ] **Step 2: Run RED**

```bash
python3.12 -m pytest tests/test_kitty_mcp_launcher.py -q
```

Expected: FAIL because `kitty mcp` is unknown.

- [ ] **Step 3: Implement minimal lifecycle code**

Add:

```bash
MCP_HOST="${KITTYBUILDER_MCP_HOST:-127.0.0.1}"
MCP_PORT="${KITTYBUILDER_MCP_PORT:-8765}"
MCP_PIDFILE="$RUN_DIR/mcp.pid"
MCP_LOG="$LOG_DIR/mcp.log"
```

`cmd_mcp_up()` must:
- reject hosts outside `127.0.0.1|localhost|::1`;
- if PID is alive, require both Kitty ownership and command containing `mcp.builder.server`, then return the same PID;
- remove a PID file only when its PID is dead;
- call `assert_port_available "MCP" "$MCP_PORT"` before a new launch;
- choose repo venv Python, fallback `python3.12`;
- launch exactly `python -m mcp.builder.server` under `nohup` with `PYTHONPATH=$KITTY_ROOT`, `KITTYBUILDER_MCP_TRANSPORT=streamable-http`, host/port env, log redirection, and atomic PID-file write;
- never install or repair anything.

`cmd_mcp_down()` must no-op for absent/dead PID and signal a live PID only when Kitty-owned and command-matched.

`cmd_mcp()`:

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

Update launcher help and top-level dispatch.

- [ ] **Step 4: Run GREEN**

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

### Task 2: Real Streamable-HTTP MCP Protocol Probe

**Files:**
- Create: `mcp/builder/probe.py`
- Create: `tests/test_mcp_builder_probe.py`
- Modify: `.github/workflows/tests.yml`

**Interfaces:**
- Produces `EXPECTED_TOOLS: frozenset[str]` containing the 16 merged-v1 tool names.
- Produces `FORBIDDEN_TOOLS = frozenset({"shell", "write_file", "git_push", "merge_pr", "sql"})`.
- Produces `endpoint_url(host: str, port: int) -> str` → `http://<host>:<port>/mcp`.
- Produces async context manager `open_session(endpoint: str)` yielding an initialized `ClientSession`.
- Produces `async call_tool_json(session, name: str, arguments: dict | None = None) -> dict`.
- Produces `async probe_protocol(endpoint: str, *, call_context: bool = True) -> dict`.

- [ ] **Step 1: Write failing real-protocol tests**

Start the actual server as a subprocess on an ephemeral loopback port. Do not call server Python functions directly.

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

Fixture subprocess:

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

Wait only for the TCP listener; the MCP call proves protocol health.

- [ ] **Step 2: Make pytest CI install the MCP-specific dependency**

Add to the pytest job install block in `.github/workflows/tests.yml`:

```yaml
pip install -r mcp/builder/requirements.txt
```

Do not change root `requirements.txt`.

- [ ] **Step 3: Run RED**

```bash
python3.12 -m pip install -r mcp/builder/requirements.txt
python3.12 -m pytest tests/test_mcp_builder_probe.py -q
```

Expected: FAIL because `mcp.builder.probe` does not exist.

- [ ] **Step 4: Implement the v1 client contract**

```python
from contextlib import asynccontextmanager
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
```

`open_session()` calls `await session.initialize()` before yielding. `call_tool_json()` accepts a dict `structuredContent`, otherwise JSON-decodes a single text content block; otherwise raises `ProbeError`. `probe_protocol()` calls `list_tools()` and optionally `kitty_context()`. A protocol success may carry domain `{ok:false}` and must preserve it.

- [ ] **Step 5: Run GREEN**

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

### Task 3: Ordered Non-Mutating Status and Doctor

**Files:**
- Create: `mcp/builder/operator.py`
- Create: `mcp/builder/operator_cli.py`
- Create: `tests/test_mcp_builder_operator.py`

**Interfaces:**
- `OperatorConfig(root: Path, host: str, port: int, pid_file: Path, log_file: Path)` with `endpoint` property.
- `load_config() -> OperatorConfig`.
- `process_status(config: OperatorConfig) -> dict`.
- `status_report(config: OperatorConfig) -> dict`.
- `async doctor_report(config: OperatorConfig, *, publication_required: bool = False) -> dict`.
- CLI subcommands `status [--json]`, `doctor [--json]`, `proof ...`.

- [ ] **Step 1: Write failing doctor-order tests**

Pin this order:

```python
EXPECTED_ORDER = [
    "checkout", "runtime", "process", "transport", "contract",
    "context", "builder", "repository", "github", "provider",
]
```

Tests must prove:
- checkout failure is `first_failure` and dependent checks are blocked;
- GitHub unavailable is external/warn unless publication is required;
- provider unavailable never triggers paid fallback;
- status/doctor never call Builder init/recover/mutation or MCP execution/publication functions;
- unhealthy top-level output has exactly one non-empty `next_action`.

- [ ] **Step 2: Run RED**

```bash
python3.12 -m pytest tests/test_mcp_builder_operator.py -q
```

Expected: import failure.

- [ ] **Step 3: Implement process/config observation**

`load_config()` uses `repo_tools.repo_root()`, v1 host/port defaults, and existing logs paths. `process_status()` uses only:
- `os.kill(pid, 0)` for liveness;
- fixed argv `ps -p <pid> -o command=`;
- fixed argv `lsof -a -p <pid> -d cwd -Fn`;
- fixed argv `lsof -tiTCP:<port> -sTCP:LISTEN`.

It never signals, deletes, starts, or rewrites anything.

- [ ] **Step 4: Implement dependency-ordered checks**

Every check returns:

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

Checks:
- checkout: `git rev-parse --show-toplevel` equals root;
- runtime: Python >=3.12 and installed MCP version >=1.27,<2;
- process: owned/alive PID and expected loopback listener;
- transport/contract/context: reuse Task 2 `probe_protocol()`;
- builder: only `build_status_snapshot_readonly` if DB exists; missing DB stays missing;
- repository: `git worktree list --porcelain`, executable `kitty`, existing root writable enough for Builder worktree creation without creating it;
- GitHub: `gh auth status` fixed argv + timeout, external unless publication required;
- provider: existing executable `scripts/kittybuilder_opencode_worker.sh`, `scripts/kittybuilder_opencode_reviewer.sh`, and `opencode` on PATH; no paid-provider calls.

Earliest local blocking failure wins `first_failure` and top-level `next_action`.

- [ ] **Step 5: Implement CLI rendering**

Human mode prints state, endpoint/PID, first problem, next action. JSON uses sorted indented JSON. Status states: `healthy|degraded|stopped|conflict|unavailable`. External warnings do not cause a local-failure exit.

- [ ] **Step 6: Run GREEN**

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

### Task 4: Strict Read-Only Attempt Evidence + Continuity Attempt Identity

**Files:**
- Modify: `gateway/builder_status_readonly.py`
- Modify: `mcp/builder/context.py`
- Modify: `tests/test_builder_status_readonly.py`
- Modify: `tests/test_mcp_builder_continuity.py`

**Interfaces:**
- `get_attempt_validation_index_readonly(attempt_id: int, *, db_path: Path) -> dict | None`.
- Per-command public evidence: `{index, command_sha256, passed, exit_code, duration_s}` only.
- `resume_context().current_work.attempt_id: int | None`.

- [ ] **Step 1: Write failing strict-read tests**

Persist deterministic validation containing a raw command and a sentinel secret/path in output. Assert:

```python
proof = get_attempt_validation_index_readonly(attempt_id, db_path=db_path)
assert proof["validation_status"] == "passed"
assert proof["commands"][0]["passed"] is True
assert len(proof["commands"][0]["command_sha256"]) == 64
assert "command" not in proof["commands"][0]
assert "output_tail" not in json.dumps(proof)
```

Also prove a missing DB remains absent. In continuity fixture assert `resumed["current_work"]["attempt_id"] == 4`.

- [ ] **Step 2: Run RED**

```bash
python3.12 -m pytest tests/test_builder_status_readonly.py tests/test_mcp_builder_continuity.py -q
```

Expected: FAIL for missing helper/attempt ID.

- [ ] **Step 3: Implement strict read-only evidence**

Reuse `_readonly_connection()`, query only `packet_attempts` by ID, parse `validation_json`, and hash raw persisted command internally:

```python
command_sha256 = hashlib.sha256(item["command"].encode("utf-8")).hexdigest()
```

Return no output tail and no raw command. Malformed durable JSON raises `RuntimeError`.

- [ ] **Step 4: Add latest attempt ID to `resume_context`**

`latest = _latest_attempt(current or {})` already exists. Add:

```python
"attempt_id": (latest or {}).get("id"),
```

to `current_work`.

- [ ] **Step 5: Run GREEN**

```bash
python3.12 -m pytest tests/test_builder_status_readonly.py \
  tests/test_mcp_builder_context.py tests/test_mcp_builder_continuity.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add gateway/builder_status_readonly.py mcp/builder/context.py \
  tests/test_builder_status_readonly.py tests/test_mcp_builder_continuity.py
git commit -m "feat(mcp): expose strict proof evidence identity"
```

---

### Task 5: KPROOF Evidence Runner Without New Authority

**Files:**
- Create: `mcp/builder/proof.py`
- Create: `tests/test_mcp_builder_proof.py`
- Modify: `mcp/builder/operator_cli.py`

**Interfaces:**
- Consumes Task 2 `open_session`, `call_tool_json`; Task 3 `doctor_report`; Task 4 `get_attempt_validation_index_readonly`; existing `get_initiative_readonly`.
- `ProofConfig(mission_id: str, endpoint: str, repo_root: Path, timeout_seconds: int = 3600, poll_seconds: float = 2.0, publication_required: bool = False)`.
- `async run_proof(config: ProofConfig) -> dict`.
- `write_proof_receipt(receipt: dict, *, root: Path) -> Path` using temp file + `os.replace`.
- CLI: `kitty mcp proof <mission-id> [--timeout SECONDS] [--poll SECONDS] [--require-publication] [--json]`.

- [ ] **Step 1: Write failing authorization/verdict tests**

Prove:
- proof never calls `mission_approve`, `publication_prepare`, paid execution, delete, or merge;
- when execution is needed, it calls only `execution_start` with `free=True, spend_authorized=False`;
- paused/blocked/needs-decision Mission => `incomplete` with blocker;
- missing validation/review/runtime marker cannot pass;
- required publication without PR => incomplete, not auto-publication.

- [ ] **Step 2: Write exact runtime-marker test**

Approved packet commands:

```json
[
  "cd gateway/kitty-chat && ./node_modules/.bin/vitest run tests/BuilderSurface.test.tsx",
  "KITTY_KPROOF_RUNTIME=1 cd gateway/kitty-chat && npx playwright test tests/smoke/retry-work.spec.ts"
]
```

Persist corresponding deterministic command results. Proof must:
1. read approved manifest with `get_initiative_readonly`;
2. find exactly one command beginning `KITTY_KPROOF_RUNTIME=1 `;
3. SHA-256 that exact command string;
4. match it to Task 4's read-only command index;
5. require that exact command result to be passed.

No marker, duplicate marker, hash mismatch, or failed marker => never pass.

- [ ] **Step 3: Write fresh-session continuity test**

Instrument session factory and assert two distinct sessions. Session 1 is fully exited before session 2 opens. Session 2 receives no prior response object and calls only:

```python
await call_tool_json(session2, "resume_context", {"mission_id": mission_id})
```

Compare exact Mission/manifest SHA, design path/SHA, plan path/SHA, original base SHA, task ID, attempt ID, PR number/head when present, blocker/unknown preservation, and one non-empty next action.

- [ ] **Step 4: Run RED**

```bash
python3.12 -m pytest tests/test_mcp_builder_proof.py -q
```

Expected: import failure.

- [ ] **Step 5: Implement evidence-gate state machine**

Only this flow is allowed:

```text
doctor
 -> session 1 resume_context/work_status
 -> verify already-approved identities
 -> execution_start(free=True, spend_authorized=False) only if eligible
 -> bounded poll work_status
 -> work_result
 -> strict validation/runtime-marker/review checks
 -> optional already-existing publication check
 -> close session 1
 -> open session 2
 -> resume_context only
 -> exact continuity comparison
 -> receipt verdict
```

Verdicts:
- completed + all required evidence + continuity => `pass`;
- deterministic validation failure or reviewer rejection => `fail`;
- authorization gate, paused/blocked work, unavailable external dependency, timeout, or missing evidence => `incomplete`.

Proof never retries workers; Builder owns repair/retry semantics.

- [ ] **Step 6: Implement atomic bounded receipt**

Path:

```text
data/kittybuilder/mcp-proof/<mission-id>-<UTC-compact>.json
```

Do not include raw MCP responses, worker output, validation output tails, environment variables, credentials, or secrets. Include v2 HEAD SHA, mission/artifact identities, task/attempt IDs, validation/review/runtime-marker verdict, publication identity when present, continuity session count `2`, verdict, blockers/unknowns, one next action.

- [ ] **Step 7: Wire CLI and exit codes**

Human output:

```text
MCP proof: PASS|FAIL|INCOMPLETE
Mission: <id>
Evidence: <receipt path>
Next: <one action>
```

Exit 0 pass, 1 fail, 2 incomplete/authorization/external unavailable.

- [ ] **Step 8: Run GREEN**

```bash
python3.12 -m pytest tests/test_mcp_builder_proof.py \
  tests/test_mcp_builder_operator.py tests/test_mcp_builder_probe.py \
  tests/test_mcp_builder_continuity.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add mcp/builder/proof.py mcp/builder/operator_cli.py tests/test_mcp_builder_proof.py
git commit -m "feat(mcp): add KPROOF evidence runner"
```

---

### Task 6: Operating Docs + Repository Gates

**Files:**
- Modify: `docs/KITTYBUILDER_MCP.md`

**Interfaces:**
- Documents exact `kitty mcp` commands, non-mutating doctor semantics, dependency remediation, runtime marker, proof receipt, and continuity invariant.

- [ ] **Step 1: Update docs with exact commands**

```bash
./kitty mcp up
./kitty mcp status --json
./kitty mcp doctor --json
./kitty mcp proof <approved-mission-id> --json
./kitty mcp down
```

Missing dependency remediation is only:

```bash
python3.12 -m pip install -r mcp/builder/requirements.txt
```

State that doctor never runs it automatically.

- [ ] **Step 2: Run focused v2 suite**

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

```bash
./venv/bin/ruff check gateway/ tests/ mcp/ workers/ scripts/runpod_worker_smoke_test.py
python3.12 -m mypy gateway/ mcp/ workers/ scripts/runpod_worker_smoke_test.py
```

Expected: PASS.

- [ ] **Step 4: Run full backend suite**

```bash
python3.12 -m pytest tests/ -q --tb=short \
  --cov=gateway --cov-report=term-missing --cov-fail-under=73
```

Expected: PASS.

- [ ] **Step 5: Run retained UI gates**

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

### Task 7: Canonical-Mac Operator Verification

**Files:**
- No committed product code unless verification exposes a defect.
- Runtime evidence only under existing ignored data/log paths.

**Interfaces:**
- Uses merged v2 checkout, real MCP server, and real operator commands.

- [ ] **Step 1: Capture exact checkout**

```bash
cd ~/Projects/kitty
git status --short --branch
git rev-parse HEAD
./kitty mcp down
```

Do not overwrite unrelated dirty work.

- [ ] **Step 2: Prove idempotent start + doctor**

```bash
./kitty mcp up
./kitty mcp up
./kitty mcp status --json
./kitty mcp doctor --json
```

Require same PID after repeated `up`, loopback-only endpoint, real initialize/list/call, expected governed v1 tools, no local blocking doctor failure.

- [ ] **Step 3: Prove owned shutdown**

```bash
./kitty mcp down
./kitty mcp status --json
```

Expected: stopped; unrelated processes untouched.

- [ ] **Step 4: Restart for dogfood**

```bash
./kitty mcp up
./kitty mcp doctor --json
```

Expected: ready for an already-approved real Mission.

- [ ] **Step 5: Record checkpoint**

Do not call v2 complete. Operator layer is verified; product proof remains Task 8.

---

### Task 8: Dogfood the Real Build Work Retry Repair Through MCP → Builder

**Files for the later separately approved product Mission:**
- Modify: `gateway/kitty-chat/src/components/BuilderSurface.tsx`
- Modify: `gateway/kitty-chat/src/lib/queries.ts`
- Modify: `gateway/kitty-chat/tests/BuilderSurface.test.tsx`
- Create: `gateway/kitty-chat/tests/smoke/retry-work.spec.ts`
- No backend file is pre-authorized. If live reproduction proves one necessary, prepare a new Mission version with that exact path and obtain approval before editing it.

**Interfaces:**
- User-visible target: contextual **Retry this work** for selected failed/stale work; approval preview; action-queue mutation; `{ok:false}` rejected; immediate `runtime-manifest` refresh; accepted → queued → running → validation → review → complete; mutation response alone never means complete.
- Enters Builder through merged v1 MCP `save_design`, `save_plan`, `mission_prepare`, `mission_approve`.

- [ ] **Step 1: Reproduce and inspect through conversational MCP**

Call `kitty_context`, then `repo_search`/`repo_read` for the four exact paths. Reproduce the broken interaction in the launched app before defining the Mission.

- [ ] **Step 2: Save design and plan through MCP**

Call `save_design`, then `save_plan` bound to its design SHA. The plan/manifest validation commands must include:

```text
cd gateway/kitty-chat && ./node_modules/.bin/vitest run tests/BuilderSurface.test.tsx
KITTY_KPROOF_RUNTIME=1 cd gateway/kitty-chat && npx playwright test tests/smoke/retry-work.spec.ts
```

- [ ] **Step 3: Prepare immutable Mission and stop for exact human approval**

Call `mission_prepare`. Present Mission ID, base/design/plan SHAs, the four allowed paths, acceptance criteria, validation commands, free/paid policy, and approval binding. General prior approval does not authorize this new exact Mission.

Expected: `state="prepared"`; no queue work created.

- [ ] **Step 4: After exact approval, accept once**

Call `mission_approve` with the exact prepared manifest/base/nonce. Confirm durable task IDs. Exact replay is idempotent.

- [ ] **Step 5: Run v2 proof**

```bash
./kitty mcp proof <mission-id> --json
```

Proof may start free Builder execution. It may not approve, spend, publish, merge, or coordinate workers itself.

- [ ] **Step 6: Require Builder-owned implementation/repair**

Builder must edit its isolated worktree, run deterministic validation including the exact runtime-marked Playwright command, obtain independent review, and repair findings through Builder attempts.

- [ ] **Step 7: Publication remains a separate explicit gate**

Only after explicit publication authorization call v1 `publication_prepare`. Never auto-merge. Then run:

```bash
./kitty mcp proof <mission-id> --require-publication --json
```

- [ ] **Step 8: Require fresh-session continuity**

Proof must close session 1, open a newly initialized session 2, call only `resume_context(mission_id=...)`, and match durable Mission/artifact/task/attempt/PR identities without pasted transcript.

- [ ] **Step 9: Final verdict**

Report v2/KPROOF success only when operator lifecycle, real protocol, no-manual-agent-coordination, real Retry interaction, deterministic validation, runtime-marked Playwright journey, independent review after repairs, fresh-session continuity, and proof receipt all pass. If publication was explicitly required, PR evidence must also exist.

Otherwise preserve evidence and report the exact failed boundary. Do not lower the pass condition.

---

## Plan Self-Review Notes

- **Spec coverage:** lifecycle, status, ordered non-mutating doctor, real protocol, proof receipt, runtime product evidence, fresh-session continuity, authorization gates, external-dependency classification, repository gates, canonical-Mac verification, and real KPROOF dogfood each have an implementation/acceptance task.
- **Placeholder scan:** no `TBD`, `TODO`, unnamed runtime test, or unknown product file remains. Product Mission scope is pinned to four exact frontend paths; any backend expansion requires a newly prepared/approved Mission.
- **Type consistency:** `OperatorConfig`, `ProofConfig`, `open_session`, `call_tool_json`, `doctor_report`, and `get_attempt_validation_index_readonly` have one signature each and are referenced consistently by later tasks.
- **No new authority:** no new durable workflow state exists; proof receipts are recomputable evidence only.
- **Runtime evidence:** exactly one approved command has the `KITTY_KPROOF_RUNTIME=1 ` marker; proof hashes that exact command and matches it to Builder's deterministic validation record.
- **Continuity gap:** `attempt_id` is added to the existing `resume_context` receipt rather than creating a second handoff format.
- **Dependency isolation:** MCP remains outside root requirements; pytest CI installs `mcp/builder/requirements.txt` specifically so real-protocol tests run.
