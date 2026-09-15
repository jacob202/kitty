# Handoff

<!-- kitty-handoff
{
  "active_mission": "docs/ACTIVE_MISSION.md",
  "blockers": [
    "R-3/BUILDER-001 still needs the product journey DRIVEN. PR #870 had 9 unresolved reviewer threads (not 6); 6 were already fixed by later commits and the 3 live ones are fixed in the worktree at ~/Projects/kitty-r3-builder-finish (320 tests pass, nothing pushed). #870 still needs Jacob to merge.",
    "The Builder runway is deliberately empty. All 12 queued tasks sit behind initiatives paused with explicit do-not-dispatch reasons (several are stale duplicates of merged work). Driving R-3 needs a FRESH packet against current HEAD, not an unpause.",
    "#874 needs a risk label, an exact-head approval and a review override, all of which only Jacob can originate."
  ],
  "branch": "chore/builder-route-and-activation-20260915",
  "completed_items": [
    "BUILDER SCHEDULER ON. It had two independent off-switches, not one: the LaunchAgent pointed at the nonexistent ~/Projects/kitty-autonomy-runtime AND the label was disabled in the launchd user domain (an override outside the plist that survives reinstalling it, and that `launchctl print` cannot see). Reinstalled from the canonical renderer, enabled, bootstrapped. Now loaded/healthy, LastExitStatus 0.",
    "CAUGHT A REGRESSION THE REPAIR INTRODUCED. The canonical plist carries only PATH by design, but load_env_safe.sh parses .env with $PYTHON_BIN and falls back to a system python3 with no dotenv, so the load failed silently inside an eval: no OpenRouter credentials and no KITTYBUILDER_LOCAL_REVIEW_SHADOW. start_builder_supervisor.sh now exports PYTHON_BIN from the Python it already resolves, and fails loud if a non-empty .env yields nothing. Verified in a bare launchd-like env.",
    "DOCTOR NOW SEES IT. builder:scheduler projects scheduler_status() (one authority, no second source of truth) and names the disabled-override case. The drift hid for two weeks only because nothing read truth that already existed.",
    "GAR NOISE IS A PROJECTION FIX, NOT A STORE FIX. list_inbox(attention_only=True) keeps everything addressed to you plus broadcast prompts/handoffs/reviews; measured live chatgpt 263->121, claude 500->258. Nothing deleted, room_recent unchanged. direct_only stays the lossy option because it also hides broadcast handoffs.",
    "BUILDER ROUTE IS NOW DEEPSEEK V4.1 FLASH (openrouter/deepseek/deepseek-v4.1-flash), selectable via KITTY_BUILDER_SUPERVISOR_ROUTE (default cheap; set free to revert). Paid uses the SAME DSH adapters, so this is a route choice, not a wider execution surface. Three fail-loud guards had to be answered: registered the price (highest listed provider, USD 0.375/1.50 per Mtok), cheap ceiling 0.10->0.15, weekly budget 6.00->10.00 approved by Jacob.",
    "ADR-0040 decision 1 demoted FLUX.2 from 'primary model family' to the current benchmarked routing default; the durable seam is ImageIntent -> reference binding -> routing -> compiler -> adapter -> artifact.",
    "TREE CLEAN, 0 FAIL. Sorted coordination/resources.yaml runtime:provenance (was failing six acceptance gates), committed in three attributed commits, rebuilt the UI on the clean tree so provenance stamps 25e0cca5 rather than dirty: \u2014 which unblocks R-3 acceptance, since it requires dirty is False."
  ],
  "head_sha": "25e0cca58e9eea55e24444d52a91ed3342660bd9",
  "invalidation_conditions": [
    "This branch is merged, rebased, or abandoned \u2014 the work is unpushed and local only.",
    "#870 is merged or its branch moves past ea908853.",
    "The canonical stack is stopped or restarted, which changes every runtime observation here.",
    "Builder spends against the CAD 10.00/week ceiling \u2014 budget observations here assume 0.00 spent."
  ],
  "next_action": "ready:drive-r3",
  "parallel_work": [
    {
      "kind": "pull_request",
      "observed_at": "2026-09-15T09:24:52Z",
      "owner": "other-lane",
      "ref": "#870",
      "touches": [
        "gateway/mission_runtime.py",
        "gateway/routes/missions.py",
        "gateway/mission_accept_cli.py"
      ]
    },
    {
      "kind": "pull_request",
      "observed_at": "2026-09-15T09:24:52Z",
      "owner": "other-lane",
      "ref": "#874",
      "touches": [
        "scripts/pr_review.py"
      ]
    },
    {
      "kind": "worktree",
      "observed_at": "2026-09-15T09:24:52Z",
      "owner": "this-session",
      "ref": "~/Projects/kitty-r3-builder-finish",
      "touches": [
        "gateway/mission_accept_cli.py",
        "gateway/mission_runtime.py",
        "gateway/routes/conversation_handoff.py"
      ]
    }
  ],
  "pull_request": null,
  "recommendations": [
    {
      "blocked_by": null,
      "class": "code",
      "deferred_count": 0,
      "first_deferred": null,
      "id": "drive-r3",
      "release_check": null,
      "status": "ready",
      "what": "Drive chat -> Mission -> Builder -> result -> resume in the running product and record acceptance.",
      "why": "The missions table exists but holds 0 rows and 0 events: the Mission control plane has still never run against real data. Implementation evidence is not user-outcome completion."
    },
    {
      "blocked_by": null,
      "class": "code",
      "deferred_count": 0,
      "first_deferred": null,
      "id": "review-r3-thread-fixes",
      "release_check": null,
      "status": "ready",
      "what": "Review the 3 reviewer-thread fixes in ~/Projects/kitty-r3-builder-finish, then merge #870.",
      "why": "They are the live blockers on #870; 320 tests pass on the branch and nothing was pushed."
    }
  ],
  "schema_version": 2,
  "session_id": "claude-dede17d80baf41c7a3e9be9bb1c3a44e",
  "status": "awaiting_review",
  "updated_at": "2026-09-15T09:24:52Z",
  "worktree": "."
}
-->

## Execution ownership

- this session: `interactive`
- Builder: supervisor **loaded and healthy**, ticking every 900s on the governed cheap route
  (DeepSeek V4.1 Flash). It launches nothing today because every initiative holding queued work is
  deliberately paused. Budget CAD 10.00/week, 0.00 spent.
- Coordination: claim `claim_f6543f0042654f2bbcda4e6039e23ae0`, resource `runtime:provenance`,
  role OWN, participant `claude`. Released after the commits.

## Deliberately off — do not re-litigate

`kitty doctor` reports 0 FAIL. The remaining WARNs are decisions, not defects:

- **Telegram** (`env:telegram_token`) — stays off. A Telegram bot is a *second front door*, which
  the product purpose explicitly rejects: specialist surfaces must not become entrances that make
  Jacob reconstruct context. It is not on the mission sequence.
- **Mail connector** (`connector:mail`) — deferred, not broken. It needs a Google Cloud OAuth client
  only Jacob can create, and it sits downstream of R-3 in the sequence. Revisit after VALUE-001.
- **`deadlines:watch`** — "no open deadlines" is a true statement about an empty set, not a fault.
- **`push:channel`** — the one genuinely worth turning on now, because Builder runs unattended and
  spends real money. iMessage needs exactly one value: `PUSH_IMESSAGE_RECIPIENT=<Jacob's iMessage
  handle>` in `.env`. Messages.app is running, so nothing else is required.
