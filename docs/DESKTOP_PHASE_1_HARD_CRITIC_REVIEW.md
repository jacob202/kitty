# Kitty Desktop Phase 1 — Hard-Critic Review (Four Layers)

**Date:** 2026-06-12
**Reviewed artifacts:**

- Kitty Desktop Phase 1 Design ("Hardened after adversarial review")
- Kitty Desktop Phase 1 Implementation Plan
- Desktop Phase 1 Plan Review (ruthless review record)
- Mobile Companion Phase 1.5

**Method:** All four documents were checked against the live repository. Verified true: `iter_chat_completions_stream()` calls LiteLLM directly with no fallback (`gateway/llm_client.py:813`); gateway health identity matches (`gateway/app.py:131`); `gateway/lib/load_env_safe.sh` and the start scripts exist; Next.js is 16.2.6; the proxy uses the exact env names the design assumes. New findings from the code are flagged inline.

> **Status update (2026-06-12):** The auth fail-open finding below is **already fixed** in this same PR (`gateway/auth.py` now fails closed with 503 when `GATEWAY_SECRET` is unset, unless `KITTY_ENV=test`). Sections referencing it are kept as written for the record; where they say "fix," read "validate the fix under launchd."

---

## Verdict

The architecture is sound — launchd + least-privilege Tauri survived verification and the ruthless review already killed the worst ideas. **But the delivery structure is wrong for a solo builder, and the plan ships only half the product loop.** The product is not "services start after login." The product is a loop: **capture instantly → Kitty resurfaces it at the right moment → you act.** The current plan builds the left half of that loop to aerospace standards and does not build the right half at all.

Tear down the *delivery order*, keep the architecture.

---

# Layer 1 — The Rebuild

## Critical findings (from the first review pass, all repo-verified)

1. **Write-only inbox (critical).** Nothing in the repository references `inbox.jsonl` — not one file. `memory_graph.py` has five adapters (memory, knowledge, journal, traces, todos); inbox is not one, and none of the desktop docs mention `memory_graph` despite CLAUDE.md's rule that all context reads go through it. Mobile 1.5's start gate requires "the inbox processor has a clear use" — a prerequisite no document plans to build. Failure mode: two weeks of captures that never resurface, the habit dies, the loop is dead. **Fix:** a read-only `InboxAdapter` in `memory_graph.py` (~50 lines, the documented StoreAdapter pattern) shipped in the same slice as capture.
2. **Stale proxy default (high).** `gateway/kitty-chat/src/app/proxy/[...path]/route.ts:3` defaults `KITTY_GATEWAY_URL` to `127.0.0.1:5001`; the gateway runs on `:8000`. If the LaunchAgent env block is ever missing, chat fails silently against a dead port. Fix the default (or fail loudly when unset) and add the env-unset case to the Gate 0 `/proxy` proof. Related drift: CLAUDE.md still says `:5001`; the plan says Python 3.12, CLAUDE.md says 3.11 — the plists hardcode interpreter paths, so verify before generating.
3. **Task 1 is a git-status snapshot, not a spec (medium).** "Restore `paths.py` to pre-desktop content" describes one machine's working tree on one day. Respec as `git checkout -- gateway/paths.py gateway/routes/register.py`, delete-if-exists for the three prototype files, and gate on the full suite passing (449 passed / 2 skipped), not an import check.
4. **Gate 0 skips the riskiest proof (medium).** The four proofs test launchd, standalone `/proxy` (against a *stub* gateway), Tauri capability isolation, and capture. The actual promise — streamed chat through launchd-started LiteLLM after login — is never proven until the very end. Add a fifth proof: one real streamed completion through the full LaunchAgent chain.
5. **Gate 0 isn't actually disposable.** The plan's Tasks 2–5 are labeled Gate 0 but commit production scaffolds, config changes, and pinned dependencies — contradicting the design doc's own "Gate 0 is discarded" rule. Run the proofs as throwaway spikes first, then build.
6. **Task 11 is release engineering for an audience of one (cut candidate).** Transactional install with verified backup/rollback defends against a failure whose recovery cost is "run the installer again." Keep the build-staleness manifest and idempotent install; cut the tested rollback machinery — idempotent re-run *is* the rollback. Deletes roughly a third of the plan's heaviest task.

## The re-cut plan: vertical slices, each ending in daily-use value

The dominant risk is not technical failure — it is **abandonment risk**: life interrupts at Task 8 of 15 and you are left with nothing usable. Re-cut the same work so every slice ends with something you use that same day:

**Slice 0 — Spike day (half a day, throwaway branch).**
The four Gate 0 proofs *plus the fifth*: one real streamed chat completion through a LaunchAgent-started LiteLLM after logout/login. Fix the proxy `:5001` default while in there, and validate that the auth fail-closed behavior (already fixed in `gateway/auth.py` in this PR — see security section) holds under launchd. No committed scaffolds.

