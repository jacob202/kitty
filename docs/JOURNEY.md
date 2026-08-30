# Kitty Building Journey

*A running log of problems, insights, learnings, and major events.
Not a timeline — a memory. Read this before starting new work so you
don't rediscover what was already learned.*

**Last updated:** 2026-07-28 (session: Builder reliability + ImagePlan + UI surfacing)

---

## Origins (Dec 2025 – Feb 2026)

Kitty started as a local-first personal AI companion. Gateway (FastAPI) +
kitty-chat (Next.js). The core insight was that a personal AI needs to
know YOU — your projects, your todos, your calendar, your patterns.

**Key early decisions:**
- LiteLLM proxy in front of all providers — one routing layer, many backends
- Provider fallback chain: local MLX → OpenAI → NVIDIA → AgentRouter → OpenRouter → Gemini
- Image generation through ComfyUI, with Draw Things as an alternative engine
- Builder (KittyBuilder) as the execution control plane for unattended work

**Early problems solved:**
- `SOUL.md` as a behavioral system prompt with `SOUL_SCRATCHPAD.md` for two-layer evolution
- Context builder: concurrent fetches, partial-failure tolerance
- Journal interviewer mode, self-review signals (drift tracking, reaction quality)
- Magic Kitty, expert packs, memory policy, SSE push

---

## Spring 2026: Trust Foundation Mission (KTF-001)

**The problem:** Planning surfaces disagreed, no packet was proven against the
unattended free-model standard, the nightly drain didn't implement the
approved delivery authority, CI was broken.

**What was done:**
- CI restored (PR #264)
- Packet acceptance-criteria honesty (KTF-002)
- Runtime truth repair (KTF-003, PR #273)
- Outcome 6 daylight proof (34/34 tests)

**Critical learning:** Never apply an immutable manifest without checking local
initiative state first. The KTF-002 pre-correction manifest could conflict with
an already-applied version. This is why Builder recovery must be liveness-certified —
you can't just look at a row and decide it's stale.

---

## July 2026: Builder Reliability + UI Alignment (this session)

### Problems discovered

1. **Cancellation wasn't truthful.** `LOOP_CANCELLED` was collapsed into exhausted
   packet handling. A cancelled packet looked identical to an exhausted one.

2. **Stale attempts could be recovered without liveness evidence.** An attempt with
   `outcome IS NULL` could be treated as stale even if the worker was still running.
   Recovery now requires run-interruption evidence (PID check, `run_interrupted` event)
   before closing an attempt and releasing its lease.

3. **The Builder UI claimed "read-only" but had mutation controls.** Resume, cleanup
   buttons could mutate Builder state from a surface labeled as read-only status.

4. **Command palette button existed but did nothing.** The `⌘K` button in TopBar
   called `onCommandPalette` which was never passed from the page component.

5. **Studio request/response contracts didn't match.** Frontend sent `seed` and
   `image_count` which the backend silently dropped. Backend declared `reference_ids`
   which nothing ever used.

6. **Image engines were registered but undispatchable.** `image_backends.py` registered
   Stability AI but `image_runner.py` only routes ComfyUI and Draw Things.

7. **Builder showed "nothing queued — ready when you are" when Builder was actually
   unavailable.** The glance card didn't distinguish unavailable from empty.

8. **Image status transport errors were swallowed.** When the `/image/status` endpoint
   failed, ImageGenPanel showed a broken UI instead of an error message.

### What we built

9. **ImagePlan boundary (adapted from GenEvolve).** The valuable GenEvolve pattern is
   the plan→renderer separation, not the agent or GPU stack. We created:
   - `ImagePlan` dataclass with validated reference resolution
   - `GuidanceBank` — 8 renderer-annotated Markdown guidance files
   - `/studio/plan` preview endpoint
   - `PlanPreviewCard` with approve-and-generate flow
   - Prompt refinement: character context + guidance tags → refined prompt

10. **Provider health transparency.** Every provider now has `kind` (local/api_credit/
    subscription) and `free_tier` annotations. Settings shows kind badges and free
    tier chips. Model selector shows provider labels.

11. **UX consolidation.** Settings became one scrollable page (was four tabs with
    dead sections). WorkView got an attention row linking todos + Builder in one
    glance. Studio got a proper "Create" header with engine health status.

12. **Builder Brain.** A collapsible Q&A section on the Builder page that answers
    "what's blocked?", "what failed?", "what's running?" from the read-only status
    projection. No LLM call, no state mutation.

13. **Navigation fixes.** Tutor, Journal, and Terminal views were unreachable —
    they existed in ViewRenderer but had no command palette entry or redirect.
    Now reachable via `⌘K`.

### Learnings

- **Liveness fence for tests:** Synthetic test attempts don't have run-interruption
  evidence, so the liveness certifier filters them out. Tests must use
  `patch.object(ba, "list_all_stale_attempts", ...)` to bypass.

- **GenEvolve adaptation pattern:** Pin source at a commit → identify the boundary →
  map to existing primitives → adapt the data shape → reject what violates local
  invariants. Never import the agent wholesale.

- **Backend → frontend gap:** We have ~120 backend routes but only ~10 are surfaced
  in the UI. The pattern: a component exists, a route exists, but they're not wired
  together. Fix: add navigation entry + ViewRenderer case + command palette entry.

- **Every tile must do something.** Read-only dead tiles erode trust. If a section
  isn't ready, say why honestly and link to the command palette.

---

## Known gaps (not yet surfaced in frontend)

These backend features have routes but no UI:

| Backend | Routes | Status |
|---|---|---|
| Calendar | `/calendar/today`, `/calendar/upcoming`, `/calendar/create` | Hidden |
| Deadlines | `/deadlines`, `/deadlines/sweep`, `/{id}/close` | Hidden |
| Life | `/life/today`, `/life/yesterday`, `/life/events`, `/life/meeting`, `/life/reflection`, `/life/proactive/generate` | Hidden |
| Weather | `/weather` | Hidden |
| Nudges | `/nudges`, `/nudge/{id}/dismiss` | Hidden |
| Usage | `/usage/summary` | Hidden |
| Research | `/research/deep` | Hidden |
| Perf | `/perf/recent`, `/perf/stats` | Hidden |
| Health | `/health/weekly` | Hidden |
| Patterns | `/patterns/weekly`, `/patterns/annual` | Hidden |
| State | `/state/now`, `/state/changes` | Hidden |
| Export | `/export`, `/sync/export`, `/sync/import` | Hidden |

## Architecture debt notes

- `image_backends.py` registers Stability AI but `image_runner.py` can't dispatch it
- `builder_status.py` is a single long read-model — could benefit from internal seams
- `builder_loop.py` owns recovery, governor, lease, artifact, worker, validation,
  review, and settlement in one function — needs internal seams
- `context_receipt.py` is a long mixed validator — could be separated into Git,
  checkpoint, mission, PR, authority-map validators
