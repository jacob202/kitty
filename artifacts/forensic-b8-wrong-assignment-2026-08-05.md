# Forensics: why Builder executed the wrong assignment
**Date:** 2026-08-05 (analysis session)
**Subject:** Operator approved *"Repair first-run onboarding and Work navigation"*; the worker instead executed `B8-clean-checkout-mission` (a documentation-only trivia packet) and committed unrelated documentation.
**Method:** read-only runtime, DB, bundle, attempt, launch, worktree, and prompt inspection. No fixes implemented. Inferences are explicitly labelled.

---

## 1. Timeline of events

All times UTC; local is UTC−06:00. DB timestamps are SQLite `CURRENT_TIMESTAMP` (UTC); file mtimes are local.

| When | Event | Evidence |
|---|---|---|
| 2026-08-02 01:43 | Initiative `trustworthy-kittybuilder-b2-b10-v1` applied; tasks B2–B10 created. B8 task `kb_msb4yx3n_f6e8` = "Prove a clean-checkout mission". | `events` id 1493; `initiatives` row |
| 2026-08-02 (interactive op) | Campaign operator starts tmux `builder-b2-b10` running `./kitty builder initiative run trustworthy-kittybuilder-b2-b10-v1 --free --model openrouter/deepseek/deepseek-v4-flash-0731 --publish --gate auto`. B2–B7 merge; B8, B9, B10 remain. | `~/kb/NOW.md` 2026-08-02; `~/.zsh_history` 3976–3984 |
| 2026-08-02 21:50–22:12 | **B8 attempt 106**: worker runs run `run_mscc36sf_7190`; commits `7ea5e077`, `9bbc945a` (B8 trivia docs) on branch `feat/b8-clean-checkout-trivia`. Identity gate fails: wrong branch + missing `[B8-clean-checkout-mission]` markers. Escalation `needs_decision`. | `events` 1696–1708 |
| 2026-08-03 08:01 | B8 attempt 107 crashed (worktree on wrong branch). | `events` 1710–1716 |
| 2026-08-05 00:54 / 04:01 / 04:15 / 04:16 | B8 attempts 108–111; infra crashes (`git worktree` timeout, `ActiveRunConflictError`). Attempt 111 **starts a worker and is never closed** → leaks an open (stale) attempt. Operator grants: 04:04 ×2, 04:28 ×2 (raises budget 3→7). | `events` 1717–1749 |
| 2026-08-05 08:47:45 L (14:47:45) | Campaign run #1: B8 attempt 112 crashes at preflight (`worktree … on 'main'`). | `operator-logs/b2-b10-campaign-20260805-084744.log`; `events` 1750–1756 |
| 2026-08-05 **08:48:47 L (14:48:47)** | tmux `builder-b2-b10` (created 08:48:46 L) starts campaign run #2: `next_packet` selects **B8 as a recovery candidate** (blocked + leaked stale attempt 111 + deps done + not budget-exhausted) → `run_packet` → **attempt 113**, run `run_msg7ctiy_a86f`. | tmux session create time; log `…-084847.log`; `events` 1757–1767 |
| 2026-08-05 15:13:28 | Attempt 113 fails. Repair loop archives worktree, **auto-releases task** (`repair_loop_retry attempt 9`, `builder_loop.py:956-964`) and opens **attempt 114** in the same invocation, run `run_msg88iiw_9e3a`. | `events` 1768–1774 |
| 2026-08-05 09:16:08 L | Worker commits **`00edce20` "docs: B8 clean-checkout mission session note"** on `kittybuilder/kb_msb4yx3n_f6e8` — the unrelated documentation observed. | `git show 00edce20`; run log `combined.log` |
| 2026-08-05 15:16:55 | Identity gate fails attempt 114: commit lacks `[B8-clean-checkout-mission]` marker. Escalation `needs_decision`. `run_initiative` logs `packet_exhausted` + `continued_after_packet_failure` **then continues** → `idle`, exit 0. tmux pane shows `idle: … exhausted: B8`. | `events` 1775–1782; tmux pane; `builder_run.py:574-591` |
| Ongoing | B8 task remains `blocked`; B9/B10 `queued` but depend on B8 → unreachable. No task/packet anywhere matches the operator's approved work. | `tasks` table; `initiative_packets.depends_on_json` |

---

## 2. Root cause analysis

### 2A. The "wrong" assignment that reached the worker was B8 — by selection, not by worker error
The launched worker genuinely and faithfully executed its own bundle: B8 is a *"trivia packet (documentation-only, no code mutation)"* proof packet, and the worker implemented exactly that (a session-note doc within `allowed_paths`). The worker is **not** the trust failure. The trust failure is upstream: **Builder selected the wrong packet to run**, and kept re-selecting it.

