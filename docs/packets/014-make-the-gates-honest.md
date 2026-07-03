# Packet 014 — Make the gates honest

- **Status:** ready — diagnosis complete 2026-07-02; every fix below is
  pre-decided. This packet is mechanical.
- **Best executor:** any competent model (Codex, Claude Code, cheap tier).
  No judgment calls remain; if one appears, the packet is defective — stop.
- **Purpose:** The UI test suite fails (6 tests), no CI job runs it, and two
  Python tests leak real local data. #70 merged red and broke main because a
  gate didn't exist. This packet makes every gate real before packet 004
  builds on top of them.

## Context you need (all of it — do not re-diagnose)

1. **The 6 UI failures are stale text matchers, not bugs.** The v2 design
   migration (#56/#57) rewrote `SessionSidebar` and `TopBar` copy; the tests
   still assert pre-v2 copy. **The components are the source of truth. Never
   change component copy or layout to satisfy a test** — with one deliberate
   exception (the TopBar `title` attribute, below).
2. **`npm run <script>` exits 194 silently on Jacob's machine** (node 26.4 /
   npm 11.17, repo-specific, un-root-caused). Locally you MUST use direct
   bins: `./node_modules/.bin/vitest run` and
   `node node_modules/next/dist/bin/next build`. CI (ubuntu) does not have
   this bug, but use direct bins there too so there is exactly one invocation
   path everywhere.
3. **The 2 Python failures are test-isolation leaks** — they pass on CI
   (clean `data/`) and fail locally where real data exists. The fix is
   isolation in the tests, never changes to production code.

## Exact scope

### A. Fix the 6 UI tests (`gateway/kitty-chat/tests/`)

`tests/SessionSidebar.test.tsx` — current v2 component facts
(`src/components/SessionSidebar.tsx`): there is **no** `sessions` header, no
close (✕) button, and no collapsed mode (the `collapsed` prop is accepted but
unimplemented). The new-chat button's text is `+` + ` new chat`. Group labels
are lowercase: `today`, `yesterday`, `earlier`. There is a search input with
placeholder `search chats` and a footer reading `all synced · audience of one`.

Per-test decisions:

1. `renders sessions header and new chat button` → rename to
   `renders new chat button and search input`; assert
   `screen.getByRole('button', { name: '+ new chat' })` and
   `screen.getByPlaceholderText('search chats')`. Drop the `sessions` assert.
2. `shows today and earlier groups based on date` → assert
   `screen.getByText('today')` and `screen.getByText('earlier')` (lowercase).
   Note: mockChats has one chat <24h old and one 48h old, so `yesterday`
   does not render — do not assert it.
3. `shows chat titles` → passes already; leave untouched.
4. `calls onSelectChat when session clicked` → passes already; leave untouched.
5. `shows close button only on hover for non-collapsed` → **delete.** v2 has
   no close affordance; `onCloseChat` is a dead prop (see "Debt recorded").
6. `collapses to icon-only mode when collapsed prop is true` → **delete.**
7. `new chat button shows + only when collapsed` → **delete.**

`tests/gatewayIntegration.test.tsx` — the failing test expects
`getByTitle('Using offline model list')`. v2 signals offline by turning the
model dot red (`background: modelFromGateway ? activeModel.color :
'var(--c-red)'` in `src/components/TopBar.tsx`) with no accessible name.
**Decision: restore the `title` attribute on that dot element** —
`title={modelFromGateway ? undefined : 'Using offline model list'}` — and
leave both tests as written. This is the one allowed component edit: it adds
an accessible name, changes zero pixels.

### B. Add a kitty-chat CI job

Append to `.github/workflows/tests.yml` (alongside `pytest`/`lint`/`typecheck`):

```yaml
kitty-chat:
  runs-on: ubuntu-latest
  defaults:
    run:
      working-directory: gateway/kitty-chat
  steps:
    - name: Checkout
      uses: actions/checkout@v4
    - name: Setup Node
      uses: actions/setup-node@v4
      with:
        node-version: 22
        cache: npm
        cache-dependency-path: gateway/kitty-chat/package-lock.json
    - name: Install
      run: npm ci
    - name: Test
      run: ./node_modules/.bin/vitest run
    - name: Build
      run: node node_modules/next/dist/bin/next build
```

