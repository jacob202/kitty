# Dependency Audit

Concrete procedure for the dependency boundary — the supply chain as a failure
path. Use the exact vocabulary from `LANGUAGE.md` → "Dependency boundary":
**dependency boundary**, **silent upgrade**, **ghost dependency**, **version
drift**, **pinned**.

Dependency hygiene is this skill's boundary facet, not a separate skill (see the
`improve-codebase` and `maintain-repo` routers). This reference is the executable
half: the vocabulary says what is wrong; this says how to find it, here.

## Sources of record

| Surface | Path | Notes |
|---|---|---|
| Python (root) | `requirements.txt` | Installed by CI tests/typecheck; the gateway runtime set |
| Python (worker) | `workers/comfy_worker/requirements.txt` | Separately deployed service; **deliberately** pins `fastapi 0.140.0` / `pydantic 2.12.5` against the gateway's `0.141.1` / `2.13.4` — the tests.yml typecheck comment records why (pip would be unresolvable). Deliberate divergence is documented, not a defect. |
| Python (MCP) | `mcp/builder/requirements.txt`, `mcp/imagen/requirements.txt` | Typecheck installs these; keep visibility on their pins |
| Frontend | `gateway/kitty-chat/package.json` + `package-lock.json` | CI uses `npm ci` — the lockfile is the install authority |
| Tooling | `pyproject.toml`, `uv.lock`, `pytest.ini` | `pyproject.toml` is tool configuration, not a package definition (per the 2026-07 documentation audit) |
| Read-only clones | `.slim/clonedeps/repos/` | Inspect, never edit (AGENTS.md) |

## Existing machinery (cite it, don't re-run it)

| Runner | What it does | Truth level |
|---|---|---|
| `nightly-health.yml` → `deptry` | Declared-vs-imported analysis | **Advisory**; baseline 65 findings (2026-07-15), mostly optional deps (`docx`, `fitz`, `pypdf`) and transitive imports (`starlette`, `google`); the workflow itself says "Configure `deptry.toml` before gating" |
| `nightly-health.yml` → `pip-audit` | Python advisory scan | **Advisory** |
| `tests.yml` → `kitty-chat` job → `npm audit --audit-level=high` | Frontend advisories | **Advisory** (`continue-on-error`) |
| Dependabot PRs | Version bumps | Subject to the auto-merge prohibition below |

A clean advisory run is **not** an audit result — advisories have no gate and no
disposition owner. This procedure supplies the triage; the nightly supplies raw
output.

## Checks

Run only the checks the request needs; record the exact command and its output as
evidence.

1. **Declared-vs-imported (ghost + hidden).** Run `deptry .` and compare the
   current count against the recorded baseline rather than reporting "N findings"
   as new. A **ghost dependency** (declared, never imported) is hidden evidence:
   either use it or remove it — with the suite passing afterwards. A hidden
   dependency (imported, only resolved transitively) is the mirror defect: the
   build depends on someone else's pin.
2. **Pinning and silent upgrades.** For each manifest, find unpinned or loosely
   ranged entries that can drift on the next install. Confirm the install path
   actually uses the lock (`npm ci` does; a bare `pip install -r` does not
   enforce transitive pins). A **silent upgrade** is the defect; a deliberate,
   documented pin is the fix. Bounded ranges (`>=x,<y`) are **bounded**, not
   **pinned** — they cannot drift to a new major, but they still float inside
   the range, so classify them separately from open-ended requirements and never
   call a bounded set pinned.
3. **Lockfile reality.** A lockfile that locks nothing is inert config: a
   `uv.lock` carrying no packages while nothing in `Makefile`, `scripts/`, or CI
   invokes `uv` implies lock management that is not happening. A lock the
   install path never consumes is not evidence of pinning — check that the lock
   is live before trusting it as one.
4. **Version drift.** Compare pins for the same package across the root and
   sub-requirements. Classify each hit: **documented-deliberate** (the comfy_worker
   case — cite the tests.yml comment and leave it) versus **accidental** (an
   unenforced invariant — the deployed tree silently runs two versions). Never
   "fix" a deliberate divergence; report it as context.
5. **Advisories with triage.** For pip-audit / npm audit findings, state:
   package, version, advisory id, whether the vulnerable path is reachable in
   this system, and the fix's blast radius. **Do not auto-bump** — see rules.
6. **Install-time execution.** Flag any dependency fetched from a git ref, URL,
   or build-script-running source: installs that execute third-party code are a
   boundary risk worth naming explicitly (this repo already treats build-script
   execution as a reviewed decision elsewhere).
7. **Env skew (mark unknowns).** Local venvs (`venv/`, `.venv/`) may differ from
   CI's environment. State what you verified and what you cannot — an
   unverifiable env is `unknown`, never "fine."

## Output

Report findings in this skill's normal candidate shape: **Files** (manifests),
**Failure path** (how the quiet failure crosses the boundary), **Current
behaviour** (silent upgrade / ghost / drift / undispositioned advisory),
**Loud behaviour** (pin it, remove it, document the divergence, triage the
advisory), **Blast radius** (what changes without a diff, and how often the path
is taken). Rank by blast radius — a silent upgrade on the install path outranks a
ghost package.

## Rules

- **Never upgrade a dependency without explicit authorization.** AGENTS.md lists
  adding a heavy dependency among the never-do-unilaterally actions; dependency
  and lockfile roots are in the sensitive/irreversible subset
  (`scripts/pr_scope.py`).
- **Never auto-merge a dependency PR** — AGENTS.md names dependency/lockfile
  changes explicitly in the auto-merge prohibition.
- **Advisory output is evidence, not a verdict.** An advisory finding becomes a
  defect only with a reachable path and an impact statement.
- **A deliberate divergence is not drift.** When a pin conflict is documented
  (tests.yml is the example), cite the record and leave it — reopen only if the
  record is wrong.
- **Changing pins changes the lockfile is changing the deployed tree.** Any
  proposed fix names the exact manifests, the resolved versions before/after, and
  the tests that prove the suite still passes at the new resolution.