### 2B. Why B8 was the only selectable packet in its initiative
`next_packet()` (`builder_initiative.py:1273`) returns `[eligible…] + [recovery…]`, lowest `seq` first:

- **Eligible** requires own task `queued` + deps done + not exhausted (`builder_initiative.py:1151-1182`).
- **Recovery** (`builder_initiative.py:1236-1270`) requires task `blocked` + deps done + a stale open attempt (`outcome IS NULL`, liveness-certified) + not exhausted.
- B8's deps (B2–B7) are all `done`, so whenever B8's task is `queued` **or** `blocked` with a leaked/ stale attempt, B8 is selectable. B9/B10 depend on B8, so they are always unreachable while B8 is not done (`_compute_unreachable`, `builder_initiative.py:1090-1099`).

### 2C. Why B8 never exhausted → never failed closed
`_attempts_exhausted` (`builder_initiative.py:1048-1063`) counts only `_BUDGET_CONSUMING_OUTCOMES = {failed, aborted}` against `policy.max_attempts`. B8's nine attempts: 4× `failed`, 5× `crashed`. Crashes are budget-neutral by design; the four failures never reached the inflated max (raised 3→7 by four operator `grant-attempt`s during the session, `builder_attempt.py:599-696`). So `_exhausted_packet_ids` returns `∅` — B8 is **never** budget-exhausted and remains perpetually selectable.

### 2D. Why the worker loop didn't stop after escalation
Attempt 114 failed with an **identity escalation** (`identity_verification_failed`, `builder_identity.py:245-258` requires every commit subject to carry `[B8-clean-checkout-mission]`). `_classify_exhaustion` correctly returns `stop_class=needs_decision` (`builder_run.py:68-92`), but `run_initiative` (buildler_run.py:574-591) after `packet_exhausted`:
1. logs `continued_after_packet_failure` with `stop_class=needs_decision`, then
2. **`continue`s** to the next packet, and
3. when none remains returns `outcome="idle"` → CLI exits **0** (`builder_cli.py:1521`).

A `needs_decision` escalation therefore never parks the work; the campaign wrapper sees a clean exit and re-runs, re-selecting B8. Meanwhile the repair loop itself auto-releases the blocked task between retries (`builder_loop.py:956-964`, `repar_loop_retry`) and on stale-attempt recovery (`builder_loop.py:749-781`), so the loop re-arms itself without a human.

### 2E. The operator's approved work never existed in Builder
Searches of `builder_queue.db` (tasks, initiatives, events, runs, manifests) and the repo find **no** task/packet/initiative for "Repair first-run onboarding and Work navigation". The only trace is a historical shell command `./kitty builder initiative attempts kproof-001-onboarding-work` in `~/.zsh_history` — that initiative is not in the DB (applied or not). The approved work lived in the interactive lane as intent only; nothing materialized it as a Builder queue item. With no queued onboarding repair and B8 perpetually selectable in the initiative the campaign keeps draining, **B8 is what every `initiative run` invocation picks** — including the one the operator intended to be doing the onboarding repair.

### Root-cause statement
> The wrong assignment reached the worker because Builder's packet selection (`run_initiative` → `next_packet` → `eligible_packets`/`_recovery_packets`) is decoupled from the operator's approved work and from the packet's own failure history: in `trustworthy-kittybuilder-b2-b10-v1` the *only* selectable packet is the stale doc-only trivia packet B8, whose budget never exhausts (crashes are budget-neutral, failures were operator-granted past), whose leaked open attempt re-arms it as a "recovery" candidate, and whose terminal `needs_decision` escalation does not stop the outer loop (`continue` + exit 0). The operator's real approved work was never reified as a Builder task, so the loop had nothing correct to pick and re-picked the wrong packet instead of failing closed.

---

## 3. Exact source files involved

