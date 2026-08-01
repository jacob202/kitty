# Progress review — planning horizon, checkpoints, and verified reality

**Written:** 2026-07-31
**Verified against:** `origin/main` @ `aae7577`, GitHub Actions runs on `main`,
`./kitty context --agent`
**Question answered:** how far ahead have we actually planned, what are the
checkpoints, where are we on them, and what is genuinely proven to work?

Evidence rule used throughout: a thing is **verified** only if a command ran and
its output was read. Repository prose is a claim, not evidence. Where the only
available evidence is prose, this document says so.

---

## 1. How far the plan actually reaches

Short answer: **one phase, roughly a week wide. Everything past it is a bullet
list.**

`docs/ROADMAP.md` is the sole planning authority (ADR 0020). It contains:

| Horizon | What exists | Depth |
|---|---|---|
| Phase 1 — trust foundation | 7 ordered outcomes, 7 exit criteria, a named restart sequence (KTF-001) | Fully specified, executable |
| Phase 2 | **Nothing.** No section, no outcomes, no exit criteria | Does not exist |
| Later phases | 6 bullet lines (worker contracts, runtime projections, autonomy, product deepening, Image Studio direction) | Named only. No order, no owner, no exit criteria |
| "Done" | `docs/NORTH_STAR.md` §6 — a morning ritual that holds | Qualitative, deliberately not a checklist |

So the planning horizon is: **detailed for one phase that is now claimed
complete, and undefined for everything after it.** That is the headline finding.

### The Phase 2 contradiction

`docs/ACTIVE_MISSION.md` declares mission `KLF-001`, titled *"Phase 2 Life-First
Home Truth"*, status `running`, approved by Jacob 2026-07-31T11:29Z.

`docs/ROADMAP.md` contains no Phase 2. Grep confirms the string appears nowhere
in the roadmap or the authority map.

Phase 1's own exit criteria require that *"no active authority files contradict
the roadmap or active mission."* An active mission naming a phase the roadmap
does not define is exactly that contradiction. The work KLF-001 did is good and
correct — the problem is that it has no sequence to sit inside.

---

## 2. The checkpoint ladder as actually written

These live in three different files and were written at three different times.
Collected here for the first time:

**Checkpoint 1 — Move-in day** (`docs/packets/README.md`, D12, decided
2026-07-04). Five conditions, all product-facing:

1. Morning brief lands on the iPhone unprompted, with real mail and deadlines
2. Every active project shows one concrete next step
3. Benefits/admin paper is watched — photograph a letter, deadline escalates
4. Capture resurfaces at the right moment
5. Everything Kitty did is an auditable queue row; nothing sent without approval

Marked **reached 2026-07-05** on the strength of Waves 0–4 completing.

**Checkpoint 2 — Phase 1 exit** (`docs/ROADMAP.md`). Seven criteria:

- Python and frontend CI green from a clean checkout
- No active authority file contradicts the roadmap or mission
- Builder has ≥2 verified `free-exec` packets
- One unattended daylight run crosses packet failure and provider exhaustion
- One low-risk packet completes the full approved delivery path
- One real project completes the resume-loop proof end to end
- Status reconstructable from evidence without chat history

