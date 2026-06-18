# Kitty — Architecture Decisions & Roadmap

**Date:** 2026-06-11
**Status:** Living document. Revisit each decision at the trigger listed in its "When to reconsider" row.

**Assumptions made in this document:**

- Kitty runs on Jacob's Mac (the macOS-only integrations — AppleScript calendar, iMessage, ambient app detection, Apple Health — confirm this). Linux/Windows portability is a non-goal.
- There is exactly one user. No multi-tenancy, no auth beyond the existing `gateway/auth.py` shared-secret middleware.
- The Telegram bot is the current away-from-desk channel and works.
- "Daily use" means: Kitty is open or reachable every day, the morning brief gets read, and at least one chat/todo/memory interaction happens per day without anything needing a restart.

---

## 1. Diagnosis

Kitty does not have a feature problem; it has a **reliability and consolidation problem**. The repo contains ~90 backend modules, five completed build phases, two frontends' worth of artifacts (the live Next.js `kitty-chat` plus Open WebUI scripts, filters, and admin docs left over from an abandoned path), and four different storage substrates (JSON files, JSONL logs, ChromaDB, mem0) — but running it requires shepherding multiple processes (`gateway`, LiteLLM, formerly Open WebUI) with shell scripts that contain hardcoded paths, and the docs disagree with each other about which port the gateway is even on (`docs/ARCHITECTURE.md` says 8000, `CLAUDE.md` says 5001). Every new capability added before the stack runs itself unattended makes the daily-use goal *further* away, because each one is another thing that can be half-wired. The real problem to solve next is: **make the existing system boring to operate — one command, one storage story, one UI — and then let daily use, not enthusiasm, decide what gets built after that.**

---

## 2. Recommended architecture

Keep the shape you have. It is already right for a local-first single-user companion. The work is subtraction and hardening, not new structure.

```
┌─────────────────────────────────────────────────────────┐
│  Jacob's Mac (everything below runs here)                │
│                                                          │
│  launchd ──supervises──► Kitty Gateway (FastAPI :5001)   │
│                            │                             │
│                            ├── LiteLLM proxy (:8001)     │
│                            │     └── DeepSeek / Sonnet / │
│                            │         fallback chain      │
│                            ├── memory_graph (read API)   │
│                            │     ├── mem0 (facts)        │
│                            │     ├── ChromaDB (knowledge)│
│                            │     └── SQLite (everything  │
│                            │         currently in JSON)  │
│                            ├── voice_pipeline            │
│                            ├── buddy (mood/drift)        │
│                            └── telegram_bot (remote)     │
│                                                          │
│  Browser ──► kitty-chat (Next.js :3000, also the PWA)    │
└─────────────────────────────────────────────────────────┘
        ▲
        │ Tailscale (later) — phone reaches the same URLs
```

Principles:

1. **The gateway is the product.** Every client (web UI, Telegram, Siri shortcut, future PWA) is a thin view over the same HTTP/WebSocket surface. Never put logic in a client.
2. **One read path for context: `memory_graph`.** Already the rule in CLAUDE.md. Extend it with a write-side `StorageRouter` so write paths stop importing stores directly (Decision 9).
3. **Process supervision belongs to the OS.** launchd, not shell scripts in a terminal tab (Decision 6). The `com.kitty.*.plist` files already in `gateway/` show this was the instinct — finish it.
4. **No new substrates.** No new database, queue, framework, or UI until something currently in daily use demands it.

---

## 3. Roadmap

Each phase has an exit criterion. Do not start the next phase until the previous one's criterion has held for a few days of real use.

| Phase | Theme | Exit criterion |
|---|---|---|
| **A** (≈1 week) | Boring to operate | `kitty up` starts everything via launchd; survives reboot; `kitty doctor` is green; Open WebUI artifacts deleted; docs agree on ports |
| **B** (≈1–2 weeks) | One storage story | All JSON-file stores (chats, todos, buddy state, loops, nudges) live in one SQLite file; nightly backup of `data/`; 449-test baseline still green |
| **C** (≈1 week) | Daily-driver polish | Morning brief read on phone via Telegram daily; brief/chat first-token latency acceptable; zero manual restarts for a week |
| **D** (open-ended) | Agents & background tasks (the old "Phase 2") | One background agent (e.g. researcher or web monitor digest) produces output Jacob actually reads, on a schedule, unattended |
| **E** (only if earned) | Reach — PWA on phone via Tailscale, then maybe Tauri shell | Kitty used away from desk weekly |