| File | Role in the failure |
|---|---|
| `gateway/builder_run.py:274-282` | `run_initiative` → `next_packet` selection entry (autonomous + campaign path). |
| `gateway/builder_initiative.py:1151-1182` | `eligible_packets` (queued + deps done + not exhausted). |
| `gateway/builder_initiative.py:1236-1270` | `_recovery_packets` — resurrects blocked B8 on stale open attempt. |
| `gateway/builder_initiative.py:1048-1063` | `_attempts_exhausted` — only `{failed, aborted}` consume budget. |
| `gateway/builder_attempt.py:599-696` | `grant_attempt` — operator budget inflation (3→7). |
| `gateway/builder_attempt.py:899/1039 + _BUDGET_CONSUMING_OUTCOMES` | 9 attempts; 5 crashed / 4 failed. |
| `gateway/builder_loop.py:693-842` | `run_packet` — blocked+stale recovery release (`:749-781`). |
| `gateway/builder_loop.py:949-996` | Repair loop — auto `operator_release_task("repair_loop_retry …")` between attempts. |
| `gateway/builder_runner.py:178-264` | `ensure_worktree` — worktree/branch id; source of the wrong-branch infra crashes. |
| `gateway/builder_runner.py:859+` | `run_worker` — launches `opencode-free`, generates bundle/brief/prompt. |
| `gateway/builder_identity.py:145-258` | `verify_worker_identity` — commit marker `[B8-clean-checkout-mission]` gate that the worker's doc commits fail. |
| `gateway/builder_run.py:68-92, 545-591` | `_classify_exhaustion` → `needs_decision` + **`continue`** (the missing fail-closed). |
| `gateway/builder_cli.py:1420-1472, 1521` | `run-packet`/`run-init` CLI; exit 0 on `idle`. |
| `scripts/nightly_packet_drain.sh` | Hourly drain — targets the first `[active]` initiative; on Aug 5 it drained `kx-06` (idle), so it was **not** the B8 driver (evidence: all `drain-…-log`s say `initiative=kx-06`). |
| `scripts/kittybuilder_opencode_worker.sh` | The invoked worker command (prompt assembly + bundle/context verification). |

---

## 4. Sequence diagram

```
Operator (interactive lane)
   │  approves "Repair first-run onboarding and Work navigation"  (NEVER reified as a Builder task/packet)
   │
   ▼
tmux "builder-b2-b10"  ──  ./kitty builder initiative run trustworthy-kittybuilder-b2-b10-v1 --free --gate auto

   run_initiative(builder_run.py)
     └─ next_packet()                       [only selectable: B8]
           ├─ eligible_packets()            B8 task QUEUED + deps done + not exhausted(4 failed < max 7)
           └─ _recovery_packets()           B8 BLOCKED + leaked stale attempt 111
                    │
                    ▼
     run_packet(B8)        [builder_loop.py]
       ├─ blocked + stale → reconcile + operator_release("stale_attempt_reconciliation")
       ├─ while True:
       │    ├─ claim_and_start_attempt → attempt 113 (run run_msg7ctiy_a86f)
       │    │     └─ run_worker → kittybuilder_opencode_worker.sh → opencode-free
       │    │           bundle 114 (B8 trivia, doc-only) + brief + context manifest
       │    │           Worker writes docs/session-notes/2026-08-05-b8-clean-checkout-mission.md
       │    │           commits 00edce20 "docs: B8 clean-checkout mission session note"
       │    │           └─ returns; attempt fails (worktree archived)
       │    ├─ repair_loop_retry: operator_release_task → attempt 114 (run run_msg88iiw_9e3a)
       │    │     └─ worker runs same trivia bundle; commits docs again
       │    └─ verify_worker_identity → MISSING [B8-clean-checkout-mission] marker → escalation
       │          attempt_closed(failed)
       └─ outcome=exhausted (budget NOT spent because failures < max)
              │
              ▼
   run_initiative: packet_exhausted (stop_class=needs_decision)
                   + continued_after_packet_failure
                   + continue  ──▶ no next packet ──▶ idle ──▶ exit 0   ⚠ NO FAIL-CLOSED
             (next campaign invocation repeats from the top → B8 again)
```

---

## 5. Minimal patch recommendation (NOT implemented — analysis only)

Smallest change that fails closed on the observed scenario, with no redesign and no behavior change to healthy packets:

**In `gateway/builder_run.py`, exhaustion handling (around lines 545-591):** when `loop_result["outcome"] != "succeeded"` and the classification is `STOP_NEEDS_DECISION`, **pause the initiative** (`bi.pause_initiative(…, reason=…)`) and return `outcome="paused"` with `stop_class=needs_decision`, instead of logging `continued_after_packet_failure` + `continue`.

Rationale:
- A `needs_decision` (scope/identity escalation, ambiguous repeated failure) is exactly the case the CP-03 classifier says "ask Jacob". Today that signal is recorded but then ignored by the loop control flow.
- Pausing uses existing machinery (`bi.pause_initiative` + the pause check at `builder_run.py:264`), so the next `initiative run` invocation stops at the gate instead of re-selecting B8.
- It does not touch healthy packets (which exhaust as `routine` and keep retrying/continuing as today).

