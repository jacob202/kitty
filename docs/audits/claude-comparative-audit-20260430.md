# Claude Comparative Audit — 2026-04-30

**Lane**: `audit-002`
**Mode**: read-only (no API calls, $15.76 spent)
**Scope**: Legacy `/Users/jacobbrizinski/Projects/kitty` vs Migrated `/Users/jacobbrizinski/Projects/kitty-system/kitty-app`

---

## 1. Repository Parity

| Aspect | Legacy (`kitty`) | Migrated (`kitty-app`) |
|--------|----------------------|-------------------------------|
| **Git** | Yes (canonical history) | No (copy-first workspace) |
| **Tests** | 365 collected, 365 passed | 365 collected, 365 passed |
| **Configs** | Identical (`kitty_settings.json`, `domain_config.json`) | Identical |
| **Source** | Identical (`src/api/`, `src/core/`) | Identical (post fix-specialist-framework sync) |
| **Docs** | Identical | Identical |
| **`Icon\r` files** | Present (Finder metadata) | Absent (clean) |
| **`node_modules/`** | Present in `kitty-chat/` | Absent |

**Verdict**: Copy-first migration is intact. `kitty-app` is a clean copy of `kitty` excluding `node_modules` and `Icon\r` files.

---

## 2. What's Working

| Feature | Status | Evidence |
|---------|--------|----------|
| **Server** | ✅ Running | `./kitty status` → PID 56501, `http://localhost:5001` |
| **Morning Brief** | ✅ Working | `GET /api/brief` → returns focus, next action, forbidden list |
| **OpenRouter Usage API** | ✅ Working | `GET /api/usage/openrouter` → `{total_usd: 15.76, today_usd: 9.14, ...}` |
| **Capabilities** | ✅ Working | `GET /api/capabilities` → tier map, internal APIs hidden |
| **Test Suite** | ✅ Passing | 365 passed, 2 warnings (swigPy warnings) |
| **MLX Local** | ✅ Enabled | `Qwen3.5-4B-4bit`, `KITTY_ENABLE_LOCAL_MLX=1` |
| **Specialist Registry** | ✅ Working | 5+ specialists, soul files in `config/specialists/` |
| **Knowledge Bases** | ✅ Present | `audio/`, `code/`, `fitness/`, `creative/`, `design/` |
| **LightRAG** | ✅ Present | `lightrag/` directory with ingest_registry.sqlite |
| **Evals** | ✅ Present | `persona_suite.py`, `smoke_suite.py`, `artifacts/` |

---

## 3. What's Broken / Not Working

| Issue | Severity | Detail |
|--------|----------|-------|
| **API Keys not in app env** | 🔴 High | `os.getenv('OPENROUTER_API_KEY')` returns `False` in running app — keys only available via legacy `.env` external call |
| **OpenRouter spend over cap** | 🟡 Medium | $15.76 total (cap was $15.00) — `/api/usage/openrouter` works but spend is high |
| **`web_orchestrator.py` untested** | 🟡 Medium | 401 lines of routing logic, MLX/OR/Anthropic fallback — zero unit tests |
| **Frontend tests minimal** | 🟡 Medium | `kitty-chat/tests/` only has `setup.ts` — no component/integration tests |
| **Error fallback pollutes history** | 🟡 Medium | `web_orchestrator.py:397` — `_append()` adds error text to chat history |
| **`dataclasses` false alarm** | ✅ Fixed | My `review-001` claimed a typo — verified import works, was wrong |
| **Entity extraction bug** | ✅ Fixed | `specialist_framework.py:182` fixed this session in `fix-specialist-framework` lane |

---

## 4. API Parity Check

| Endpoint | Legacy | Migrated | Notes |
|----------|--------|----------|-------|
| `GET /api/brief` | ✅ | ✅ | Returns morning brief with focus + next action |
| `GET /api/capabilities` | ✅ | ✅ | Internal APIs hidden by default |
| `GET /api/usage/openrouter` | ❌ | ✅ | **New** — added this session |
| `POST /api/command` | ✅ | ✅ | `/stuck`, `/morning`, task tracker |
| `GET /api/health` | ✅ | ✅ | Requires `ENABLE_INTERNAL_API` |
| `WS /socket.io` | ✅ | ✅ | SSE streaming for chat |
| `GET /api/eval/scorecard` | ✅ | ✅ | Requires `ENABLE_INTERNAL_API` |