**Slice 1 — "Kitty survives reboot" (1–2 evenings). No Tauri.**
Three LaunchAgents + wrapper scripts + a health CLI. Test by actually rebooting. The buried insight: **launchd is the product; Tauri is the polish.** Once the LaunchAgents exist, `localhost:4000` in a browser kills the Terminal-after-reboot pain — the entire stated motivation — on day two.

**Slice 2 — Capture + resurface, shipped together (2–3 evenings).**
Quick Capture writing `inbox.jsonl` **and** the `InboxAdapter` so captures appear in `unified_context()`, search, and the morning brief. Rule: **never ship a writer without its reader.** This is also where the desktop plan reconciles with TASKS.md's "Phase 2: agents" — the inbox processor is the first background agent, and resurfacing is its v0.

**Slice 3 — Tauri shell (2–3 evenings).**
Tray, `Cmd+Shift+K`, capture window, the least-privilege capability split from the design (keep all of it). Add what the plan forgot: **a global shortcut for capture itself**, not just the main window. Capture must be one keystroke, window in <300 ms, cursor already in the text field — or it loses to Apple Notes and the loop never forms.

**Slice 4 — Status + slim install (1–2 evenings).**
Keep the truthful health model and staleness manifest. Cut rollback machinery. Install is idempotent and loud on failure.

**Slice 5 — Acceptance.**
Failure injection, logout/login, reboot. Unchanged from the plan — this part is good.

## "Worth keeping" — customer-experience additions (all cheap)

- **First run ends in delight, not logs.** The installer's last act: open the capture window with placeholder text — *"Tell me something to remember."* First contact is a capture, not terminal scroll.
- **Status is invisible when healthy.** Surface health only on *transition to broken* (tray icon state change, notification). Don't design Jacob into a sysadmin role for his own companion.
- **Kitty's voice in the chrome.** Tray copy, capture confirmations, errors — run them through SOUL.md. "Got it. It's safe with me." costs nothing and is the difference between product and utility.
- **Define success as usage, not gates.** Phase 1 exit criterion: *one week in which something was captured every day and Kitty mentioned at least one capture back unprompted.*

---

# Layer 2 — Meta-analysis: what the planning process did

1. **The adversarial review optimized "can't fail," never "worth using."** All 14 findings are failure modes; zero are about value delivery. A critique inherits the blind spot of its prompt — a robustness review produces robustness and *silently certifies scope*. The inbox-with-no-reader hole survived a "ruthless" review because no question in the review could have caught it.
2. **Effort was allocated by technical risk; the binding constraint is motivational risk.** Transactional installers defend against a cheap failure; a 15-task payoff-at-the-end structure invites the expensive one. Solo-builder plans should be scored on *time-to-first-payoff* and *interruption tolerance* — neither metric appears in any of the four documents.
3. **The hardening loop only ratcheted up.** Design → review → hardened design added gates, manifests, transactions, receipts. Nothing in the process had the role of *subtraction*. Every revision cycle needs one pass whose only permitted output is deletions.
4. **The docs cite the codebase carefully but never cite the user.** No line like "Jacob hit startup friction N times this week." The problem statement is plausible but undocumented — which matters when scope pressure comes and you need to remember why you're building this.

# Layer 3 — Meta-meta: the human-AI planning loop itself

1. **Successive AI review converges on *defensible*, not *bold*.** The pipeline was: AI drafts → AI adversarial review → hardened doc → AI hard-critic. Each pass is the same kind of mind re-reading the same text; after about two passes it stops adding information and starts adding *armor*. The reviewer that adds new information after that point is **reality**: one spike, one reboot, one week of usage. Never let documents go two generations without contact with running code in between.
2. **The planning stack now outweighs the artifact.** Four polished documents describe a desktop app of which zero lines exist. The thinking is good, but the healthy order for the next phase is inverted: spike first, write the design doc after Gate 0 with real findings in it. Plans written before contact are hypotheses formatted as decisions.
3. **"Set me up for success" is being asked of the wrong layer.** A plan cannot guarantee an outcome; it can only minimize the distance to the first moment the product gives something back. Judge every revision by one number: *days until Kitty does something for Jacob it couldn't do before.* Current plan: ~3 weeks. Re-cut: 2 days (Slice 1), loop closed in under a week (Slice 2).
4. **What's right at the meta level:** stop rules, scope locks, evidence-gated completion, and inviting hard critique of already-hardened plans. That discipline is rare. The meta-skill to add: aim it at *value* with the same ruthlessness as *failure*.

---

# Layer 4 — Expert panel

## The launchd / SRE graybeard

- **`KeepAlive` + `ThrottleInterval` makes a misconfigured service flap forever, silently.** LiteLLM with a bad key will crash-restart every throttle interval for weeks. Add "restarted N times in the last hour" to the Status model — the single most diagnostic launchd signal.
- **launchd does not rotate stdout logs.** The plan promises 5 MB rotation, but `StandardOutPath` files grow unbounded; services must rotate their own logs (or a cleanup runs in the health check). As written, the promise and the mechanism don't connect.
- **The GUI login environment will cause half the bugs:** no shell init, minimal PATH, different locale. Absolute paths everywhere is correct; add one cheap defense — each wrapper logs its resolved (redacted) environment at startup, turning "works in Terminal, dies under launchd" into a 30-second diagnosis.