Marked **exited 2026-07-31** by `.claude/STATE.md` ("KTF-001 succeeded: all 9
scope items independently verified; Phase 1 exits").

**Checkpoint 3 — Phase 2.** Undefined.

**Checkpoint 4 — Later phases.** Six unordered bullets.

**Checkpoint 5 — North Star "done."** Mornings Jacob *wants* to open Kitty.

### Where we actually stand on Checkpoint 2

Two of the seven exit criteria are false as of this writing:

| Criterion | Status | Evidence |
|---|---|---|
| CI green from a clean checkout | **FALSE** | `Tests` workflow red on `main` for 19 consecutive runs since `a3c2fc62` (2026-07-30 15:31Z). Current run 30629260871 on `aae7577`: 2 of 6 jobs failing |
| No authority file contradicts the roadmap | **FALSE** | Mission KLF-001 names a Phase 2 the roadmap does not define |
| ≥2 verified `free-exec` packets | Unknown here | Builder DB absent in this checkout; `./kitty context --agent` reports `builder.state = unavailable` |
| Daylight run crossing failure boundaries | Prose only | `docs/initiatives/ktf-004-*` manifests exist; no runtime evidence readable from the repo |
| One low-risk packet through full delivery | Plausible | PR #325 did commit → push → PR → review → merge |
| Resume-loop proof on a real project | Prose only | STATE claims verification against live project data; not reproducible from repo |
| Status reconstructable without chat history | Partial | This document was reconstructable — but only after reconciling four contradicting files |

**Phase 1 has not met its own exit criteria.** The declaration that it exited
was made in `.claude/STATE.md`, which is a session checkpoint, not the roadmap
authority. Nobody updated `docs/ROADMAP.md` to match.

---

## 3. What is verified working — three honest tiers

Using the states mandated by `docs/FEATURE_REALITY_2026-07-28.md` (Working /
Partial / Planned). That document set the rule on 2026-07-28 and it has never
been applied to an actual list. This is that list.

### Tier A — verified by a command whose output was read

Source: GitHub Actions run 30629260871 on `main` @ `aae7577`, 2026-07-31 12:04Z.

| Gate | Result |
|---|---|
| `pytest` | **3418 passed, 1 failed**, 78% coverage (73% floor met) |
| `lint` (ruff) | pass |
| `typecheck` (mypy) | pass |
| `kitty-chat` (frontend unit + build) | pass |
| `hygiene` (vulture, lychee, deptry, pip-audit) | pass |
| `browser-smoke` (Playwright) | **0 passed, 14 failed, 10 skipped** |

That 3,418-test backend suite is the strongest asset in this repo. It is real,
it is broad, and it passes. Treat it as the foundation, not as decoration.

The single pytest failure is
`tests/test_cold_start_acceptance.py::test_clean_reader_can_resolve_all_cold_start_questions`,
which asserts the literal string `"Trust Foundation and Resume-Loop Proof"` is
in `docs/ACTIVE_MISSION.md`. The mission was legitimately retitled. The test
hardcodes prose that changes by design every mission — it will break again next
mission unless its *shape* is fixed, not its string.

The browser-smoke failure is more serious and is covered in §4.

### Tier B — built and merged, but only prose says it works end to end

From `docs/packets/README.md` (registry last updated **2026-07-14** — 17 days
stale) plus `docs/PROJECT_STATUS.md`:

Shipped and merged: state spine (001), inbox triage (002), action queue (003),
state home (004), Gmail read-only connector (005), dev-session resume (006),
delegation generator (007), knowledge library + expert retrieval (008),
de-faked loops/insights (009), capture-to-knowledge (010), brief v2 + push
(011), privacy boundary (012, later retired by ADR 0022), nudges/web_monitor
(013), honest gates (014), phone channel (015), next-step navigator (016),
benefits/admin rails (017), expert packs (018), project registry + resume
(021), memory taste (023).

Backend surface is genuinely large: 50 route modules under `gateway/routes/`,
57 UI components under `gateway/kitty-chat/src/components/`.

The caveat from `FEATURE_REALITY` still holds and is the honest reading:
capabilities were built in parallel, surfaced inconsistently, and documented
through stale snapshots. Breadth is not the problem. Integration is.

**Two of these are marked shipped but were never independently closed out:**

- **016 (next-step navigator)** — the packet explicitly says it closes out
  "after a week of Jacob judging real Bs, not on merge alone." No record of
  that week exists.
- **Move-in bar (all 5 criteria)** — declared reached 2026-07-05 by inferring
  it from packet completion. No single run has ever exercised all five
  end to end.

### Tier C — spec authored, zero shipped code

| # | Packet | State |
|---|---|---|
| 019 | Job search scaffold | ⏸ parked by Jacob ("plan it, don't build it") |
| 020 | GitHub read-only connector | 🧭 planned, never authored |
| 022 | Magic Kitty cross-project insight | 🚧 partial — route/module/tests on main (#153); executor contract + privacy hardening remain |
| 024 | Chat log idea mine | 📋 spec only |
| 025 | Imagegen pipeline v2 | 📋 spec only |
| 026 | Builder reliability | ◐ rails landed, closeout runs as 027 |
| 027 | Builder restart/recovery proof | 🚧 in Builder queue, state unknown here |
| 028 | Reasoning engine | 📋 spec only |

### Tier D — unknown, and must stay unknown

Builder runtime state. `data/kittybuilder/builder_queue.db` does not exist in
this checkout, so initiatives, attempts, leases, provider exhaustion, and
publication state are **unknown**, not empty. Same for actual product usage:
`data/kitty/` is empty here, so nothing in this repo can tell you whether Jacob
opened Kitty this week.

---

## 4. What is actually broken right now

Independently confirmed, and consistent with the review already sitting in
PR #326 (`docs/research/pr-review-48h-2026-07-31.md`, which found the same
things and is worth merging).

**B1 — the browser gate is dead, and it died silently.**
All 14 Playwright smoke tests fail. `browser-smoke` in `.github/workflows/tests.yml`
starts only the Next.js server, with no Python gateway behind it. `HealthGate`
in `KittyRuntimeProvider.tsx` fetches `/proxy/health`, gets nothing, and renders
a "Gateway offline" panel *instead of its children*, so `<main>` never mounts
and every spec times out on `waiting for locator('main')`.

Last green: `8790c21` at 03:39Z. First red: after `8828019 feat(ui): health
gate, PWA dismiss, builder breakdown, model display names`.

This is a test-environment bug, not a product bug — gating the UI on a live
gateway is correct behaviour. But the consequence matters: North Star rule 4
says *"UI work isn't done until it's seen working in a browser. No exceptions."*
That rule currently has no enforcement. Any UI regression merged today ships
unnoticed. Fix the smoke suite (stub `/proxy/health` in a Playwright fixture),
not the gate.

**B2 — `main` has been red for over a day and the signal is buried.**
19 consecutive failing `Tests` runs. Lint and hygiene were the cause until
`d55a084` fixed them; browser-smoke and the cold-start test are the cause now.
The cost is visible in B1: the health-gate regression landed into already-red
CI, so nobody could see a new failure appear.

**B3 — the PR automation shipped in #301 is broken in three places.**
`pr-auto-label` uses labeler v4 config against `actions/labeler@v5` and has
never once worked; `pr-test-hints` declares `pull-requests: read` and 403s on
every run; `pr-risk-guardrails` hard-fails any PR whose body lacks
`Manual approval: YES`, which pins all 13 Dependabot PRs permanently red on a
gate no bot can satisfy. PR #327 is open against this.

**B4 — 13 Dependabot PRs are stuck**, including `anthropic` 0.92 → 0.120 and
`next` 16.2.11 → 16.2.12. Nothing owns dependency hygiene in the roadmap.

**B5 — Builder session residue is being committed.** `.gitignore` covers
`.opencode/` but not `.omo/` or `.ocx/`; 8 `.omo/run-continuation/ses_*.json`
files are tracked on `main`. PR #324 is pure residue and should be closed.

---

## 5. What is missing from the plan that should be there

The parts nobody wrote down, ordered by how much they'd hurt.

**M1 — There is no Phase 2.** The active mission cites it; the roadmap does not
define it. Until a Phase 2 section exists with outcomes and exit criteria, every
future session will re-derive priority from a session checkpoint, which is
precisely the failure mode ADR 0020 was written to end. **This is the single
highest-leverage missing artifact.**

**M2 — Nothing measures the only success metric the project has.** North Star
says the measure is "mornings Jacob *wants* to open Kitty — nothing else." No
roadmap outcome, no checkpoint, and no test tracks whether Kitty is opened,
whether a brief was read, or whether a suggested next step was ever done. The
repository can prove 3,418 tests pass and cannot prove the product was used
once. Everything in §3 Tier B is at risk of being permanently unfalsifiable
without this.

**M3 — The move-in bar was never re-verified as a whole.** It was declared
reached by inferring it from packet merges on 2026-07-05, and the five criteria
have never been exercised together in one run. With the browser gate dead
(B1), there is also nothing that would catch it silently breaking. A single
scripted end-to-end pass over all five would convert the project's most
important claim from inference to evidence.

**M4 — No feature has ever been labelled Working / Partial / Planned.** The
hard rule was written on 2026-07-28 and never applied. §3 of this document is
the first attempt. It belongs in a maintained file, not an audit snapshot.

**M5 — No data-durability checkpoint.** `scripts/kitty_backup.py` exists.
Nothing in the roadmap owns "Jacob's benefits deadlines, job-search state, and
journal survive a dead Mac." For a local-first single-user product holding
exactly the paperwork that caused a $600-class miss, an untested backup is a
liability, not a mitigation. No restore has ever been proven.

**M6 — Nothing owns "the brief arrives when the Mac is closed."** Move-in
criterion 1 says the brief lands on the iPhone unprompted.
`scripts/kitty_desktop_launchd.py` schedules the local runtime — and launchd
does not run on a sleeping or powered-off laptop. ADR 0002 (local-first,
single-user) and the unprompted-phone-delivery promise are in unresolved
tension. Either the promise needs a hosted delivery path or it needs to be
restated honestly as "when the Mac is awake."

**M7 — No spend ceiling with a checkpoint.** `gateway/token_spend_report.py`
and `scripts/spend_report.py` exist. Meanwhile the RunPod work in PR #306 rents
a GPU on every push to its branch and has failed 100% of the time (~$0.30–0.40
of nothing so far). North Star §3 makes cost a first-class design constraint;
the roadmap has no outcome for "monthly spend is visible and capped."

**M8 — No branch or PR retention policy.** 72 remote branches, including
near-duplicate pairs (`codex/review-and-plan` / `codex/eeview-and-plan`,
`feat/` vs `feature/runpod-image-studio-smoke`). Cheap to fix, gets worse
monthly.

**M9 — The packet registry is stale enough to mislead.** Last updated
2026-07-14. It is the file most likely to be read as "what's built," and it is
17 days behind. This is the same class of confusion as mistaking a spec for a
shipped feature — a mistake already made once in this project's history.

---

## 5a. Why shipped work never reached the product

Added after Jacob asked the obvious follow-up: weeks of merged work, and nothing
about Kitty feels different. Two findings answer it.

### The launchd-served UI was frozen at the last hand-run build

The UI had two start paths that behaved differently:

| path | command | freshness |
|---|---|---|
| `scripts/desktop/start_ui.sh` (launchd service — the daily-driver path) | `npm run start` | serves the prebuilt `.next/`, **never rebuilt** |
| `./kitty verify-home` | `next dev` | compiles from source, always current |
| `make ui-tailnet` (phone over Tailscale) | `next dev` | always current |

`start_ui.sh` checked only that `.next/` *existed*. `.next/` is gitignored, so it
is a purely local artifact, and the only thing that produced it was `make
ui-build` — run by hand. `ui-build` appears nowhere in `scripts/`, nowhere in
`.github/`, and in no Git hook. `./kitty up` does not touch the UI. Neither
`./kitty doctor` nor `./kitty status` checked build freshness.

So under the installed desktop service, every `git pull` changed source that was
never compiled, and nothing said so. In the three weeks to 2026-07-31 that
covers **99 distinct UI source files, 72 of them components**.

CI cannot catch this by construction: `browser-smoke` runs `next build` fresh on
every run, so the build always matches source *there*. The staleness existed
only on the machine actually being used.

Yesterday's handoff recorded the symptom — *"The production UI on :4000 can lag
source; current code was verified with a temporary dev server on :4001"* — as a
gotcha to work around rather than as the reason the product never changes.

**Fixed** in `scripts/desktop/start_ui.sh`: the launcher now rebuilds whenever a
build input (`src`, `public`, `package.json`, `package-lock.json`,
`tsconfig.json`, `next.config.*`) is newer than `.next/BUILD_ID`, and a failed
build stops the service instead of falling back to serving stale code. Jacob
chose auto-rebuild over fail-loud on 2026-07-31: launch time is not something he
is optimizing for.

### Four commits in five went to the factory, not the product

205 non-merge commits on `main` since 2026-07-10, classified by what they touch:

| category | count | share |
|---|---|---|
| Machine and governance — Builder, KTF proofs, packets, handoffs, session state, CI, docs about docs | ~124 | ~60% |
| Product-facing — Home, image, insight loop, UI wiring | ~42 | ~20% |
| Mixed or unclassified — including four commits titled `tmp`, `tmp2`, `tmp3`, `tmp4` | ~39 | ~19% |

`docs/NORTH_STAR.md` §1 already names this failure mode: *"A session that
improves KittyBuilder but doesn't move Jacob's actual life forward is overhead.
Sometimes necessary, never the point."* The ratio says overhead has been the
default rather than the exception.

### Correction, and the real cause (2026-07-31, later the same day)

The frozen-build finding above was real, was fixed, and was regression-tested
in PR #328 — but it was not the reason Kitty looked unchanged. Jacob checked
his actual Mac and found **no `com.kitty.ui` launch agent installed**, so
`start_ui.sh` — the file that was fixed — is never invoked there. `./kitty up`
starts `next dev` directly, which compiles from source and was never stale.

The real cause, captured in his `238636c` commit and
`docs/reference/LAUNCHER_CONTRACT.md`, and added to `docs/ROADMAP.md` as Gate
0.5: **two Next.js servers from two different Kitty worktrees held port 4000
at once**, one on IPv4 (`127.0.0.1`) and one on IPv6. `kitty` probed
`127.0.0.1:4000` and validated the canonical checkout's health; the browser
opened `http://localhost:4000`, which macOS resolved to `::1` and landed on
the other worktree. The health check and the screen were never looking at the
same process. Separately, `pid_owned_by_kitty()` scoped ownership to the
running script's own `$KITTY_ROOT`, so `./kitty down` from the canonical
checkout left the other worktree's listener running and called it unrelated.

This is a materially better explanation than the frozen-build theory: Jacob
was not looking at a stale build, he was looking at a different checkout
entirely, and no single command he had would tell him so.

**Verified against `origin/main` @ `fb4e300`, in an isolated environment
without access to Jacob's Mac** — two real `git worktree` checkouts of this
repository, a live listener bound in each, and the actual (unmodified)
`assert_port_available` / `pid_owned_by_kitty` / `cmd_down` logic invoked
directly, not paraphrased:

| case | expected | result |
|---|---|---|
| no listener on the port | `assert_port_available` succeeds | ✅ exit 0 |
| listener from the *same* checkout | refuse, name it a leftover from this checkout | ✅ `held by a leftover Kitty process from this checkout` |
| listener from a *sibling worktree* of the same repo | refuse, name the other worktree's path and the fix command | ✅ `held by another Kitty worktree` / `worktree: <path>` / `Stop it with: (cd "<path>" && ./kitty down)` |
| `cmd_down`'s port-clearing loop against the cross-worktree listener | it is killed | ✅ confirmed dead by `ps` and `lsof` after the loop ran |
| `cmd_down`'s port-clearing loop against a listener with **no Kitty or Git relationship at all** (a plain process in `/tmp`, unrelated to Kitty) | *(not itself a pass/fail — see the finding below)* | it was also killed |

The first three confirm the roadmap's own Gate 0.5 verification step —
*"`./kitty up` from two separate worktrees; the second must refuse to
start"* — already holds on current `main`. The cross-worktree recognition
and the sibling-worktree shutdown both work as specified.

**New finding, not yet in the roadmap: `cmd_down`'s kill loop has no
ownership check at all.** Reading `kitty:345–353`, the loop is:

```bash
# Kill anything on Kitty ports regardless of ownership. The launchd
# KeepAlive cycle makes "leave unrelated" useless — if a process respawns
# before kitty start claims the port, the operator loops forever.
for port in "$UI_PORT" "$GATEWAY_PORT" "$LITELLM_PORT"; do
  for pid in $(listener_pids "$port"); do
    kill -KILL "$pid"
  done
done
```

It does not call `pid_owned_by_kitty` at all — it kills every listener on
4000/8000/8001, full stop. That satisfies Gate 0.5's requirement 7
("shutdown must recognize all Kitty worktrees") by brute force, but it
overshoots requirement 6's spirit: if Jacob ever runs an unrelated dev server
on one of those three ports for something else entirely, `./kitty down` will
now kill it with no warning and no ownership distinction in the log line.
Confirmed directly: a plain `python3 -m http.server` in `/tmp`, verified by
`pid_owned_by_kitty` to return "not owned," was killed by the same loop
without comment.

The comment justifying this — the launchd `KeepAlive` respawn loop — no
longer applies to the verified state: no launch agent is installed. Whether
to re-add an ownership gate (log and skip unrelated listeners, matching what
`stop_owned_listener()` — currently dead code, defined but never called —
already implements) or keep the blast radius as-is is a decision for Jacob,
not something to change silently under a roadmap gate marked PENDING.

**Gate 0.5 status, corrected:** several of its ten required properties are
already implemented on `main` (cross-worktree detection, `127.0.0.1`-only
probe/open in the `kitty` CLI, per-listener kill-on-down, `startup_identity`
printing checkout/SHA/build/PID/port). What remains, read directly against the
spec in `docs/reference/LAUNCHER_CONTRACT.md`:

- **No shared bootstrap.** `start_ui.sh` and the `kitty` CLI are still two
  independent scripts, each with its own copy of the source-load and
  `next`-invocation logic. Requirement 2 ("one canonical UI bootstrap ... no
  path may start `next dev` directly while another uses `start_ui.sh`") is
  unmet — the fix in #328 and the `kitty` CLI's own freshness check both
  exist, but as two implementations of the same idea rather than one.
- **`check_ui_freshness` in the `kitty` CLI only warns, never rebuilds.**
  `check_ui_freshness || true` at `kitty:314` — a stale `next dev` process
  isn't actually a freshness problem (`next dev` recompiles live), but the
  function exists and is asymmetric with `start_ui.sh`'s enforcement, which
  requirement 4 says must be identical on every path.
- **No "mode" field.** `startup_identity` prints checkout, SHA, build, PID,
  and port, but not development vs. production, which requirement 8 lists
  explicitly.
- **The unconditional `cmd_down` kill loop**, above — not a missing
  requirement, but a real deviation from the spec's intent worth a decision.

This section corrects rather than replaces the frozen-build finding above:
that fix was real, tested, and shipped, and remains true for anyone who does
install the launch agent. It was not, however, the explanation for what Jacob
was actually seeing.

Combined, the two findings explain the whole gap: most of the work was not
product work, and the product work that did exist was not being compiled onto
the screen where it would be judged.

## 6. Recommended order

Grounded in the roadmap's own operating rule: *finish one trustworthy end-to-end
product loop before expanding feature scope.* No new features until this
section's items land.

**Superseded by events, recorded for the trail.** Sections 1–4 as originally
written recommended getting `main` green and resolving the Phase 1 / Phase 2
contradiction (M1). Both happened the same day this review was written:
`docs/ROADMAP.md` was rewritten wholesale into a "Gate 0 — Repository and
Release Recovery" structure (`0.1`–`0.n`, ratified 2026-07-31), Gates 0.1
(green main) and 0.2 (PR automation) are marked COMPLETE, and PR #326/#327's
content is folded in. There is no longer a Phase 1/Phase 2 file to reconcile —
there is a Gate 0 with its own outcomes and a live status field per outcome.
**Apply the same discipline to Gate 0 that this document applied to Phase 1:**
don't let an outcome's status field say COMPLETE on inference. Gate 0.5 is a
worked example directly above — three of its ten required properties were
verified against real code and real processes in this session; one real gap
(the unconditional `cmd_down` kill loop) was found and was not in the roadmap's
own text.

Remaining, in order:

1. **Decide the `cmd_down` blast radius.** Confirmed above: the current kill
   loop takes down any process on 4000/8000/8001, Kitty-owned or not. Decide
   whether to restore an ownership check (the code for it,
   `stop_owned_listener()`, already exists and is simply unused) or accept the
   wider blast radius now that the launchd `KeepAlive` justification for it no
   longer applies. This is a one-paragraph decision, not a build.

2. **Close the remaining Gate 0.5 gaps** against
   `docs/reference/LAUNCHER_CONTRACT.md`'s own checklist: unify `start_ui.sh`
   and the `kitty` CLI's UI startup into one shared bootstrap (requirement 2);
   make `check_ui_freshness` in the CLI path enforce rather than only warn
   (requirement 4); add a mode field to `startup_identity` (requirement 8).

3. **Re-verify the move-in bar end to end, once, and record it.** All five
   criteria in one run. Still unaddressed by anything above — it remains the
   project's most important unverified claim. (M3)

4. **Add the usage signal.** Even a crude one — last-opened, brief-read,
   next-step-completed. Without it, "does Kitty work" stays unanswerable and
   every future roadmap argues from vibes. (M2)

5. **Then** prove restore from backup (M5), settle the phone-delivery promise
   (M6, now sharper — a launch agent was confirmed *not installed*, so the
   promise is currently false rather than merely untested), and put a spend
   ceiling behind a checkpoint (M7).

Feature work — 022, 024, 025, 028, Image Studio — stays behind all of it. That
is the roadmap's existing rule, not a new opinion.

---

## Appendix — what this review could not verify

- Builder runtime state (DB absent from this checkout)
- Actual product usage (`data/` is gitignored and empty here)
- Whether local provider credentials, quotas, or MLX/LiteLLM routing are healthy
- The local Python suite (this container lacks gateway dependencies; 82
  collection errors, environmental only — CI is the authority for §3 Tier A)
- Anything specific to Jacob's Mac (launch agents, real port occupancy, actual
  IPv6 resolution behavior). Section 5a's Gate 0.5 verification used two real
  `git worktree` checkouts and real listeners in this session's own Linux
  environment to exercise the *logic* faithfully — the code paths, not a
  simulation of them — but it cannot stand in for confirming the fix on the
  machine where the bug was found. The roadmap's own verification commands
  (`./kitty status`, the dual-loopback `curl` check, `lsof`) remain the way to
  close Gate 0.5 for real.