Phases A–C are deliberately small. They are mostly deletion, wiring, and migration of code that already exists.

---

## 4. Coding-agent build plan

Tasks sized for one agent session each, with acceptance criteria. Test gate for every task: `python3.11 -m pytest tests/ -q --tb=short` stays at the current baseline (449 passed, 2 skipped) plus any new tests.

### Phase A — Boring to operate

| # | Task | Acceptance criteria |
|---|---|---|
| A1 | **Delete Open WebUI remnants**: `openwebui_filters/`, `openwebui_library_tools/`, `*_openwebui_*.sh`, `OPENWEBUI_ADMIN_SETTINGS.md`, related litellm config sections | Repo grep for `openwebui` returns only historical docs in `docs/archive/`; tests green |
| A2 | **Single launcher**: one `kitty` CLI (or Makefile) with `up`, `down`, `status`, `doctor`, `logs` subcommands; remove hardcoded `ROOT_DIR=` from remaining shell scripts | Fresh clone + `.env` → `kitty up` works; no absolute paths outside `gateway/paths.py` |
| A3 | **launchd service**: `com.kitty.gateway.plist` (+ LiteLLM) installed by `kitty install`; KeepAlive on crash; logs to `logs/` | Reboot Mac → gateway answers `/health` without manual action |
| A4 | **Docs reconciliation**: rewrite `docs/ARCHITECTURE.md` against reality (port 5001, kitty-chat as the UI, no Open WebUI); fold stale handoff files into `docs/archive/` | One canonical doc; CLAUDE.md and ARCHITECTURE.md agree |
| A5 | **`kitty doctor` hardening**: extend existing `doctor.py` to check gateway, LiteLLM, ChromaDB readability, mem0 init, Telegram token, disk space for `data/` | `kitty doctor` exits non-zero with a named failing check when any dependency is broken |

**Phase A progress (2026-06-18):**

- **A1 — done (verified).** Deleted the dead Open WebUI scaffolding (filters, library tools, standalone scripts, admin doc, theme CSS) plus the dead search/council chain. Test baseline moved 528 → 493 (each drop was a deleted test file, counted exactly). The genuinely-live but misleadingly-named frontend (`kitty-chat/src/lib/openwebui.ts`, the `owui*` API client) was left for a browser-verified rename.
- **A2/A3/A5 — built, NOT yet verified on macOS.** Added a single portable `kitty` launcher (`up`/`down`/`status`/`doctor`/`logs`/`install`/`uninstall`/`run-fg`) at the repo root; fixed hardcoded `ROOT_DIR=` in `start_gateway.sh`/`start_litellm.sh` to derive from the script location; added `com.kitty.gateway.plist` + `com.kitty.litellm.plist` (KeepAlive + RunAtLoad, path stamped by `kitty install`); rewrote `gateway/doctor.py` for the real stack. Verified here: bash syntax, plist XML, doctor parse, 493 tests still green. **Needs a Mac to confirm** `kitty up` actually boots the stack, launchd survives reboot, and `kitty doctor` goes green against running services.
- **A4 — done.** Port reconciled to 5001 everywhere; `ARCHITECTURE.md` rewritten; baseline refreshed in the docs.
- **Remaining to fully close A2:** the legacy multi-service launcher (`start_all.sh`, `stop_all.sh`, `status_all.sh`, `start_openwebui.sh`, `start_tool_servers.sh`, `doctor.sh`, `run_doctor_check.sh`) and `runtime_manifest.json` still carry hardcoded paths and Open WebUI wiring. They are superseded by the `kitty` script but kept for now because `tests/test_gateway_runtime_paths.py` pins them to the old world. Retiring that test + those scripts is its own focused pass.

