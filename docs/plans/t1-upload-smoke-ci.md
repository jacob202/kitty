# Plan: T1 Cards E, F, G — Upload Limits, Browser Smoke, CI Alignment

**Goal:** Close the three remaining T1 Codex blockers — streaming upload caps, a
minimal Playwright smoke suite in CI, and Python-version/coverage alignment — so
all non-T2 work is done.

---

## Card E — Blocker #8: Upload Limits

### Background

The global middleware (`gateway/app.py:156`) only checks `Content-Length` headers.
Chunked `Transfer-Encoding` requests bypass it entirely. Two upload handlers read
the full body into memory with no per-route cap:

| Handler | File | Current behavior |
|---|---|---|
| `POST /v1/audio/transcriptions` | `gateway/routes/voice.py:25` | `await file.read()` — unbounded |
| `POST /inventory/photo` | `gateway/routes/kitty_tools.py:61` | `await file.read()` — unbounded |
| WS `/voice` | `gateway/voice_pipeline.py:258` | `ws.receive()` — frame unbounded |

`POST /capture/file` (`gateway/routes/capture.py:168`) and
`POST /knowledge/ingest` (URL download, `gateway/routes/knowledge.py:257`) already
stream with caps — they are the model pattern.

### Files

| File | Change |
|---|---|
| `gateway/constants.py` | Add `MAX_VOICE_BYTES`, `MAX_INVENTORY_BYTES` |
| `gateway/routes/voice.py` | Chunked read with cap, HTTPException on overflow |
| `gateway/routes/kitty_tools.py` | Chunked read with cap, HTTPException on overflow |
| `gateway/voice_pipeline.py` | Pass `max_size=` to `ws.accept()` |
| `tests/test_upload_limits.py` | **[NEW]** regression tests: oversized voice, oversized inventory, WS frame cap |

### Steps

- [ ] **E1.** Add constants to `gateway/constants.py`:
  ```python
  MAX_VOICE_BYTES = 25 * 1024 * 1024    # 25 MB — long voice memo
  MAX_INVENTORY_BYTES = 10 * 1024 * 1024  # 10 MB — photo
  ```
- [ ] **E2.** Fix `gateway/routes/voice.py:25` — replace bare `await file.read()`
  with a chunked read loop matching `capture.py:168-181` pattern (read in 64 KB
  chunks, track cumulative bytes, raise HTTPException 413 on overflow).
- [ ] **E3.** Fix `gateway/routes/kitty_tools.py:61` — same chunked-read pattern
  for the inventory photo upload, using `MAX_INVENTORY_BYTES`.
- [ ] **E4.** Fix `gateway/voice_pipeline.py` — pass `max_size=MAX_BODY_BYTES`
  (10 MB) to `ws.accept()` in the WebSocket handler.
- [ ] **E5.** Write `tests/test_upload_limits.py` — three tests:
  - Oversized voice upload → 413 (mock UploadFile with size > MAX_VOICE_BYTES)
  - Oversized inventory photo → 413 (same pattern)
  - Verify constants exist and are sane (non-zero, reasonable)
- [ ] **E6.** Run `python3.12 -m pytest tests/test_upload_limits.py -q --tb=short`
  → all pass. Run `./venv/bin/ruff check` on changed files → clean.

### Verification

```bash
python3.12 -m pytest tests/test_upload_limits.py -q --tb=short
# Expected: all pass (3-4 tests)
./venv/bin/ruff check gateway/constants.py gateway/routes/voice.py \
          gateway/routes/kitty_tools.py gateway/voice_pipeline.py \
          tests/test_upload_limits.py
# Expected: All checks passed!
```

---

## Card F — Blocker #9: Browser Smoke Tests

### Background

Playwright v1.61.1 exists in `node_modules/` as a transitive dep of Next.js but is
not declared as a direct dependency. `pytest.ini` defines a `browser` marker but no
tests use it. CI has no browser test job. The frontend is a single-page Next.js app
on port 4000 with 11+ client-side views.

The Codex report mandates live browser verification for UI tasks. A minimal smoke
suite proves the app boots, navigates, and doesn't crash.

### Files

| File | Change |
|---|---|
| `gateway/kitty-chat/package.json` | Add `@playwright/test` as devDependency |
| `gateway/kitty-chat/playwright.config.ts` | **[NEW]** — baseURL localhost:4000, webServer config, projects (desktop + mobile) |
| `gateway/kitty-chat/tests/smoke/` | **[NEW dir]** — 3-4 spec files |
| `.github/workflows/tests.yml` | Add `browser-smoke` job (install Playwright, start UI, run specs) |
| `Makefile` | Add `smoke-test` target |

### Steps

- [ ] **F1.** Add `@playwright/test` to `gateway/kitty-chat/package.json` devDeps.
  Run `npm ci` in `gateway/kitty-chat/` to install.
- [ ] **F2.** Create `gateway/kitty-chat/playwright.config.ts`:
  - `baseURL: 'http://localhost:4000'`
  - `webServer`: `npm run start` with port 4000 check, timeout 30s
  - Two projects: `desktop` (1280×720) and `mobile` (iPhone 14, 390×844)
  - `testDir: './tests/smoke'`
  - Retries: 1, timeout: 30s per test