Optional second line (same spirit): make `_attempts_exhausted` treat a packet whose last `failed` attempt escalated as `needs_decision` as not-selectable until an explicit operator override — but that's a larger surface change; the pause-on-needs_decision is the smallest safe fix.

---

## 6. Regression test that would have caught this bug

Target file: `tests/test_builder_run.py` (or `tests/test_builder_loop.py`).

```python
def test_run_initiative_fails_closed_on_needs_decision_exhaustion(cli_db, monkeypatch):
    """After a packet exhausts with stop_class=needs_decision, the initiative
    must pause (not idle/continue) so the wrong packet is never re-selected."""
    from gateway import builder_loop as bl, builder_run, builder_initiative as bi
    init = "test-b2-b10"
    packet = "B8-clean-checkout-mission"

    def fake_run_packet(*args, **kwargs):
        return {
            "outcome": bl.LOOP_EXHAUSTED,
            "initiative_id": init,
            "packet_id": packet,
            "task_id": "t1",
            "reason": "worker identity verification failed: 1 commit(s) lack "
                      "required marker [B8-clean-checkout-mission]",
            "attempts": [{"attempt_no": 1, "outcome": "failed",
                          "escalation": {"findings": [{"category": "identity_violation"}]}}],
        }
    monkeypatch.setattr(builder_run.bl, "run_packet", fake_run_packet)

    summary = builder_run.run_initiative(init, worker_command=["true"])
    assert summary["outcome"] == "paused"          # NOT "idle"
    assert summary["stop_class"] == "needs_decision"
    assert bi.get_initiative_state(init) == bi.INITIATIVE_PAUSED

    # and a second invocation must not relaunch the worker
    calls = []
    def tracking_run_packet(*a, **k):
        calls.append(1); return fake_run_packet(*a, **k)
    monkeypatch.setattr(builder_run.bl, "run_packet", tracking_run_packet)
    builder_run.run_initiative(init, worker_command=["true"])
    assert calls == []                              # worker never relaunched
```

`_classify_exhaustion` (real code) reads the `escalation` key from `loop_result` and returns `needs_decision` for it, so with the fix this test goes red today (it would return `idle`, exit-0 shape) and green after the one-line fail-closed change.

---

## 7. One additional invariant Builder should enforce before any worker begins execution

> **No worker may be launched for a packet whose latest `initiative_decision` is `packet_exhausted` with `stop_class = needs_decision` unless an operator action (release/grant) durably recorded *after* that decision exists.**

Placement: the front of `run_packet` (`builder_loop.py:726-787`) / `next_packet` (`builder_initiative.py:1273-1294`) — refuse the packet regardless of whether it is "eligible" by task state. This is the missing boundary between *operator approval* and *packet selection*: it forces a human decision whenever Builder's own escalation classifier says the work needs one, which is precisely what would have stopped B8 from reaching a worker on Aug 5 (and blocks the silent `idle/exit 0` re-arming).

---

## Appendix A — evidence file map

- DB: `data/kittybuilder/builder_queue.db` (events 1493–1782; tasks; initiative_packets; packet_attempts 106–114).
- Bundles/briefs/logs: `data/kittybuilder/runs/run_msg7ctiy_a86f/{brief.md,combined.log}` and `run_msg88iiw_9e3a/{brief.md,combined.log}` (bundle JSON `bundle-114.json`, worker wrote `docs/session-notes/2026-08-05-b8-clean-checkout-mission.md`, commit `00edce20`).
- Operator captures: `data/kittybuilder/operator-logs/b2-b10-campaign-20260805-084744.log`, `…-084847.log`, `b8-retry-20260804-220658.log`; `data/kittybuilder/LAST_DRAIN.md`; hourly `drain-logs/drain-20260805-*.log` (all `kx-06`, idle).
- tmux session `builder-b2-b10` created **2026-08-05 08:48:46 L**; pane shows the `idle … exhausted: B8` tail.
- `~/.zsh_history` 3976–3984 (campaign commands), 5254 (`kproof-001-onboarding-work` attempt — legacy only).
- `git show 00edce20`; `git branch --contains 00edce20`.

## Appendix B — labels

- **Evidence:** all DB rows, commit SHAs, run logs, bundle content, tmux pane, initiative/packet states, dependency JSON.
- **Inference:** (1) the operator who ran the tmux campaign on Aug 5 is the same interactive lane documented in `~/kb/NOW.md`; (2) "Repair first-run onboarding and Work navigation" was an interactive-lane approval, intended to be Builder work but never materialized as a DB task (absence of any such task/initiative/event is evidence; its provenance is inference). (3) the "unrelated documentation" === commit `00edce20` + the B8 session-note file.