### Phase B — One storage story

| # | Task | Acceptance criteria |
|---|---|---|
| B1 | **SQLite foundation**: `gateway/db.py` exposing one `aiosqlite` connection to `data/kitty/kitty.db`; schema migrations as numbered SQL files | New tests for open/migrate/CRUD; path defined in `paths.py` |
| B2 | **Migrate chats** (`data/kitty/chats.json` → `chats` table) behind the existing `/chats` routes; one-shot import script in `scripts/` | Routes unchanged from the client's perspective; old file imported then renamed `.bak` |
| B3 | **Migrate todos, loops, nudges, buddy state** the same way, one store per commit | Each store: same external behavior, tests green per commit |
| B4 | **Write-side `StorageRouter`** in `memory_graph` (or sibling module): `record(kind, payload)` routing to the right store; migrate `app.py` write call-sites | Direct store imports for writes removed from routes; CLAUDE.md rule updated |
| B5 | **Nightly backup**: launchd job that snapshots `kitty.db` (`VACUUM INTO`), ChromaDB dir, and mem0 data to a dated folder; keep 14 days | Backup file appears nightly; restore documented and tested once |

### Phase C — Daily-driver polish

| # | Task | Acceptance criteria |
|---|---|---|
| C1 | **Telegram morning brief push**: deliver the cached brief at a configured time (cron.py already runs) | Brief arrives on phone daily without prompting |
| C2 | **Latency pass**: measure first-token time on `/api/chat/completions`; ensure context build is concurrent (it mostly is) and trim any store that adds >200 ms | p50 first token < 2 s on `kitty-default` |
| C3 | **Failure visibility**: when the LLM fallback chain is exhausted or a store errors, surface it in the UI and `buddy` mood instead of silent degradation | Forced LiteLLM outage produces a visible, accurate error state |

### Phase D — Agents & background tasks

Define after C ships, informed by what daily use actually surfaces. Candidate first task: a scheduled researcher digest using the existing `researcher.py` + `web_monitor.py`, delivered through the brief.

---

## 5. UI/UX plan

`kitty-chat` already has the right bones (DashboardHome, TaskPanel, MoodAvatar, Cmd+K palette, voice in the composer). The plan is refinement, not new surfaces:

1. **One home, no dead panels.** DashboardHome is canonical (per TASKS.md). Audit the Tools tab and RightPanel for anything backed by a deleted or never-used endpoint and remove it. Every visible control must do something real.
2. **State honesty.** Loading skeletons exist; add explicit *error* and *empty* states for brief, todos, loops, insights. A panel that errors should say so, not render blank — this pairs with task C3.
3. **Keyboard-first.** Cmd+K is in; ensure new-chat, focus-composer, and toggle-voice have bindings. Companion software wins on friction.
4. **Mobile-width pass (pre-PWA).** Make DashboardHome and chat usable at 390 px width. This is the entire prerequisite for the Phase E PWA — no separate mobile UI.
5. **Buddy presence, not buddy noise.** MoodAvatar in the TopBar is enough surface for mood/drift. Resist dedicated mood pages or charts until something in daily use wants them.

Explicitly not in the plan: themes/customization, settings pages for things `.env` already controls, onboarding flows (one user, already on board).

---

## 6. Decision log

### D1 — Tauri vs Electron