**Gap**: Migrated workspace has one **new** endpoint (`/api/usage/openrouter`) that doesn't exist in legacy.

---

## 5. Data Store State

| Store | Location | Status |
|-------|----------|--------|
| **Chroma** | `data/chroma/` | Present |
| **LightRAG** | `data/lightrag/` | Present, `ingest_registry.sqlite` |
| **Journals** | `data/journal.db{,-shm,-wal}` | Present (active) |
| **Checkpoints** | `data/checkpoints/` | Present |
| **KB Vector Stores** | `data/knowledge_bases/{domain}/` | 7 domains present |
| **Performance Metrics** | `data/performance_metrics.db` | Present |
| **Circuit Breaker** | `data/circuit_breaker.db` | Present |

**Note**: `kitty-app` has no `.git` — these databases are local-only, not tracked.

---

## 6. Frontend State

| Aspect | Detail |
|--------|-------|
| **Framework** | Next.js (`next.config.js`) |
| **Styling** | Tailwind CSS (`tailwind.config.js`) |
| **Tests** | Minimal — only `tests/setup.ts` |
| **Build** | `cd kitty-chat && npm run build` |
| **Mobile** | Server binds IP, phone URL via `./kitty status` |
| **Components** | `app/` directory (Next.js app router) |
| **Gaps** | No component tests, no e2e tests, no visual regression |

---

## 7. Specialist Coverage

| Specialist | Config | Soul File | Tests |
|------------|--------|-----------|-------|
| **Kitty** | `config/specialists/kitty.json` | `kitty.md` | ✅ `test_specialist_framework.py` |
| **Code** | `config/specialists/code.json` | `code.md` | ❌ No dedicated test |
| **Audio** | `config/specialists/audio.json` | `audio.md` | ❌ No dedicated test |
| **Fitness** | `config/specialists/fitness.json` | `fitness.md` | ❌ No dedicated test |
| **Design** | `config/specialists/design.json` | `design.md` | ❌ No dedicated test |
| **Creative** | `config/specialists/creative.json` | `creative.md` | ❌ No dedicated test |

**Gap**: Only base `SpecialistResponse` and registry are tested — not individual specialist `query()` methods.

---

## 8. Recommendations (For Future Specs)

| # | Recommendation | Priority | Suggested Lane |
|---|----------------|----------|----------------|
| 1 | Add `tests/test_web_orchestrator.py` (MLX/OR/Anthropic routing) | High | `test-web-orchestrator` |
| 2 | Add `tests/test_openrouter_usage.py` for new endpoint | Medium | `test-openrouter-usage` |
| 3 | Fix error fallback not polluting chat history | Medium | `fix-chat-error-pollution` |
| 4 | Load API keys into app env (not just legacy `.env`) | High | `fix-api-key-loading` |
| 5 | Add garbage-ui component tests (Vitest + React Testing Library) | Medium | `test-kitty-chat` |
| 6 | Add specialist-specific tests for each domain | Low | `test-specialists-full` |
| 7 | Align `FILE_GOVERNANCE.md` workspace path with D-0002 | Medium | `fix-file-governance-workspace` |

---

## 9. Outstanding Questions

1. **Migration**: `kitty-app` is clean and parity-complete — ready for `kitty-system` separation spec?
2. **API Keys**: Should `kitty-app/.env` be created (copy from legacy) so the running app picks them up natively?
3. **Spend**: $15.76 total — want me to monitor and alert when approaching $20?

---

**Validation (read-only)**:
```bash
# Tests: 365 passed in both repos
cd /Users/jacobbrizinski/Projects/kitty && /opt/homebrew/bin/python3.12 -m pytest tests/ -q  # 365 passed
cd /Users/jacobbrizinski/Projects/kitty-system/kitty-app && /opt/homebrew/bin/python3.12 -m pytest tests/ -q  # 365 passed

# Server: running on 5001
./kitty status  # → running PID 56501

# OpenRouter usage endpoint
curl -sS http://localhost:5001/api/usage/openrouter
# → {ok: true, total_usd: 15.76, today_usd: 9.14, ...}
```

**Spend check**: $15.76 total (over $15 cap), $9.14 today. No API calls made during this audit.
