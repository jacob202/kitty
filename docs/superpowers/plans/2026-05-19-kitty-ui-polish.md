# Kitty UI Full Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining UI polish items from the 2026-05-18 spec — debounced search with abort, RightBar search error display, TopBar fallback indicator, BriefPanel loading skeleton, and failure-path tests.

**Architecture:** All changes are local to `gateway/kitty-chat/`. Gateway typed payloads already exist; this pass adds abort support to `fetchGatewaySearch`, fixes the search effect's dependency to avoid re-firing on every streaming chunk, surfaces errors that are currently silently dropped, and adds loading/fallback visual signals where the UI is currently blank.

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript, Vitest + RTL + jsdom

---

## File Map

| File | Change |
|---|---|
| `gateway/kitty-chat/src/lib/gateway.ts` | Add `signal?` to `fetchWithTimeout` and `fetchGatewaySearch`; special-case external-abort vs timeout-abort in catch |
| `gateway/kitty-chat/src/app/page.tsx` | Fix search effect: stable `searchQuery` memo + 400ms debounce + AbortController |
| `gateway/kitty-chat/src/components/RightBar.tsx` | Show "search unavailable" card when `searchGatewayError` is set and `search` is null |
| `gateway/kitty-chat/src/components/TopBar.tsx` | Add `modelFromGateway` prop; show warning-colored dot when offline |
| `gateway/kitty-chat/src/components/BriefPanel.tsx` | Add `loading` prop; render skeleton while brief is fetching |
| `gateway/kitty-chat/tests/gatewayIntegration.test.tsx` | Tests: 500 from search → error payload; RightBar error card; TopBar offline indicator; BriefPanel skeleton |

---

## Task 1: Add AbortSignal support to `fetchGatewaySearch`

**Files:**
- Modify: `gateway/kitty-chat/src/lib/gateway.ts`

The `fetchWithTimeout` function creates its own `AbortController` for the timeout. We need to forward an external signal so the caller (debounce cleanup) can cancel in-flight requests. When the external signal aborts, we abort the internal controller. When the timeout fires, the internal controller aborts normally.

In `fetchGatewaySearch`, distinguish a caller-cancelled abort (neutral — discard) from a timeout abort (error — gateway unreachable).

- [ ] **Step 1: Write failing test for external abort**

Add to `gateway/kitty-chat/tests/gatewayIntegration.test.tsx`:

```typescript
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { fetchGatewaySearch } from '../src/lib/gateway'

describe('fetchGatewaySearch abort', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
    vi.stubGlobal('window', {
      setTimeout: globalThis.setTimeout,
      clearTimeout: globalThis.clearTimeout,
    })
  })
  afterEach(() => { vi.unstubAllGlobals() })

  it('returns neutral payload when caller aborts before fetch completes', async () => {
    // Never resolves — simulates slow network
    vi.mocked(global.fetch).mockReturnValue(new Promise(() => {}))

    const controller = new AbortController()
    const pendingResult = fetchGatewaySearch('test query', 3, controller.signal)
    controller.abort()

    const result = await pendingResult
    expect(result.fromLiveGateway).toBe(true)
    expect(result.error).toBeNull()
    expect(result.snapshot).toBeNull()
  })

  it('returns error payload when gateway returns 500', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(null, { status: 500, statusText: 'Internal Server Error' })
    )

    const result = await fetchGatewaySearch('test query')
    expect(result.fromLiveGateway).toBe(false)
    expect(result.error).toContain('500')
    expect(result.snapshot).toBeNull()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/Projects/kitty/gateway/kitty-chat && npm test 2>&1 | tail -30
```