- [ ] **F3.** Create `gateway/kitty-chat/tests/smoke/boot.spec.ts`:
  - Page loads without console errors (assert no `page.on('pageerror')`)
  - Title contains "Kitty" or is non-empty
  - Main view renders (check for `[data-testid="home"]` or visible heading)
- [ ] **F4.** Create `gateway/kitty-chat/tests/smoke/navigation.spec.ts`:
  - Sidebar links exist and are clickable
  - Clicking each nav item loads a view without crashing
  - URL doesn't change (SPA), but view content does
- [ ] **F5.** Create `gateway/kitty-chat/tests/smoke/chat.spec.ts`:
  - Navigate to chat view
  - Input bar is visible and accepts text
  - Submit a message (can mock the proxy response or use a test fixture)
  - Chat message area renders without crash
- [ ] **F6.** Create `gateway/kitty-chat/tests/smoke/settings.spec.ts`:
  - Navigate to settings view
  - Settings panel renders with expected sections
  - Mobile layout: viewport ≤900px shows sidebar overlay pattern
- [ ] **F7.** Add `browser-smoke` job to `.github/workflows/tests.yml`:
  - Runs after `kitty-chat` job (needs build)
  - Steps: checkout, setup-node, npm ci, npx playwright install chromium,
    `npm run start &`, wait-for-port 4000, `npx playwright test`, upload artifacts
- [ ] **F8.** Add `smoke-test` to Makefile: `cd gateway/kitty-chat && npx playwright test`
- [ ] **F9.** Run locally: `cd gateway/kitty-chat && npx playwright test` → all pass.

### Verification

```bash
cd gateway/kitty-chat && npx playwright test --reporter=list
# Expected: boot, navigation, chat, settings specs pass on desktop + mobile
# (6 total: 3 specs × 2 projects, or 4 specs × 2 = 8)
```

---

## Card G — Blocker #10: CI Alignment + Coverage

### Background

CI uses Python 3.11; all local commands use 3.12. Coverage is reported but not
gated (`--cov-fail-under` deferred). No `.python-version` file. No `make test`
target for Python.

### Files

| File | Change |
|---|---|
| `.python-version` | **[NEW]** — `3.12` |
| `.github/workflows/tests.yml` | Bump `python-version: '3.12'` in all 3 Python jobs |
| `pyproject.toml` | Update `target-version = "py312"`, `python_version = "3.12"` |
| `Makefile` | Add `test` target (Python) and `ci` target (full local CI) |
| `AGENTS.md` | Update default commands to note `.python-version` alignment |

### Steps

- [ ] **G1.** Create `.python-version` with content `3.12`.
- [ ] **G2.** Update `.github/workflows/tests.yml`:
  - Change `python-version: '3.11'` → `'3.12'` in all three Python jobs
    (pytest, lint, typecheck)
- [ ] **G3.** Update `pyproject.toml`:
  - `[tool.ruff] target-version = "py312"`
  - `[tool.mypy] python_version = "3.12"`
- [ ] **G4.** Add to `Makefile`:
  ```makefile
  test:
  	python3.12 -m pytest tests/ -q --tb=short
  ci: lint typecheck test ui-test ui-build
  lint:
  	./venv/bin/ruff check gateway/ tests/
  typecheck:
  	python3.12 -m mypy gateway/
  ```
- [ ] **G5.** Run locally to verify: `make ci` → all pass.
- [ ] **G6.** Run `--cov-fail-under` measurement:
  ```bash
  python3.12 -m pytest tests/ --cov=gateway --cov-report=term-missing -q --tb=short 2>&1 | tail -5
  ```
  Record the coverage %. Add `--cov-fail-under=<measured - 4>` to CI's pytest
  invocation and to `pyproject.toml [tool.coverage] report fail_under`.

### Verification

```bash
make ci
# Expected: lint pass, typecheck pass, pytest pass, vitest pass, next build pass
python3.12 -m pytest tests/ --cov=gateway --cov-report=term-missing -q --tb=short 2>&1 | grep "TOTAL"
# Expected: TOTAL line shows coverage %, fail_under is set
```

---

## Execution Order

**Sequential within each card, parallel across cards:**

```
Card E (upload limits)     ──→ independent, can run in parallel
Card F (browser smoke)     ──→ independent, can run in parallel
Card G (CI alignment)      ──→ independent, can run in parallel
```

All three cards touch disjoint files — no merge conflicts. Each card commits
independently.

## Risks

| Risk | Mitigation |
|---|---|
| Playwright install fails in CI (no Chromium binary) | Use `npx playwright install --with-deps chromium` in CI job; pin Playwright version |
| Coverage measurement reveals regressions | Measure first, set threshold at measured minus 4, not at 100% |
| Voice/inventory chunked read changes behavior for large files | Match capture.py pattern exactly — same chunk size, same cleanup |
| WebSocket `max_size` too restrictive for legitimate audio | Set to 10 MB (same as global body limit); voice frames are typically <1 MB |