| | |
|---|---|
| **Recommendation** | **Neither, for now.** Kitty stays a browser tab pointed at localhost. If a desktop shell is ever earned (Phase E), use **Tauri 2** wrapping the existing `kitty-chat` URL. |
| **Why** | The backend is a Python server, so neither framework's main job (bundling app logic) applies — the shell would only provide a window, tray icon, and global hotkey. Tauri uses the system WebView (~few-MB binary, low RAM) vs Electron shipping Chromium (~150 MB+); for a wrapper around an already-running localhost app, Tauri's tradeoffs win outright. Docs: [Tauri 2](https://v2.tauri.app/), [Electron](https://www.electronjs.org/docs/latest) |
| **Tradeoffs** | No shell means no tray icon, global hotkey, or native notifications for now (Telegram + `notify.py` cover notifications). Tauri later means a Rust toolchain in the repo and WKWebView quirks vs Chromium. |
| **Risks** | Building the shell early is pure overbuild risk: a third runtime to babysit before the server runs itself. |
| **When to reconsider** | After Phase C, if you catch yourself wanting a global "talk to Kitty" hotkey or menu-bar presence weekly. That's the Tauri trigger — and it's a ~1-day wrap, so deferring costs nothing. |

### D2 — Local database choice

| | |
|---|---|
| **Recommendation** | **SQLite**, one file (`data/kitty/kitty.db`), accessed via [`aiosqlite`](https://aiosqlite.omnilib.dev/) with plain SQL and numbered migrations. No ORM. |
| **Why** | Single user, single machine, single process — exactly SQLite's design center ([docs](https://sqlite.org/docs.html), [when to use](https://sqlite.org/whentouse.html)). It replaces the scattered JSON files (chats, todos, buddy state, loops) whose failure mode today is silent corruption on concurrent writes. Backup becomes one `VACUUM INTO`. An ORM adds a dependency and a learning surface for ~10 small tables. |
| **Tradeoffs** | Hand-written SQL and migrations; no automatic schema sync. JSON files were trivially human-inspectable; mitigate with `sqlite3` CLI and a `kitty db` shell shortcut. |
| **Risks** | A half-finished migration is worse than no migration — two sources of truth. Mitigate by migrating one store per commit behind unchanged routes (tasks B2–B3). |
| **When to reconsider** | Postgres only if Kitty ever becomes multi-device-writer or multi-user. Neither is on the horizon; don't pre-build for it. |

### D3 — Vector database choice

| | |
|---|---|
| **Recommendation** | **Keep ChromaDB** (`PersistentClient`, already wired in `archivist.py`/`knowledge.py`). Do not migrate vectors during Phase B. |
| **Why** | It works, it's local, the index is derived data (rebuildable via `scripts/kitty_manage.py ingest`), and the corpus is one person's documents — thousands of chunks, not millions. Switching vector stores is the classic overbuild move: high effort, zero user-visible change. Docs: [Chroma](https://docs.trychroma.com/) |
| **Tradeoffs** | One more on-disk substrate next to SQLite, and Chroma is a heavier dependency than the data size justifies. [`sqlite-vec`](https://github.com/asg017/sqlite-vec) would collapse vectors into `kitty.db`. |
| **Risks** | Chroma's API has churned across majors before; pin the version. Because the index is derived, the blast radius of any forced migration is one re-ingest. |
| **When to reconsider** | If a Chroma upgrade forces a rewrite anyway, or after Phase B if you want one-file backups badly — then move to `sqlite-vec` in a single re-ingest. Never adopt a server-based vector DB (Qdrant, Weaviate, pgvector) for this workload. |

### D4 — Local-first vs cloud sync

| | |
|---|---|
| **Recommendation** | **Strictly local-first. No cloud sync, ever, for the data layer.** Remote *access* (not sync) via [Tailscale](https://tailscale.com/kb) to the Mac in Phase E. Off-machine *safety* via the Phase B encrypted backup if desired. |
| **Why** | Kitty's value is precisely that iMessage excerpts, health data, journal, and ambient app usage stay on the machine. Sync would mean conflict resolution, schema versioning across replicas, and a privacy posture rewrite — enormous cost, and the actual need ("use Kitty from my phone") is met by the Telegram bot today and Tailscale later, because the Mac is always on. |
| **Tradeoffs** | Mac off or asleep ⇒ Kitty unreachable (configure the Mac to stay awake as a server). No multi-machine story. |
| **Risks** | Single disk = single point of loss — that's what task B5 (nightly backups, 14-day retention, off-machine copy optional) exists for. Tailscale misconfiguration could expose the gateway; keep `auth.py` enforced even on the tailnet. |
| **When to reconsider** | Only if a second always-on machine enters the picture. Even then, prefer "move the server" over "sync the data." |

### D5 — Open WebUI wrapper vs custom frontend

| | |
|---|---|
| **Recommendation** | **Custom frontend (`kitty-chat`) — already decided in practice. Finish the decision by deleting the Open WebUI scaffolding** (task A1). |
| **Why** | The repo has chosen: chats, dashboard, tasks, mood, and voice all live in kitty-chat; Open WebUI survives only as backup/sync shell scripts and admin docs. Kitty's UI needs (buddy avatar, brief dashboard, task rail, nudges) are companion-shaped, not chat-app-shaped — fighting a general chat UI's plugin system costs more than owning a Next.js app you already built. |
| **Tradeoffs** | You own every feature: model pickers, chat search, attachments arrive only when you build them. Open WebUI's ecosystem (tools, pipelines) is foregone — but the gateway's own skill/agent registry fills that role. |
| **Risks** | Frontend scope creep is *the* risk with an owned UI. The UI/UX plan above (§5) is deliberately a refinement list, not a feature list. |
| **When to reconsider** | Realistically never for Kitty. If you want a generic multi-model chat playground someday, run Open WebUI as a *separate* tool against LiteLLM — don't re-merge it into Kitty. |

### D6 — Background service vs bundled app server

| | |
|---|---|
| **Recommendation** | **Background service under launchd** (`KeepAlive`, `RunAtLoad`), not a server bundled into an app the user must open. Tasks A2–A3. Docs: [launchd jobs](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html) |
| **Why** | A companion that's only alive when an app window is open isn't a companion. The morning brief loop, cron jobs, web monitors, and Telegram bot all assume an always-on process. The repo already contains four `com.kitty.*.plist` files — the pattern is half-adopted; finishing it is cheaper than inventing an app-lifecycle story. launchd restarts crashes for free. |
| **Tradeoffs** | Debugging a daemon is less immediate than a terminal tab (mitigate: `kitty logs` tailing `logs/`, and a `kitty run-fg` foreground mode for development). Python env changes need a `kitty restart`. |
| **Risks** | launchd jobs failing silently at boot — `kitty doctor` (A5) plus a Telegram "I'm awake" ping covers detection. |
| **When to reconsider** | If Kitty ever ships to anyone else (it won't), a bundled app becomes the right call. For one operator-owner, the service model is strictly better. |

### D7 — Mobile companion approach

| | |
|---|---|
| **Recommendation** | **Now: the existing Telegram bot.** Phase E: **kitty-chat as a PWA over Tailscale** (mobile-width pass from §5 + a [web app manifest](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)). **No native app.** |
| **Why** | The Telegram bot already does brief/chat/stuck-nudges with zero additional infrastructure and real push notifications. A PWA reuses 100% of the UI you're building anyway. A native (or React Native/Flutter) app is a second codebase, signing certificates, and an app-store relationship — for one user. The Siri Shortcut (`docs/SIRI_SHORTCUT.md`) already covers voice-on-phone cheaply. |
| **Tradeoffs** | Telegram routes personal queries through a third party — keep payloads minimal and high-level there; the PWA path over Tailscale is fully private. PWAs on iOS have weak push/background support, which is exactly what Telegram compensates for. |
| **Risks** | Building mobile before Phase C means a flaky server experienced from a worse debugging position. Order matters: reliability first, reach second. |
| **When to reconsider** | Native app only if always-listening voice on the phone becomes the core use case — that's the one thing the PWA+Telegram combo can't do. |

### D8 — Browser extension timing

| | |
|---|---|
| **Recommendation** | **Defer indefinitely.** Not in any current phase. |
| **Why** | The plausible jobs — "watch this page," "save this to knowledge," "what's Jacob researching" — are already covered server-side by `web_monitor.py`, the knowledge ingest pipeline, and `web_tracker.py`/`patterns.py`. An extension adds a third client codebase, a manifest-v3 review cycle, and a permission-prompt trust decision, mostly to duplicate that. |
| **Tradeoffs** | No one-click "send current page to Kitty" (workaround: a bookmarklet hitting a gateway ingest endpoint — one afternoon, no extension). No in-page Kitty overlay — which is a feature, not a loss, for focus. |
| **Risks** | If built now it would be the fourth half-wired surface. The pattern this document exists to break. |
| **When to reconsider** | After a month of daily use, *if* the bookmarklet is being used many times a day and its friction is the complaint. The extension should be demanded, never speculative. |

### D9 — Memory architecture

| | |
|---|---|
| **Recommendation** | **Keep the three-layer split, keep `memory_graph` as the only read interface, add the write-side `StorageRouter` (task B4).** Layers: **episodic** (chats/journal/traces → SQLite after Phase B), **semantic facts** (mem0 — [docs](https://docs.mem0.ai/)), **reference knowledge** (documents → ChromaDB). Consolidation (episodic → semantic, the "dream loop") stays a Phase D candidate, not a current build. |
| **Why** | This separation already exists and matches how the data behaves: episodic data is append-only and time-ordered; facts are small, mutable, and deduplicated (mem0's job); knowledge is bulk, derived, and rebuildable. `memory_graph`'s adapter pattern (the deep-module rule in CLAUDE.md) is the architecture's best asset — it means storage substrates can change underneath (B-phase migrations, a future sqlite-vec move) without touching any caller. |
| **Tradeoffs** | mem0 is an opinionated dependency for fact extraction; owning a bespoke fact store would be simpler conceptually but re-implements extraction/dedup it already does. Three layers means three things `kitty doctor` must check. |
| **Risks** | The known failure mode is bypass: new code reading files directly instead of going through `memory_graph` (the CLAUDE.md rule exists because it happened). The `StorageRouter` closes the same hole on the write side. Second risk: unbounded context growth as stores fill — the C2 latency budget is the early-warning system. |
| **When to reconsider** | If mem0's extraction quality or maintenance becomes a recurring problem, replace it with a `facts` table in `kitty.db` + an explicit extraction prompt — behind the same adapter, callers unchanged. Revisit the dream-loop after Phase C, when there's enough episodic data for consolidation to be worth anything. |

---

## 7. Cut These For Now

Strict list. None of these get built until Kitty has survived **30 days of daily use without a manual restart**. Most have an explicit later trigger above; the rest should be re-proposed only by a need that shows up in actual use.

| Cut | Why it's tempting | Why it waits |
|---|---|---|
| **Tauri/Electron desktop shell** | "Real app" feel, tray icon, hotkey | Wrapper around a server that doesn't yet run itself (D1) |
| **Browser extension** | One-click page capture, in-page overlay | Server-side monitors + a bookmarklet cover it (D8) |
| **Native/RN mobile app** | Push, voice on the go | Telegram now, PWA later (D7) |
| **Cloud sync / hosted Kitty** | Access from anywhere | Tailscale gives access without surrendering local-first (D4) |
| **Vector DB migration (sqlite-vec or any server DB)** | One-file elegance | Zero user-visible benefit; Chroma works (D3) |
| **Multi-agent council expansion** (`council_graph`, `council_orchestrator`, `team_protocol`, `antigravity_tools`) | Architecturally fascinating | Already partially excluded from the test baseline; agents earn investment in Phase D only after one simple background agent proves useful |
| **Image generation UI** (`image_gen.py` + ComfyUI) | Fun | Already correctly skipped in TASKS.md; needs local ComfyUI, no daily-use pull |
| **Dream loop / memory consolidation** | The coolest memory feature | Needs months of accumulated episodic data to consolidate; Phase D+ (D9) |
| **Cron schedule editor UI** | Visible control over background jobs | A config file read by `cron.py` is enough for one user |
| **New integrations (email, Spotify, smart home, …)** | Each one makes Kitty "know more" | Context builder already injects 8+ sources; latency budget (C2) before breadth |
| **Settings/preferences UI** | Polish instinct | `.env` + config files; one user doesn't need a GUI for them |
| **Evals expansion** | Rigor feels virtuous | Keep the existing smoke evals frozen; invest only when a model-routing change actually misbehaves |

The test for un-cutting anything: *you reached for it three separate times during normal daily use and it wasn't there.* Not "it would be cool," not "while I'm in here anyway."
