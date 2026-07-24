# Handoff — KX-05/KX-06 + Reasoning Backend + Dogfood — Complete

## What was done

### KX-05 (Companion Layer) — 5 packets
- **01 (onboarding):** gateway persistence via `app_settings` table, cross-device sync, ChatGPT/Claude import wizard step. New: `gateway/onboarding.py`, `gateway/routes/onboarding.py`, `gateway/routes/import_chatgpt.py`
- **02 (self-repairs):** `/repairs` endpoint with plain-English titles + T0 action-queue fix buttons. RepairsCard on Home under "system" section. Chat intent: "what's wrong" injects repair feed. New: `gateway/actions/repair_check.py`, `repair_dismiss.py`
- **03 (builder control):** `/builder/action` endpoint (run/pause/resume/cancel/cleanup via T0 action queue). BuilderControls component on Builder surface. Fixed `packetNeedsAttention` to exclude `cancelled`. New: `gateway/routes/builder_control.py`, 5 builder action executors
- **04 (experts):** `/knowledge/experts` from books_manifest (5 experts: builder 81, mind 53, wisdom 52, body 25, voice 8). ExpertStrip on Home with book counts + sample titles
- **05 (chat polish):** ActiveTaskCards capped at 3 + test-data filter + "+N more" expand. StatusBar 3-consecutive-fail threshold (no more flapping). Memory evidence suppressed on smalltalk. Session resume card reads H1 heading. CLI copy purged from 7 places

### KX-06 (Proactive Feed) — 2 packets
- **01 (signals):** `/signals` endpoint returns RepairsIssue shape from signal_store. SignalsCard on Home with 20 Web_monitor items + Dismiss buttons
- **02 (deadline cards):** PhoneAccessCard plain-English copy (no CLI/API jargon)

### Reasoning Backend (RE-C1/C2/C5) — confirmed complete
- `gateway/reasoning.py`: `classify_complexity()` heuristic (trivial/standard/deep) wired into `route_model()` and completions pipeline. 105/105 tests pass
- `gateway/context_assembler.py`: tier-aware caps 300/1200/2400, trivial skips enrichments
- Execution receipts: `Receipt` + `log_receipt()` stitched into existing `log_llm_usage()` sites

### Backend net-new files
- `gateway/onboarding.py`, `gateway/routes/onboarding.py`, `gateway/routes/import_chatgpt.py`
- `gateway/routes/builder_control.py`, `gateway/routes/signals.py`
- `gateway/actions/repair_check.py`, `repair_dismiss.py`, `builder_*.py` (5 files)
- `config/action_tiers.json` — 7 new T0 action kinds

### Dogfood results
- ✅ Onboarding wizard: 4 steps, name "Jacob" persists across reload
- ✅ Experts strip: 5 experts rendering with book counts + sample titles
- ✅ System repairs: "everything looks healthy" card on Home
- ✅ Signals: 20 Web_monitor items with Dismiss buttons
- ✅ Import wizard: tested with real export, `--source` flag fixed
- ✅ Builder: controls component renders pause/resume/cleanup buttons
- ⚠️ Greeting name: wired into WhatsNext empty state (not visible when session context has data)

### Verification
- Frontend: TypeScript clean, 36/36 HomeState tests pass, 66/66 affected tests pass
- Backend: 105/105 reasoning tests pass, 142/144 llm tests pass (2 fail on LiteLLM local)
- Build: `npm run build` clean

## Lessons learned

1. Builder workers stuck as `[blocked]` need initiative-level gate cleared. Manual builds faster.
2. Action tiers + executor files are a paired contract — add both in same commit.
3. Test assertions by exact text are brittle — use regex matchers.
4. StatusBar flapping is render-count, not polling. Use render-side ref, not useEffect.
5. Launchd gateway processes need full unload/reload — `./kitty down` doesn't touch launchd.
6. Route registration in `register.py` must include both import AND loop entry.

## Blockers
None. `.git/index.lock` reoccurs — a background process (codegraph/builder) holds git locks intermittently.

## Invalidation
HEAD beyond `54784e0`.
