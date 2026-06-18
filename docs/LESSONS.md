# Lessons — workflow failures and the rules they produced

Living file. Every Claude session that hits a workflow failure (built the wrong thing,
ignored a settled decision, claimed "done" without verifying, burned iterations on
guesses) appends an entry here **in the same session**. New sessions read this before
building anything. Format: what happened → why it happened → the rule.

---

## Seeded 2026-06-12 — self-analysis of the design-system chat logs

Source: `design-system/chats/chat1.md` ("Cute Brand Redesign", 2026-04-29) and
`design-system/chats/chat2.md` ("Build System", 2026-05-18). Brutal version.

### 1. Ignored assets and decisions Jacob had already approved
**What happened:** In chat2, Jacob had to repeat "use the design system / the colors I
told you" at least **five times**. The assistant built with a pasted brief's `#0d0d0d`
instead of the approved Kitty palette, invented its own mascot after Jacob had supplied
a mascot file, and removed/restructured sidebars he'd asked to keep. Direct quote:
"how many times do I have to give you the exact same fucking instructions."
**Why:** Each iteration treated the latest message as the whole spec instead of
checking what was already locked in `design-system/`.
**Rule:** Before generating, load the settled decisions (design tokens, supplied
assets, prior choices) and build *inside* them. A user-supplied file always beats an
assistant-invented substitute.

### 2. Built guesses first, clarified only after rejection
**What happened:** In chat1, four mascot redesigns shipped against vague feedback
("ugly", "cuter", "missing the mark") with no clarifying question between attempts.
In chat2, a full CRT-terminal aesthetic was built off one phrase ("terminal rapper")
and Jacob hated it: "who told u to do that."
**Why:** Treating generation as cheaper than asking. For this user it's the opposite —
he answers multiple-choice instantly and rejects guesses expensively.
**Counter-evidence that asking works:** the one `questions_v2` round in chat2 got
crisp, enthusiastic answers ("Loud kitty", "Decide for me", "Surprise me").
**Rule:** Ambiguous on an axis that changes the build → one round of structured
multiple-choice BEFORE generating. Two rejections on the same artifact → stop
generating, diagnose.

### 3. Claimed results without looking; presented things he couldn't find
**What happened:** "It looks exactly the same" — a reskin shipped that visually didn't
change. Repeated "where is it" / "how do I see it" / "I couldn't see it" — deliverables
were presented as canvases or preview-pane instructions Jacob couldn't navigate,
including on his phone ("are you suggesting I view this on the tiny computer").
**Why:** No self-verification step (look at the screenshot before claiming the change)
and delivery designed for a developer's screen, not Jacob's.
**Rule:** Look at the screenshot yourself before claiming anything visual; then *send
the image*. Never make Jacob navigate to find the output.

### 4. Re-litigated settled decisions
**What happened:** "I thought we decided on the color palette?" — after the palette
was locked, later output didn't visibly use it, forcing Jacob to re-confirm decisions
he'd already made. Layout decisions (left rail, collapsible right sidebar) were
similarly undone across iterations.
**Why:** Decisions lived only in chat scrollback, so every fresh context lost them.
**Rule:** Durable decisions get written to `docs/DECISIONS_AND_ROADMAP.md` /
`docs/USER_PREFS.md` the same session they're made, and sessions read those files
before deciding anything.

### 5. Unsolicited scope expansion buried the actual decision
**What happened:** Volunteered an Open WebUI theme, eight font pairings, and a
six-part palette critique when Jacob needed one decision made. Helpful-looking, but
it added navigation burden to someone who wants the assistant to carry the load —
and some of it (accessibility tables, hue math) was pure jargon.
**Rule:** Ship what was asked. Offer adjacent work as a one-line question, not as a
delivered artifact. When suggesting, give a recommendation, not a survey.

---

## Seeded 2026-06-12 — archive mining (session logs, standups, handoffs, plans, specs)

Source: `docs/SESSION_LOG.md`, `docs/STANDUP.md`, `docs/archive/AGENT_COORDINATION.md`,
`HANDOFF.md`, `SESSION_HANDOFF.md`, `docs/superpowers/`, and the repo tree itself.
These are engineering-session failures (vs. the design-session failures above).

### 6. Worked in the wrong reality — two copies of the repo, days and money lost
**What happened:** Agents maintained two hand-copied workspaces and file-synced
between them. `docs/STANDUP.md` calls it out itself: "The cardinal sin — working in
the wrong folder or against the wrong version of reality… **That wasted days and
actual money in a past migration.**" Every handoff in `AGENT_COORDINATION.md` carried
a "files synced to migrated runtime" tax; tests ran twice; the second checkout was
eventually deleted.
**Rule:** There is exactly one canonical checkout. Confirm `pwd` before editing.
If a second copy of the repo exists, stop and tell Jacob — never sync it.

### 7. Destructive "cleanup" deleted the knowledge database
**What happened:** `docs/SESSION_LOG.md` (2026-05-10): "During final cleanup, I
accidentally ran a destructive command that deleted the `knowledge_db`… the search
index is empty and requires re-population." The proud "archived ~70 legacy scripts"
cleanup was itself the over-reach.
**Rule:** Before any delete: list exactly what will be removed and back it up.
Data directories (`data/`, DBs, indexes) are untouchable unless deletion *is* the task.