## The product designer

- The journey today: install (terminal) → status window (operator UI) → chat (the product). Invert the emphasis. Measure *time-to-first-capture* from install: under a minute, installer hands you directly into it.
- **Kill every decision in the capture flow.** Project and tags cost a decision each time; hide them behind a disclosure and let the future processor infer them.
- Give the spiraling / "What am I avoiding?" concepts a **desktop presence** (they're mobile-only in the plans). The Mac is where Jacob already is all day; a tray "What am I avoiding?" item is one menu entry and tests the concept a full phase before mobile exists.

## The security engineer

- The Tauri capability design is genuinely strong — keep it exactly.
- **`gateway/auth.py` failed open** (fixed in this PR — `fix(auth): fail closed when GATEWAY_SECRET unset outside KITTY_ENV=test`). Previously, if `GATEWAY_SECRET` was unset and `KITTY_ENV` ≠ `prod`, every request bypassed auth. The concrete launchd failure mode it enabled: `load_env_safe.sh` fails silently → gateway runs unauthenticated on `:8000` → any local process can read Kitty's memory. The middleware now returns 503 when the secret is missing outside `KITTY_ENV=test`. Remaining work: the LaunchAgent wrapper must still fail hard when the secret is missing, and Status should report "auth enforced: yes/no" as a first-class check.
- **Localhost is not a trust boundary.** Browsers will POST to `127.0.0.1:8000` from malicious websites (CSRF/DNS-rebinding against localhost). CORS in `app.py` allows credentials with a localhost origin list; add Host-header validation and confirm no state-changing route is reachable without the bearer token.
- Both fixes are one evening each and matter more than the installer's rollback path.

## The behavioral coach (ADHD-aware companion design)

- **Capture systems die at review, not capture.** The `processed:false` flag quietly assumes a review ritual that will never happen. Design for **zero-ritual resurfacing**: Kitty raises captures in conversation and the morning brief; there is no "go process your inbox."
- **The spiraling button's contract is response, not storage.** A distress signal written to a sleeping Mac and never acknowledged teaches — at the worst possible moment — that Kitty isn't there. Desktop-first version done right: when Kitty is next opened after a distress capture, she opens *with* it ("Last night was rough. Want to talk about it, or park it?"). That behavior is the prerequisite for the mobile button, and it's buildable in Slice 2.
- **The trust loop compounds.** Every time Kitty echoes a capture back in her own voice, the next capture gets more likely. That echo is the growth mechanic of the entire product, and no document plans it.

## The solo-dev economist

- Honest price: 2–4 weeks of evenings, and the biggest line item is **Rust/Tauri** (`capture.rs` with locking and fsync, clippy-clean, capability configs, two bundled frontends) — for a tray icon, a shortcut, and a text box.
- **Plan B worth pricing before committing:** launchd (Slice 1) + a Raycast script command or Hammerspoon hotkey appending to `inbox.jsonl` + the InboxAdapter. Roughly three evenings, zero new languages, ~80% of Phase 1's value: survives reboot, instant capture, resurfacing loop closed.
- Tauri then has to *earn* its slot with what only it provides — the status surface, the polished window, the long-term native shell — built with a week of real usage data behind the decision. If the loop changes your week, build the shell with conviction. If it doesn't, you saved two weeks of Rust on the wrong product.

## Mobile Phase 1.5 (carried from the first review)

- The design-only discipline is correct; keep the start gate.
- The inbox processor / resurfacing behavior is a **hard prerequisite** for the distress button, not a nice-to-have.
- The transport doc lists three options neutrally; for a single user the realistic default is option 2 (Tailscale-style user-controlled tunnel). Naming the default now simplifies the auth design (no pairing protocol) without committing.

---

# Synthesis — the Monday plan

1. **Spike day** (Slice 0, throwaway): five proofs including real streamed chat under launchd. Fix the proxy `:5001` default; validate the auth fail-closed fix (already in `gateway/auth.py`) under launchd.
2. **Slice 1 by midweek:** LaunchAgents live, reboot test passed, Terminal retired. The headline benefit is already real.
3. **Slice 2 by the weekend:** capture (Raycast/Hammerspoon stopgap is fine) + InboxAdapter + brief resurfacing. **The loop closes here. This is the moment the product becomes worth keeping.**
4. **Then decide on Tauri** with a week of real usage data, and build Slices 3–5 from the existing plan — slim Task 11, respec Task 1.

**One-sentence version of all four layers:** the plans bulletproofed the pipe and forgot the person drinking from it — re-cut the build so Kitty gives something back within the first week, and let reality, not another review pass, harden everything after that.