Blocking from day one (no `continue-on-error`) — part A makes it green first.

### C. Makefile targets for the direct-bin invocations

Add to the root `Makefile` (which currently has only `agent-wrap`):

```make
.PHONY: agent-wrap ui-test ui-build

ui-test:
	cd gateway/kitty-chat && ./node_modules/.bin/vitest run

ui-build:
	cd gateway/kitty-chat && node node_modules/next/dist/bin/next build
```

Then update the "Commands" section of `CLAUDE.md` root file: replace
`cd gateway/kitty-chat && npm test && npm run build` with
`make ui-test && make ui-build   # npm run is broken on this machine (exit 194)`.

### D. Fix the 2 Python isolation leaks (tests only — no production code)

1. `tests/test_action_queue.py::test_t0_executes_from_proposed_and_records_result`
   — the autouse `isolate` fixture patches `todo_store.TODO_DB_FILE`, yet the
   final assert `todo_store.get()[0]["content"] == "buy milk"` sees real
   rows locally. Diagnose which read path in `gateway/todo_store.py` binds
   the DB path at def time / import time instead of reading the module
   constant at call time (same class of bug as the `read_inbox` default-arg
   note in `tests/test_state_composer.py`), and patch the correct seam in
   the fixture. If the only fix is a production-code change, STOP and split
   a packet — do not touch `gateway/` here.
2. `tests/test_state_composer.py::test_real_sources_compose_against_isolated_stores`
   — patches todo/chats/journal/desktop stores but **not the signal store**;
   since #77, real signals exist locally, so
   `sections["signals"]["unprocessed_count"] == 0` fails. Add
   `monkeypatch.setattr(signal_store, "SIGNALS_DB_FILE", db_file, raising=False)`
   (import `signal_store` alongside the other stores; mirror the existing
   patch style in that test).

## Files likely touched

- `gateway/kitty-chat/tests/SessionSidebar.test.tsx`
- `gateway/kitty-chat/tests/gatewayIntegration.test.tsx`
- `gateway/kitty-chat/src/components/TopBar.tsx` (the `title` attribute only)
- `.github/workflows/tests.yml`
- `Makefile`, `CLAUDE.md` (Commands section only)
- `tests/test_action_queue.py`, `tests/test_state_composer.py` (fixtures only)

## Files not to touch

- `src/components/SessionSidebar.tsx` — no component changes; tests conform
  to it, not the reverse.
- Any `gateway/*.py` production module. Isolation is fixed in test fixtures.
- The existing `pytest`/`lint`/`typecheck` CI jobs.

## Debt recorded, not fixed here

`SessionSidebar`'s `collapsed`, `width`, and `onCloseChat` props are accepted
but unimplemented in v2 (close-chat UI was lost in the migration). Do not
implement or remove them in this packet — note them in the PR description so
packet 004 decides their fate.

## Acceptance criteria

- `make ui-test` → 0 failures locally.
- `make ui-build` → exits 0 locally.
- `python3.12 -m pytest tests/test_action_queue.py tests/test_state_composer.py -q`
  → 0 failures **on Jacob's machine with real `data/` present** (that's the
  point; CI-green alone proves nothing here).
- Full suite: `python3.12 -m pytest tests/ -q --tb=short` → no new failures.
- The PR's CI shows a `kitty-chat` check run, and it is green.
- Zero changes to component copy/layout except the TopBar `title` attribute.

## Verification

```bash
make ui-test && make ui-build
python3.12 -m pytest tests/ -q --tb=short
git diff --stat   # confirm no unexpected files
```

## Risks / rollback

- **CI node version drift vs local (26.x local, 22 on CI):** acceptable —
  next/vitest support both; local direct-bin runs stay the source of truth.
- **Rollback:** revert the PR; tests return to red, which is where they are now.

## Too broad if

It implements the collapsed sidebar or close-chat feature, root-causes the
npm-194 bug, touches production Python, or restyles anything.

## Jacob reviews

Nothing — mechanical packet. Merge on green CI + reviewer pass.