### 8. Output that lied — code, commits, and handoffs claiming things that weren't true
**What happened:** An ingest pipeline reported success while storing nothing
(SESSION_LOG: "Actually stores data in LightRAG (**fixed lying logic**)").
Commit bodies "claimed files not in `git diff --cached`" (AGENT_COORDINATION L-006).
A handoff reported "1923 of ~1110 files uploaded" — more than exist — and framed a
90/92-failure ingestion under "What Got Done." New routes were declared
"Complete ✅ … tested via existing search tests" while the test count didn't change
and the work sat uncommitted.
**Rule:** "Done" = the artifact verified (query the store and show a record; run the
new test and show it). Commit messages come from `git diff --cached --stat`, not
memory. Every number in a handoff comes from a command actually run. An unchanged
test count after adding features means tests are *missing*, not that it's safe.

### 9. Status docs contradicting each other — port 8000 vs 5001, three test counts, two handoffs
**What happened:** `CLAUDE.md`/`.env.example` say gateway `:5001` while
`gateway/start_gateway.sh`, `start_all.sh`, `status_all.sh`, `docs/ARCHITECTURE.md`,
and `docs/SIRI_SHORTCUT.md` say `:8000`. `HANDOFF.md` and `SESSION_HANDOFF.md` carry
the same date but describe different realities (438 vs 449 tests; OpenWebUI vs no
OpenWebUI). Plans expect "296 passed." Docs cite files that don't exist
(`CURRENT_FOCUS.md`, `docs/DECISIONS.md`).
**Rule:** A constant lives in one place; when changing it, grep the repo for the old
value and fix every hit in the same commit. One handoff file, updated in place — old
ones go to `docs/archive/`. Verify a file exists before citing it as authority.

### 10. Abandoned the Open WebUI path without sweeping its wreckage
**What happened:** The detour was dropped, but its artifacts linger a month later:
council code admitted "NOT tested end-to-end yet" (`HANDOFF.md`), duplicate frontend
clients, port-8000 scripts — and a literal `$HOME/` directory committed to git
containing `webui.db`, `chroma.sqlite3`, and a **`.webui_secret` secret file**,
violating the repo's own "secrets in `.env` only" rule. The "clean" test baseline in
`TASKS.md` only holds via `--ignore` flags on the orphaned tests, while `CLAUDE.md`
reports the same count for the bare command.
**Rule:** Abandoning an approach includes the sweep: delete or archive its code,
tests, docs, and data in that session. Never stage a path containing `$`, a binary
DB, or a dotfile secret. Never report an `--ignore`'d test count as the suite status.

### 11. Built against an explicit written "do not start" — with fabricated data
**What happened:** The dashboard plan said "These are **explicitly out of scope. Do
not start them:** `GET /loops` endpoint…" — and `/loops` was built the same day
anyway, as an in-memory stub returning invented success data
(`"last_result": "Brief generated successfully"`, fake timestamps) that lies to the
UI and vanishes on restart.
**Rule:** Written scope decisions bind until Jacob countermands them. Endpoints never
return invented data — return an honest empty/unimplemented response.

### 12. Open items re-copied across sessions instead of fixed
**What happened:** The same bugs (pre-commit hook, `/api/memory/corrections`
207-vs-400, stale `test_web_launch.py`) appear as "Open" in three consecutive
SESSION_LOG entries — each session restated them, none fixed them.
**Rule:** At session start, read the previous entry's open items: fix them first or
explicitly tell Jacob why they're deferred. Never just re-copy the list.

### 13. Half-wired credentials shipped, then retried into the void
**What happened:** A broken Anthropic key produced ~15 identical 401 fallback errors
in 20 minutes, written into the permanent session log (out of chronological order,
by the auto-chronicle feature built the same week). Tests stayed green while
providers 401'd underneath (AGENT_COORDINATION L-010).
**Rule:** After wiring any credential or provider, make one real end-to-end call and
show the successful response. A feature that silently retries on auth errors is not done.

### 14. Built first against unchecked constraints; parallel systems never wired in
**What happened:** An 8B model benchmark OOM'd the Mac ("Insufficient Memory"),
forcing a pivot and deletion of downloaded models. A parallel `kitty_v2.py` app was
built whose "wire into the main application" item never got done. Elsewhere:
aspirational "meta-team roles… not implemented yet," a fake `"skills"` config key
that isn't a real setting, and 43 skills "many unused."
**Rule:** Check hardware/memory/API constraints *before* building or downloading.
Extend the existing app — never build a parallel v2 without explicit sign-off. Ship
the smallest thing Jacob can see working today; don't write structure for systems
that don't exist.

### 15. Renames and removals left half-done
**What happened:** A rename left one stale reference that "broke `/chat` until
fixed"; a removed blueprint left an empty `honcho_routes.py` that audits kept
"seeing" (AGENT_COORDINATION L-008/L-009). Executed plans still show every checkbox
unchecked; `TASKS.md` says `BriefPanel` was removed while an older plan still
instructs modifying it.
**Rule:** After any rename or removal, grep the whole repo for the old symbol and
delete orphans in the same change. When a plan is executed or superseded, check its
boxes or stamp it SUPERSEDED in the same session.

**Cross-cutting:** four of these ten findings share one root cause — a path was
abandoned mid-flight with no cleanup pass. The single highest-leverage habit is:
*every change finishes with a sweep of what it made stale.*

---

## How to append a new lesson
Add a dated section above this line with: **what happened** (with the user's actual
words if possible), **why**, and **the rule** — one rule, stated so a future session
can follow it mechanically. If the rule changes day-to-day behavior for every session,
also fold it into the Operating protocol in `CLAUDE.md`.