Expected: both new tests FAIL (function signature doesn't accept signal yet / abort not handled).

- [ ] **Step 3: Update `fetchWithTimeout` to forward external signal**

In `gateway/kitty-chat/src/lib/gateway.ts`, replace `fetchWithTimeout`:

```typescript
async function fetchWithTimeout(
  input: string,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  externalSignal?: AbortSignal,
): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)

  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort()
    } else {
      externalSignal.addEventListener('abort', () => controller.abort(), { once: true })
    }
  }

  try {
    return await fetch(input, { signal: controller.signal })
  } finally {
    window.clearTimeout(timeoutId)
  }
}
```

- [ ] **Step 4: Update `fetchGatewaySearch` signature and catch block**

In `gateway/kitty-chat/src/lib/gateway.ts`, replace `fetchGatewaySearch`:

```typescript
export async function fetchGatewaySearch(
  query: string,
  limit = 5,
  signal?: AbortSignal,
): Promise<GatewaySearchPayload> {
  const q = query.trim()
  if (!q) {
    return { snapshot: null, fromLiveGateway: true, error: null }
  }

  try {
    const response = await fetchWithTimeout(
      `${GATEWAY_BASE}/search?q=${encodeURIComponent(q)}&limit=${limit}`,
      1800,
      signal,
    )
    if (!response.ok) {
      return {
        snapshot: null,
        fromLiveGateway: false,
        error: describeFetchError(null, response),
      }
    }
    const json = await response.json()
    return {
      snapshot: summarizeGatewaySearch({
        query: q,
        memories: json?.memories,
        knowledge: json?.knowledge,
        journal: json?.journal,
        todos: json?.todos,
      }),
      fromLiveGateway: true,
      error: null,
    }
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      if (signal?.aborted) {
        // Caller cancelled (debounce cleanup) — discard silently
        return { snapshot: null, fromLiveGateway: true, error: null }
      }
      // Our internal timeout fired
      return {
        snapshot: null,
        fromLiveGateway: false,
        error: 'Request timed out — is the Kitty gateway running?',
      }
    }
    return {
      snapshot: null,
      fromLiveGateway: false,
      error: describeFetchError(err, null),
    }
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd ~/Projects/kitty/gateway/kitty-chat && npm test 2>&1 | tail -30
```

Expected: both `fetchGatewaySearch abort` tests PASS; existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/kitty && git add gateway/kitty-chat/src/lib/gateway.ts gateway/kitty-chat/tests/gatewayIntegration.test.tsx
git commit -m "feat(kitty-chat): add AbortSignal support to fetchGatewaySearch"
```

---

## Task 2: Debounce search in `page.tsx`

**Files:**
- Modify: `gateway/kitty-chat/src/app/page.tsx`

The current search `useEffect` depends on the full `activeChat` object, which changes on every streaming token (assistant message updates). This fires a new search on each chunk. Fix by:
1. Deriving a stable `searchQuery` string that only changes when the **user message count** changes or the active chat switches.
2. Replacing the effect with a 400ms debounce + `AbortController` that cancels on cleanup.

- [ ] **Step 1: Add `searchQuery` memo after the `activeChat` derivation**

In `gateway/kitty-chat/src/app/page.tsx`, after line 85 (`const activeChat = ...`), add:

```typescript
const userMessageCount = activeChat?.messages.filter(m => m.role === 'user').length ?? 0
// Only recalculate when the active chat or user message count changes — not on every stream chunk
// eslint-disable-next-line react-hooks/exhaustive-deps
const searchQuery = useMemo(() => latestSearchQuery(activeChat), [activeChatId, userMessageCount])
```

Add `useMemo` to the React import at the top of the file (it's already imported, verify: line 2 shows `startTransition, useState, useRef, useEffect, useCallback` — add `useMemo`):

```typescript
import { startTransition, useState, useRef, useEffect, useCallback, useMemo } from 'react'
```

- [ ] **Step 2: Replace the search useEffect**

Find the search `useEffect` (currently lines 133–160) and replace it entirely:

```typescript
useEffect(() => {
  if (!searchQuery) {
    setSearchSnapshot(null)
    setSearchGateway({ live: true, error: null })
    return
  }

  const controller = new AbortController()

  const timeoutId = window.setTimeout(async () => {
    const payload = await fetchGatewaySearch(searchQuery, 3, controller.signal)
    if (controller.signal.aborted) return
    startTransition(() => {
      setSearchSnapshot(payload.snapshot)
      setSearchGateway({ live: payload.fromLiveGateway, error: payload.error })
    })
  }, 400)

  return () => {
    clearTimeout(timeoutId)
    controller.abort()
  }
}, [searchQuery])
```

- [ ] **Step 3: TypeScript check**

```bash
cd ~/Projects/kitty/gateway/kitty-chat && npx tsc --noEmit 2>&1
```

Expected: no errors.

- [ ] **Step 4: Run all tests**

```bash
cd ~/Projects/kitty/gateway/kitty-chat && npm test 2>&1 | tail -20
```

Expected: all existing tests pass.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/kitty && git add gateway/kitty-chat/src/app/page.tsx
git commit -m "fix(kitty-chat): debounce search — only re-query on user message or chat switch"
```

---

## Task 3: RightBar search error display

**Files:**
- Modify: `gateway/kitty-chat/src/components/RightBar.tsx`
- Modify: `gateway/kitty-chat/tests/gatewayIntegration.test.tsx`

Currently when search fails (`searchGatewayError` is set), the `search` snapshot is `null` and no card renders — the user sees nothing. Add a "Search unavailable" card that shows when the error prop is non-null and search snapshot is null.

- [ ] **Step 1: Write failing test**

Add to `gateway/kitty-chat/tests/gatewayIntegration.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react'
import { RightBar } from '../src/components/RightBar'

describe('RightBar', () => {
  it('shows search unavailable card when searchGatewayError is set', () => {
    render(
      <RightBar
        chats={[]}
        activeChat={null}
        isStreaming={false}
        search={null}
        searchGatewayError="Gateway returned 500 Internal Server Error"
      />
    )
    expect(screen.getByText('Search unavailable')).toBeInTheDocument()
    expect(screen.getByText(/500/)).toBeInTheDocument()
  })

  it('shows search results when search snapshot has data', () => {
    render(
      <RightBar
        chats={[]}
        activeChat={null}
        isStreaming={false}
        search={{
          query: 'test',
          counts: { memories: 1, knowledge: 0, journal: 0, todos: 0 },
          sections: {
            memories: ['Memory A: remember this'],
            knowledge: [],
            journal: [],
            todos: [],
          },
        }}
        searchGatewayError={null}
      />
    )
    expect(screen.getByText('Gateway search')).toBeInTheDocument()
    expect(screen.getByText('Memories')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/Projects/kitty/gateway/kitty-chat && npm test 2>&1 | grep -A 3 "RightBar"
```

Expected: `Search unavailable` test FAILS (element not found).

- [ ] **Step 3: Add search error card to RightBar**

In `gateway/kitty-chat/src/components/RightBar.tsx`, find the `{search && (...)}` block (around line 103) and add the error card immediately before it:

```typescript
      {searchGatewayError && !search && (
        <RightCard accent="var(--warning)" title="Search unavailable">
          <p style={bodyStyle}>{searchGatewayError}</p>
        </RightCard>
      )}

      {search && (
        // ... existing block unchanged
```

- [ ] **Step 4: Run tests**

```bash
cd ~/Projects/kitty/gateway/kitty-chat && npm test 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/kitty && git add gateway/kitty-chat/src/components/RightBar.tsx gateway/kitty-chat/tests/gatewayIntegration.test.tsx
git commit -m "feat(kitty-chat): show search unavailable card on gateway error"
```

---

## Task 4: TopBar model fallback indicator

**Files:**
- Modify: `gateway/kitty-chat/src/components/TopBar.tsx`
- Modify: `gateway/kitty-chat/src/app/page.tsx`
- Modify: `gateway/kitty-chat/tests/gatewayIntegration.test.tsx`

When models come from the fallback (gateway unreachable), the model picker button should visually signal this. Add a warning-colored dot that replaces the model-color dot when `modelFromGateway` is false. Keep it subtle — no text change.

- [ ] **Step 1: Write failing test**

Add to `gateway/kitty-chat/tests/gatewayIntegration.test.tsx`:

```typescript
import { TopBar } from '../src/components/TopBar'

describe('TopBar', () => {
  const baseProps = {
    activeModel: { id: 'kitty-default', name: 'default', color: '#4D9FFF', glow: '#4D9FFF99' },
    models: [],
    onSelectModel: () => undefined,
    showModelMenu: false,
    setShowModelMenu: () => undefined,
    isStreaming: false,
    activeChat: null,
  }

  it('shows offline indicator when modelFromGateway is false', () => {
    render(<TopBar {...baseProps} modelFromGateway={false} />)
    expect(screen.getByTitle('Using offline model list')).toBeInTheDocument()
  })

  it('does not show offline indicator when modelFromGateway is true', () => {
    render(<TopBar {...baseProps} modelFromGateway={true} />)
    expect(screen.queryByTitle('Using offline model list')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/Projects/kitty/gateway/kitty-chat && npm test 2>&1 | grep -A 3 "TopBar"
```

Expected: FAIL — `modelFromGateway` prop doesn't exist yet.

- [ ] **Step 3: Add prop to TopBar**

In `gateway/kitty-chat/src/components/TopBar.tsx`, add `modelFromGateway` to the `Props` interface and the function signature:

```typescript
interface Props {
  activeModel: Model
  models: Model[]
  onSelectModel: (m: Model) => void
  showModelMenu: boolean
  setShowModelMenu: (v: boolean) => void
  isStreaming: boolean
  activeChat: Chat | null
  modelFromGateway?: boolean
}

export function TopBar({
  activeModel, models, onSelectModel, showModelMenu, setShowModelMenu,
  isStreaming, activeChat, modelFromGateway = true,
}: Props) {
```

In the model picker button, replace the existing dot span with:

```typescript
          {/* dot — warning color when using offline fallback */}
          <span
            title={modelFromGateway ? undefined : 'Using offline model list'}
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: modelFromGateway ? activeModel.color : 'var(--warning)',
              flexShrink: 0,
              transition: 'background 0.3s',
            }}
          />
```

The existing dot span (around line 86) looks like:
```typescript
<span style={{ width: 7, height: 7, borderRadius: '50%', background: activeModel.color, flexShrink: 0 }} />
```
Replace that entire span with the one above.

- [ ] **Step 4: Pass `modelFromGateway` from `page.tsx`**

In `gateway/kitty-chat/src/app/page.tsx`, find the `<TopBar` usage (around line 325) and add the prop:

```typescript
        <TopBar
          activeModel={activeModel}
          models={availableModels}
          onSelectModel={handleSelectModel}
          showModelMenu={showModelMenu}
          setShowModelMenu={setShowModelMenu}
          isStreaming={isStreaming}
          activeChat={activeChat}
          modelFromGateway={modelGateway.live}
        />
```

- [ ] **Step 5: TypeScript check and tests**

```bash
cd ~/Projects/kitty/gateway/kitty-chat && npx tsc --noEmit && npm test 2>&1 | tail -20
```

Expected: no type errors; all tests pass.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/kitty && git add gateway/kitty-chat/src/components/TopBar.tsx gateway/kitty-chat/src/app/page.tsx gateway/kitty-chat/tests/gatewayIntegration.test.tsx
git commit -m "feat(kitty-chat): TopBar dot turns warning when using offline model fallback"
```

---

## Task 5: BriefPanel loading skeleton

**Files:**
- Modify: `gateway/kitty-chat/src/components/BriefPanel.tsx`
- Modify: `gateway/kitty-chat/src/app/page.tsx`
- Modify: `gateway/kitty-chat/tests/gatewayIntegration.test.tsx`

Currently the brief area shows fallback placeholder cards immediately (before the gateway responds). Add a `loading` prop. When true, render 3 dim skeleton cards instead of the real/fallback cards. This prevents the "flash of fallback content" on fast connections.

- [ ] **Step 1: Write failing test**

Add to `gateway/kitty-chat/tests/gatewayIntegration.test.tsx`:

```typescript
describe('BriefPanel', () => {
  // ... existing tests

  it('shows loading skeleton when loading prop is true', () => {
    render(
      <BriefPanel
        chats={[]}
        onSelectChat={() => undefined}
        onPrompt={() => undefined}
        brief={null}
        loading={true}
      />
    )
    expect(screen.getByRole('status', { name: /loading brief/i })).toBeInTheDocument()
  })

  it('shows fallback cards when loading is false and brief is null', () => {
    render(
      <BriefPanel
        chats={[]}
        onSelectChat={() => undefined}
        onPrompt={() => undefined}
        brief={null}
        loading={false}
      />
    )
    // Fallback card labels from buildCards
    expect(screen.getByText('NEXT UP')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/Projects/kitty/gateway/kitty-chat && npm test 2>&1 | grep -A 5 "BriefPanel"
```

Expected: loading skeleton test FAILS.

- [ ] **Step 3: Add `loading` prop and skeleton to BriefPanel**

In `gateway/kitty-chat/src/components/BriefPanel.tsx`:

Add `loading` to the `Props` interface:

```typescript
interface Props {
  chats: Chat[]
  onSelectChat: (id: string) => void
  onPrompt: (text: string) => void
  brief?: GatewayBrief | null
  loading?: boolean
}
```

Add `loading = false` to the function destructuring:

```typescript
export function BriefPanel({ chats, onSelectChat, onPrompt, brief, loading = false }: Props) {
```

Replace the `{/* SECTION B — Three priority cards */}` section (the `<section style={cardsGridStyle}>` block) with:

```typescript
      {/* SECTION B — Three priority cards (or loading skeleton) */}
      {loading ? (
        <section
          role="status"
          aria-label="loading brief"
          style={cardsGridStyle}
        >
          {[0, 1, 2].map(i => (
            <div
              key={i}
              style={{
                ...cardBaseStyle,
                height: 90,
                opacity: 0.35,
                background: 'var(--surface-low)',
                animation: 'none',
              }}
            />
          ))}
        </section>
      ) : (
        <section style={cardsGridStyle}>
          {cards.map((card) => (
            <PriorityCardItem key={card.label} card={card} />
          ))}
        </section>
      )}
```

- [ ] **Step 4: Pass `loading` from `page.tsx`**

In `gateway/kitty-chat/src/app/page.tsx`, find the `<BriefPanel` usage (around line 395) and add the prop:

```typescript
            <BriefPanel
              chats={chats}
              onSelectChat={id => { setActiveChatId(id) }}
              onPrompt={handlePrompt}
              brief={brief}
              loading={!briefGateway.loaded}
            />
```

- [ ] **Step 5: TypeScript check and all tests**

```bash
cd ~/Projects/kitty/gateway/kitty-chat && npx tsc --noEmit && npm test 2>&1 | tail -20
```

Expected: no type errors; all tests pass.

- [ ] **Step 6: Commit**

```bash
cd ~/Projects/kitty && git add gateway/kitty-chat/src/components/BriefPanel.tsx gateway/kitty-chat/src/app/page.tsx gateway/kitty-chat/tests/gatewayIntegration.test.tsx
git commit -m "feat(kitty-chat): BriefPanel loading skeleton while brief is fetching"
```

---

## Task 6: Final check and handoff update

**Files:**
- Modify: `gateway/kitty-chat/tests/gatewayIntegration.test.tsx` (final review)
- Modify: `SESSION_HANDOFF.md`

- [ ] **Step 1: Run full test suite**

```bash
cd ~/Projects/kitty/gateway/kitty-chat && npm test 2>&1
```

Expected: all tests pass.

- [ ] **Step 2: Run Python tests (don't break gateway)**

```bash
cd ~/Projects/kitty && /opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short 2>&1 | tail -10
```

Expected: 296 passed, 2 deselected (or more).

- [ ] **Step 3: TypeScript full check**

```bash
cd ~/Projects/kitty/gateway/kitty-chat && npx tsc --noEmit 2>&1
```

Expected: no errors.

- [ ] **Step 4: Update SESSION_HANDOFF.md**

Update the "What landed" section of `SESSION_HANDOFF.md` to add:

```markdown
- **UI polish (2026-05-19):** `fetchGatewaySearch` accepts optional `AbortSignal`; search effect debounced 400ms (fires on user-message-count/chat change only, not stream chunks); RightBar shows "Search unavailable" card on gateway error; TopBar model dot turns warning-colored when using offline fallback; BriefPanel shows skeleton during brief load.
```

Update "Updated:" date to `2026-05-19`.

- [ ] **Step 5: Final commit**

```bash
cd ~/Projects/kitty && git add SESSION_HANDOFF.md
git commit -m "docs: update handoff — UI polish complete (debounce, error surfaces, skeleton)"
```

---

## Manual Smoke Checklist (5 min)

After all tasks complete:

1. **Gateway off** → open KittyChat → `modelGateway.loaded=true, live=false` → orange banner shows; model dot turns warning-colored.
2. **Gateway off** → brief skeleton visible briefly then fallback cards render.
3. **Gateway on** → models load from gateway; dot stays model-color.
4. **Send a message** → confirm search fires once (not repeatedly during streaming). Check Network tab: single `/search` request after typing, not one per chunk.
5. **Rapid chat switching** → verify only one search fires per settled chat (prior ones aborted).
6. **Kill gateway mid-session** → send message → search error card appears in RightBar with error text.

---

## Self-Review

**Spec coverage check:**
- [x] Typed fetch results — already done (not in this plan)
- [x] Debounced search + abort — Task 2
- [x] RightBar failure copy — Task 3
- [x] TopBar fallback signal — Task 4
- [x] BriefPanel loading — Task 5
- [x] Tests for 500 path — Task 1 + 3 + 4 + 5

**Placeholder scan:** No TBD/TODO. All code blocks are complete.

**Type consistency:**
- `fetchGatewaySearch(query: string, limit?: number, signal?: AbortSignal)` — used consistently in Task 1, 2
- `modelFromGateway?: boolean` — added to Props in Task 4 and passed from page.tsx in Task 4
- `loading?: boolean` — added to Props in Task 5 and passed from page.tsx in Task 5
- `cardBaseStyle` referenced in Task 5 skeleton — defined at BriefPanel.tsx line 248 ✓
