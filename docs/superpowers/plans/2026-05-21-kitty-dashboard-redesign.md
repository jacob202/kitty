# Kitty Dashboard Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the generic dark chat UI with a dashboard-first personal command center — warm dark base, 5-zone layout (rail + sidebar + center dashboard + right panel + collapsible terminal strip).

**Architecture:** `page.tsx` owns top-level state and passes slices down to the 5 layout zones. Each zone is a focused component that imports only what it needs. The terminal strip wraps the existing chat machinery; the dashboard surfaces data already available from `/brief` and `/mood`.

**Tech Stack:** Next.js 16, React 19, TypeScript, Vitest + @testing-library/react, existing `src/lib/gateway.ts` fetch helpers.

**Spec:** `docs/superpowers/specs/2026-05-21-kitty-chat-ui-redesign.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `src/app/globals.css` | Warm dark tokens, remove radial glow |
| Modify | `src/lib/types.ts` | Add `KittyMode`, `NavTab`, `TerminalState` |
| Create | `src/components/BriefStrip.tsx` | 4-card horizontal brief row |
| Create | `src/components/TodayCompass.tsx` | Priority action banner (full width) |
| Create | `src/components/LoopWatch.tsx` | Stubbed loop-watch panel |
| Create | `src/components/PromptToolkit.tsx` | Quick-launch prompt chips |
| Create | `src/components/InsightFeed.tsx` | Kitty insight cards |
| Create | `src/components/DashboardHome.tsx` | Assembles the center dashboard view |
| Create | `src/components/TerminalStrip.tsx` | Collapsible terminal/chat at bottom |
| Modify | `src/components/TopBar.tsx` | Nav tabs + mode selector, remove ASCII face |
| Modify | `src/components/SessionSidebar.tsx` | Add `collapsed` prop + animation |
| Modify | `src/components/RightPanel.tsx` | Kitty card + schedule + overdue + system |
| Modify | `src/app/page.tsx` | New 5-zone shell, wire all props |
| Extend | `tests/gatewayIntegration.test.tsx` | Assertions for new components |

---

## Task 1: Warm dark tokens

**Files:**
- Modify: `src/app/globals.css`

- [ ] **Step 1: Update canvas/surface tokens**

Replace the top `:root` block (lines that define `--canvas`, `--bg`, `--panel`, `--bg-raised`, `--panel-2`, `--bg-card`, `--recessed`, `--bg-deep`, `--background`) with warmer values. Also kill the `.app-canvas` radial-gradient background and the `--bg-raised` / `--bg-card` aliases. Keep all accent tokens (`--orange`, `--teal`, `--primary`, etc.) unchanged.

Find this block and replace it:
```css
/* Canvas / surfaces */
--canvas:      #0A0C12;
--bg:          #0A0C12;
--panel:       #10141D;
--bg-raised:   #10141D;
--panel-2:     #161B26;
--bg-card:     #161B26;
--recessed:    #0D1017;
--bg-deep:     #0D1017;
```
Replace with:
```css
/* Canvas / surfaces — warm dark */
--canvas:      #0f0f14;
--bg:          #0f0f14;
--panel:       #131318;
--bg-raised:   #131318;
--panel-2:     #1a1a22;
--bg-card:     #1a1a22;
--recessed:    #0b0b10;
--bg-deep:     #0b0b10;
```

Also find and replace the `--background` token:
```css
--background:  #0A0C12;
```
→
```css
--background:  #0f0f14;
```

Also find and replace the `--border` and `--border-dim` tokens:
```css
--border:      #252C3A;
--border-dim:  #1E2436;
```
→
```css
--border:      #222230;
--border-dim:  #1a1a28;
```

- [ ] **Step 2: Remove the radial glows from `.app-canvas`**

Find:
```css
.app-canvas {
  background:
    radial-gradient(circle at 20% 0%, rgba(102, 119, 204, 0.08), transparent 34%),
    radial-gradient(circle at 88% 12%, rgba(184, 156, 255, 0.07), transparent 30%),
    var(--canvas);
}
```
Replace with:
```css
.app-canvas {
  background: var(--canvas);
}
```

- [ ] **Step 3: Add layout dimension tokens for new shell**

At the end of the `:root` block, find the existing layout tokens:
```css
/* Layout */
--rail:     64px;
--sidebar:  248px;
--rightbar: 332px;
```
Replace with:
```css
/* Layout */
--rail:        44px;
--sidebar:     220px;
--sidebar-collapsed: 0px;
--rightbar:    220px;
--topbar:      40px;
--terminal:    130px;
```

- [ ] **Step 4: Verify build still passes**

```bash
cd gateway/kitty-chat && npx tsc --noEmit && npx next build 2>&1 | tail -5
```
Expected: exit 0, "✓ Compiled" or similar.

- [ ] **Step 5: Commit**

```bash
git checkout -b feat/kitty-dashboard-redesign
git add gateway/kitty-chat/src/app/globals.css
git commit -m "feat(ui): warm dark tokens, remove radial glows"
```

---

## Task 2: New TypeScript types

**Files:**
- Modify: `src/lib/types.ts`

- [ ] **Step 1: Add `KittyMode`, `NavTab`, `TerminalState` to types.ts**

Append to the end of `src/lib/types.ts`:
```typescript
export type KittyMode = 'gentle' | 'balanced' | 'blunt' | 'auto'

export type NavTab = 'chats' | 'journal' | 'knowledge' | 'tasks'

export interface TerminalState {
  expanded: boolean
  height: number          // px — 130 collapsed, up to window.innerHeight expanded
  pendingPrompt: string   // set by PromptToolkit chip clicks
}
```

- [ ] **Step 2: Verify types file compiles**

```bash
cd gateway/kitty-chat && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add gateway/kitty-chat/src/lib/types.ts
git commit -m "feat(ui): add KittyMode, NavTab, TerminalState types"
```

---

## Task 3: `BriefStrip` component

**Files:**
- Create: `src/components/BriefStrip.tsx`
- Extend: `tests/gatewayIntegration.test.tsx`

The strip shows 4 static-stub cards. Weather and schedule are hardcoded stubs until dedicated backend endpoints exist. The `intention` field from `GatewayBrief` feeds the NEXT UP card.

- [ ] **Step 1: Write the failing test**

Open `tests/gatewayIntegration.test.tsx`. Add this import at the top:
```typescript
import { BriefStrip } from '../src/components/BriefStrip'
```

Add this test inside the existing `describe` block (or create a new one):
```typescript
describe('BriefStrip', () => {
  it('renders four card labels', () => {
    const { getByText } = render(<BriefStrip intention="standup at 10:30" />)
    expect(getByText('WEATHER')).toBeDefined()
    expect(getByText('NEXT UP')).toBeDefined()
    expect(getByText('OVERDUE')).toBeDefined()
    expect(getByText('FOCUS')).toBeDefined()
  })

  it('shows intention text in NEXT UP card', () => {
    const { getByText } = render(<BriefStrip intention="standup at 10:30" />)
    expect(getByText('standup at 10:30')).toBeDefined()
  })

  it('renders gracefully with no intention', () => {
    const { getByText } = render(<BriefStrip intention={null} />)
    expect(getByText('NEXT UP')).toBeDefined()
  })
})
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd gateway/kitty-chat && npx vitest run tests/gatewayIntegration.test.tsx 2>&1 | tail -15
```
Expected: FAIL — `BriefStrip` not found.

- [ ] **Step 3: Create `src/components/BriefStrip.tsx`**

```typescript
'use client'

interface Props {
  intention: string | null
}

interface BriefCard {
  label: string
  value: string
  sub: string
  color: 'default' | 'orange' | 'red' | 'teal'
}

function cardColor(color: BriefCard['color']): string {
  if (color === 'orange') return 'var(--orange)'
  if (color === 'red')    return '#e74c3c'
  if (color === 'teal')   return 'var(--teal)'
  return 'var(--text)'
}

export function BriefStrip({ intention }: Props) {
  const cards: BriefCard[] = [
    { label: 'WEATHER', value: '—', sub: 'no data', color: 'default' },
    { label: 'NEXT UP', value: intention ?? '—', sub: 'from brief', color: 'orange' },
    { label: 'OVERDUE', value: '—', sub: 'nothing flagged', color: 'red' },
    { label: 'FOCUS',   value: '—', sub: 'see compass', color: 'teal' },
  ]

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: '8px',
    }}>
      {cards.map(card => (
        <div key={card.label} style={{
          background: 'var(--panel)',
          border: '1px solid var(--border)',
          borderRadius: '6px',
          padding: '10px 12px',
        }}>
          <div style={{
            fontSize: '9px',
            letterSpacing: '1.5px',
            color: 'var(--text-muted)',
            fontWeight: 600,
            marginBottom: '5px',
          }}>
            {card.label}
          </div>
          <div style={{
            fontSize: '14px',
            fontWeight: 700,
            color: cardColor(card.color),
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}>
            {card.value}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '3px' }}>
            {card.sub}
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Run test — verify it passes**

```bash
cd gateway/kitty-chat && npx vitest run tests/gatewayIntegration.test.tsx 2>&1 | tail -15
```
Expected: PASS for all BriefStrip tests.

- [ ] **Step 5: Commit**

```bash
git add gateway/kitty-chat/src/components/BriefStrip.tsx \
        gateway/kitty-chat/tests/gatewayIntegration.test.tsx
git commit -m "feat(ui): BriefStrip component — 4-card brief row"
```

---

## Task 4: `TodayCompass` component

**Files:**
- Create: `src/components/TodayCompass.tsx`
- Extend: `tests/gatewayIntegration.test.tsx`

Derives content from `GatewayBrief.intention`. Shows a priority action checkbox + a nudge line. No new backend calls.

- [ ] **Step 1: Write failing test**

Add to `tests/gatewayIntegration.test.tsx`:
```typescript
import { TodayCompass } from '../src/components/TodayCompass'

describe('TodayCompass', () => {
  it('renders the TODAY\'S COMPASS label', () => {
    const { getByText } = render(
      <TodayCompass intention="write the landlord email" nudge={null} onAction={() => {}} />
    )
    expect(getByText("TODAY'S COMPASS")).toBeDefined()
  })

  it('shows the intention as the action', () => {
    const { getByText } = render(
      <TodayCompass intention="write the landlord email" nudge={null} onAction={() => {}} />
    )
    expect(getByText('write the landlord email')).toBeDefined()
  })

  it('shows nudge text when provided', () => {
    const { getByText } = render(
      <TodayCompass intention="x" nudge="You've been in a design loop." onAction={() => {}} />
    )
    expect(getByText("You've been in a design loop.")).toBeDefined()
  })
})
```

- [ ] **Step 2: Run test — verify fails**

```bash
cd gateway/kitty-chat && npx vitest run tests/gatewayIntegration.test.tsx 2>&1 | tail -10
```

- [ ] **Step 3: Create `src/components/TodayCompass.tsx`**

```typescript
'use client'

interface Props {
  intention: string | null
  nudge: string | null
  onAction: (text: string) => void  // called when user clicks "Draft now" — pre-fills terminal
}

export function TodayCompass({ intention, nudge, onAction }: Props) {
  const action = intention ?? 'No priority set — check brief'

  return (
    <div style={{
      background: 'var(--panel)',
      border: '1px solid var(--border)',
      borderRadius: '6px',
      padding: '14px 16px',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '10px',
      }}>
        <div style={{
          fontSize: '9px',
          letterSpacing: '1.5px',
          color: 'var(--text-muted)',
          fontWeight: 600,
        }}>
          TODAY'S COMPASS
        </div>
        <div style={{
          fontSize: '10px',
          color: 'var(--orange)',
          border: '1px solid rgba(232,120,69,0.3)',
          padding: '2px 6px',
          borderRadius: '3px',
        }}>
          1 ACTION
        </div>
      </div>

      <div style={{
        background: 'rgba(78,204,163,0.06)',
        border: '1px solid rgba(78,204,163,0.2)',
        borderRadius: '4px',
        padding: '10px 12px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
        marginBottom: nudge ? '8px' : 0,
      }}>
        <div style={{
          width: '16px',
          height: '16px',
          border: '1px solid var(--teal)',
          borderRadius: '3px',
          flexShrink: 0,
          marginTop: '1px',
          cursor: 'pointer',
        }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '13px', color: 'var(--text)', fontWeight: 500 }}>
            {action}
          </div>
          {intention && (
            <button
              onClick={() => onAction(action)}
              style={{
                marginTop: '6px',
                fontSize: '11px',
                color: 'var(--orange)',
                background: 'none',
                border: 'none',
                padding: 0,
                cursor: 'pointer',
              }}
            >
              → Kitty can draft this
            </button>
          )}
        </div>
      </div>

      {nudge && (
        <div style={{
          fontSize: '11px',
          color: 'var(--text-muted)',
          fontStyle: 'italic',
          paddingTop: '8px',
          borderTop: '1px solid var(--border-dim)',
        }}>
          {nudge}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run test — verify passes**

```bash
cd gateway/kitty-chat && npx vitest run tests/gatewayIntegration.test.tsx 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
git add gateway/kitty-chat/src/components/TodayCompass.tsx \
        gateway/kitty-chat/tests/gatewayIntegration.test.tsx
git commit -m "feat(ui): TodayCompass — priority action banner"
```

---

## Task 5: `LoopWatch`, `PromptToolkit`, `InsightFeed` (leaf components — no tests needed for stubs)

**Files:**
- Create: `src/components/LoopWatch.tsx`
- Create: `src/components/PromptToolkit.tsx`
- Create: `src/components/InsightFeed.tsx`

- [ ] **Step 1: Create `src/components/LoopWatch.tsx`**

```typescript
'use client'

export function LoopWatch() {
  return (
    <div style={{
      background: 'var(--panel)',
      border: '1px solid var(--border)',
      borderRadius: '6px',
      padding: '14px 16px',
      height: '100%',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '10px',
      }}>
        <div style={{
          fontSize: '9px',
          letterSpacing: '1.5px',
          color: 'var(--text-muted)',
          fontWeight: 600,
        }}>
          LOOP WATCH
        </div>
        <div style={{
          fontSize: '10px',
          color: 'var(--text-muted)',
          border: '1px solid var(--border)',
          padding: '2px 6px',
          borderRadius: '3px',
        }}>
          WATCHING
        </div>
      </div>
      <div style={{
        fontSize: '12px',
        color: 'var(--text-muted)',
        fontStyle: 'italic',
        lineHeight: '1.5',
      }}>
        Watching for repeated queries across sessions. Patterns will appear here once enough history exists.
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create `src/components/PromptToolkit.tsx`**

```typescript
'use client'

const PROMPTS: { icon: string; label: string; text: string }[] = [
  { icon: '⚡', label: "I'm stuck",         text: "I'm stuck and not sure what to do next. Help me figure out the most important thing right now." },
  { icon: '🛒', label: 'Buying something',  text: "I'm about to buy something. Walk me through a quick 5-step check before I spend the money." },
  { icon: '🎯', label: 'Force a decision',  text: "I need to make a decision and I keep going in circles. Give me a forced choice with clear next steps." },
  { icon: '🪞', label: 'Call me out',       text: "I want you to be direct: am I solving the wrong problem right now? What am I avoiding?" },
  { icon: '🧠', label: 'Brain dump',        text: "I need to brain dump. I'll write whatever's on my mind and you help me sort it into categories." },
  { icon: '📋', label: 'Triage my tasks',   text: "Look at my current tasks and tell me what to do first, what to drop, and what to schedule." },
]

interface Props {
  onSelect: (text: string) => void
}

export function PromptToolkit({ onSelect }: Props) {
  return (
    <div style={{
      background: 'var(--panel)',
      border: '1px solid var(--border)',
      borderRadius: '6px',
      padding: '14px 16px',
    }}>
      <div style={{
        fontSize: '9px',
        letterSpacing: '1.5px',
        color: 'var(--text-muted)',
        fontWeight: 600,
        marginBottom: '10px',
      }}>
        PROMPT TOOLKIT
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '7px' }}>
        {PROMPTS.map(p => (
          <button
            key={p.label}
            onClick={() => onSelect(p.text)}
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: '4px',
              padding: '6px 11px',
              fontSize: '11px',
              color: 'var(--text-dim)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              transition: 'border-color 0.15s, color 0.15s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(232,120,69,0.5)'
              ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--orange)'
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--border)'
              ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-dim)'
            }}
          >
            <span>{p.icon}</span>
            <span>{p.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `src/components/InsightFeed.tsx`**

`memory_snippet` from GatewayBrief is used as the first insight. Second insight is static if no brief.

```typescript
'use client'

interface Props {
  memorySnippet: string | null
  onFollowUp: (text: string) => void
}

export function InsightFeed({ memorySnippet, onFollowUp }: Props) {
  return (
    <div style={{
      background: 'var(--panel)',
      border: '1px solid var(--border)',
      borderRadius: '6px',
      padding: '14px 16px',
    }}>
      <div style={{
        fontSize: '9px',
        letterSpacing: '1.5px',
        color: 'var(--text-muted)',
        fontWeight: 600,
        marginBottom: '10px',
      }}>
        INSIGHT
      </div>

      {memorySnippet ? (
        <div>
          <div style={{
            fontSize: '12px',
            color: 'var(--text-dim)',
            lineHeight: '1.6',
            fontStyle: 'italic',
          }}>
            "{memorySnippet}"
          </div>
          <button
            onClick={() => onFollowUp('What makes you say that?')}
            style={{
              marginTop: '6px',
              fontSize: '11px',
              color: 'var(--teal)',
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
            }}
          >
            → What makes you say that?
          </button>
        </div>
      ) : (
        <div style={{
          fontSize: '12px',
          color: 'var(--text-muted)',
          fontStyle: 'italic',
        }}>
          No insights yet — start a session to generate observations.
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Verify TypeScript is clean**

```bash
cd gateway/kitty-chat && npx tsc --noEmit 2>&1 | head -20
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add gateway/kitty-chat/src/components/LoopWatch.tsx \
        gateway/kitty-chat/src/components/PromptToolkit.tsx \
        gateway/kitty-chat/src/components/InsightFeed.tsx
git commit -m "feat(ui): LoopWatch (stub), PromptToolkit, InsightFeed"
```

---

## Task 6: `DashboardHome` — center assembly

**Files:**
- Create: `src/components/DashboardHome.tsx`

Assembles Tasks 3–5 components into the scrollable center column.

- [ ] **Step 1: Create `src/components/DashboardHome.tsx`**

```typescript
'use client'

import { BriefStrip } from './BriefStrip'
import { TodayCompass } from './TodayCompass'
import { LoopWatch } from './LoopWatch'
import { PromptToolkit } from './PromptToolkit'
import { InsightFeed } from './InsightFeed'
import type { GatewayBrief } from '@/lib/gateway'

interface Props {
  brief: GatewayBrief | null
  briefLoading: boolean
  onPromptSelect: (text: string) => void  // opens terminal + pre-fills text
}

function timeOfDay(): string {
  const h = new Date().getHours()
  if (h < 12) return 'morning'
  if (h < 17) return 'afternoon'
  return 'evening'
}

export function DashboardHome({ brief, briefLoading, onPromptSelect }: Props) {
  const dateStr = new Date().toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric',
  })

  return (
    <div style={{
      flex: 1,
      overflowY: 'auto',
      padding: '20px',
      display: 'flex',
      flexDirection: 'column',
      gap: '14px',
    }}>
      {/* Greeting */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        <div style={{
          width: '44px',
          height: '44px',
          background: 'rgba(232,120,69,0.12)',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '24px',
          flexShrink: 0,
        }}>
          🐱
        </div>
        <div>
          <h1 style={{
            fontSize: '22px',
            fontWeight: 700,
            color: 'var(--text)',
            lineHeight: 1.2,
          }}>
            {timeOfDay()}, jacob{' '}
            <span style={{ color: 'var(--orange)' }}>:3</span>
          </h1>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
            {dateStr} · {briefLoading ? 'loading brief…' : brief ? 'brief ready' : 'gateway offline'}
          </div>
        </div>
      </div>

      {/* Brief strip */}
      <BriefStrip intention={brief?.intention ?? null} />

      {/* Today's Compass — full width */}
      <TodayCompass
        intention={brief?.intention ?? null}
        nudge={null}
        onAction={onPromptSelect}
      />

      {/* 2-col grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <PromptToolkit onSelect={onPromptSelect} />
        <LoopWatch />
        <InsightFeed
          memorySnippet={brief?.memory_snippet ?? null}
          onFollowUp={onPromptSelect}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd gateway/kitty-chat && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
git add gateway/kitty-chat/src/components/DashboardHome.tsx
git commit -m "feat(ui): DashboardHome — assembles center dashboard view"
```

---

## Task 7: `TerminalStrip` — collapsible terminal/chat

**Files:**
- Create: `src/components/TerminalStrip.tsx`

The terminal is 130px by default. Clicking `⤢` or dragging the handle expands to fill the remaining height. When expanded, a scrollable log of `Message[]` is shown above the input bar. Boot log (SYS lines) is static on mount.

- [ ] **Step 1: Create `src/components/TerminalStrip.tsx`**

```typescript
'use client'

import { useRef, useEffect, useState, useCallback } from 'react'
import type { Message } from '@/lib/types'

interface LogLine {
  time: string
  tag: 'SYS' | 'KTY' | 'USR'
  text: string
}

interface Props {
  messages: Message[]
  pendingPrompt: string
  onPendingPromptClear: () => void
  onSend: (text: string) => void
  isStreaming: boolean
  contextCount: number
  expanded: boolean
  onExpandToggle: () => void
}

function nowHHMMSS(): string {
  return new Date().toTimeString().slice(0, 8)
}

const BOOT_LOG: LogLine[] = [
  { time: nowHHMMSS(), tag: 'SYS', text: 'Kitty starting up…' },
  { time: nowHHMMSS(), tag: 'SYS', text: 'Gateway OK · memory loaded · models ready' },
]

export function TerminalStrip({
  messages,
  pendingPrompt,
  onPendingPromptClear,
  onSend,
  isStreaming,
  contextCount,
  expanded,
  onExpandToggle,
}: Props) {
  const [input, setInput] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const logRef = useRef<HTMLDivElement>(null)

  // Pre-fill input when a prompt chip fires
  useEffect(() => {
    if (pendingPrompt) {
      setInput(pendingPrompt)
      onPendingPromptClear()
      inputRef.current?.focus()
    }
  }, [pendingPrompt, onPendingPromptClear])

  // Auto-scroll log to bottom
  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight)
  }, [messages, expanded])

  const handleSend = useCallback(() => {
    const text = input.trim()
    if (!text || isStreaming) return
    onSend(text)
    setInput('')
  }, [input, isStreaming, onSend])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
    if (e.key === 'Escape' && expanded) onExpandToggle()
  }, [handleSend, expanded, onExpandToggle])

  // Map Message[] to LogLine[] for display
  const logLines: LogLine[] = [
    ...BOOT_LOG,
    ...messages.map(m => ({
      time: new Date(m.timestamp).toTimeString().slice(0, 8),
      tag: (m.role === 'user' ? 'USR' : 'KTY') as LogLine['tag'],
      text: m.content,
    })),
  ]

  const tagColor = (tag: LogLine['tag']) => {
    if (tag === 'SYS') return 'var(--teal)'
    if (tag === 'KTY') return 'var(--orange)'
    return 'var(--text-muted)'
  }

  const collapsedHeight = 130
  const height = expanded ? '100%' : `${collapsedHeight}px`

  return (
    <div style={{
      height,
      background: '#080810',
      borderTop: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      transition: 'height 0.2s ease',
    }}>
      {/* Header bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '5px 14px',
        borderBottom: '1px solid var(--border-dim)',
        flexShrink: 0,
        cursor: 'ns-resize',
      }}>
        <span style={{
          fontSize: '10px',
          color: 'var(--text-muted)',
          letterSpacing: '1.5px',
          fontFamily: 'var(--font-mono)',
        }}>
          TERMINAL // KTY
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            width: '6px', height: '6px', borderRadius: '50%',
            background: 'var(--teal)', display: 'inline-block',
          }} />
          <span style={{ fontSize: '10px', color: 'var(--teal)' }}>
            {isStreaming ? 'PROCESSING' : 'ACTIVE'}
          </span>
          <button
            onClick={onExpandToggle}
            style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1 }}
            title={expanded ? 'Collapse terminal' : 'Expand terminal'}
          >
            {expanded ? '✕' : '⤢'}
          </button>
        </div>
      </div>

      {/* Log */}
      <div
        ref={logRef}
        style={{
          flex: 1,
          overflow: 'hidden',
          overflowY: expanded ? 'auto' : 'hidden',
          padding: '6px 14px',
          display: 'flex',
          flexDirection: 'column',
          gap: '3px',
        }}
      >
        {logLines.slice(expanded ? 0 : -3).map((line, i) => (
          <div key={i} style={{ display: 'flex', gap: '10px', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
            <span style={{ color: 'var(--text-faint)', flexShrink: 0 }}>[{line.time}]</span>
            <span style={{ color: tagColor(line.tag), flexShrink: 0 }}>[{line.tag}]</span>
            <span style={{ color: line.tag === 'KTY' ? 'var(--text)' : 'var(--text-muted)', wordBreak: 'break-word' }}>
              {line.text}
            </span>
          </div>
        ))}
      </div>

      {/* Input bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '6px 14px',
        borderTop: '1px solid var(--border-dim)',
        background: '#0a0a14',
        flexShrink: 0,
      }}>
        <span style={{ color: 'var(--orange)', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>$</span>
        <input
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onClick={() => { if (!expanded) onExpandToggle() }}
          placeholder="Awaiting command or query…"
          style={{
            flex: 1,
            background: 'none',
            border: 'none',
            outline: 'none',
            color: 'var(--text)',
            fontFamily: 'var(--font-mono)',
            fontSize: '12px',
          }}
        />
        {contextCount > 0 && (
          <span style={{
            background: 'var(--bg-card)',
            color: 'var(--text-muted)',
            fontSize: '10px',
            padding: '3px 7px',
            borderRadius: '3px',
            fontFamily: 'var(--font-mono)',
          }}>
            /context · {contextCount}
          </span>
        )}
        <button
          onClick={handleSend}
          disabled={isStreaming || !input.trim()}
          style={{
            background: isStreaming || !input.trim() ? 'var(--border)' : 'var(--orange)',
            color: '#fff',
            border: 'none',
            padding: '4px 12px',
            borderRadius: '3px',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            cursor: isStreaming || !input.trim() ? 'default' : 'pointer',
            transition: 'background 0.15s',
          }}
        >
          send ↑
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd gateway/kitty-chat && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
git add gateway/kitty-chat/src/components/TerminalStrip.tsx
git commit -m "feat(ui): TerminalStrip — collapsible terminal/chat dock"
```

---

## Task 8: `TopBar` — tabs + mode selector

**Files:**
- Modify: `src/components/TopBar.tsx`

Rewrite TopBar to show: logo + nav tabs (Chats/Journal/Knowledge/Tasks with badges) + GENTLE/BALANCED/BLUNT/AUTO mode group on the right. Remove the ASCII face and model dropdown (model display moves to right panel).

- [ ] **Step 1: Read the current TopBar.tsx**

```bash
cat gateway/kitty-chat/src/components/TopBar.tsx
```
Note: identify what props it currently accepts so you know what to change in `page.tsx` after this task.

- [ ] **Step 2: Rewrite `src/components/TopBar.tsx`**

```typescript
'use client'

import type { NavTab, KittyMode } from '@/lib/types'

interface Props {
  activeTab: NavTab
  onTabChange: (tab: NavTab) => void
  kittyMode: KittyMode
  onModeChange: (mode: KittyMode) => void
  chatCount: number
  taskCount: number
  kittyOnline: boolean
}

const TABS: { id: NavTab; label: string; count?: keyof Pick<Props, 'chatCount' | 'taskCount'> }[] = [
  { id: 'chats',     label: 'chats',     count: 'chatCount' },
  { id: 'journal',   label: 'journal' },
  { id: 'knowledge', label: 'knowledge' },
  { id: 'tasks',     label: 'tasks',     count: 'taskCount' },
]

const MODES: { id: KittyMode; label: string }[] = [
  { id: 'gentle',   label: 'GENTLE' },
  { id: 'balanced', label: 'BALANCED' },
  { id: 'blunt',    label: 'BLUNT' },
  { id: 'auto',     label: 'AUTO' },
]

export function TopBar({
  activeTab, onTabChange,
  kittyMode, onModeChange,
  chatCount, taskCount,
  kittyOnline,
}: Props) {
  const counts: Record<string, number> = { chatCount, taskCount }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      height: 'var(--topbar)',
      background: 'var(--panel)',
      borderBottom: '1px solid var(--border)',
      padding: '0 12px',
      flexShrink: 0,
    }}>
      {/* Logo */}
      <span style={{ fontSize: '20px', marginRight: '12px' }}>🐱</span>

      {/* Nav tabs */}
      <div style={{ display: 'flex', height: '100%' }}>
        {TABS.map(tab => {
          const count = tab.count ? counts[tab.count] : 0
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              style={{
                padding: '0 16px',
                height: '100%',
                background: 'none',
                border: 'none',
                borderBottom: isActive ? '2px solid var(--orange)' : '2px solid transparent',
                color: isActive ? 'var(--orange)' : 'var(--text-muted)',
                fontSize: '12px',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'color 0.15s',
              }}
            >
              {tab.label}
              {count > 0 && (
                <span style={{
                  background: 'rgba(232,120,69,0.15)',
                  color: 'var(--orange)',
                  fontSize: '10px',
                  padding: '1px 5px',
                  borderRadius: '3px',
                }}>
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      <div style={{ flex: 1 }} />

      {/* Kitty status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginRight: '12px' }}>
        <span style={{
          width: '7px', height: '7px', borderRadius: '50%',
          background: kittyOnline ? 'var(--teal)' : '#555',
          display: 'inline-block',
        }} />
        <span style={{ fontSize: '11px', color: kittyOnline ? 'var(--teal)' : 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.5px' }}>
          {kittyOnline ? 'KITTY ACTIVE' : 'OFFLINE'}
        </span>
      </div>

      {/* Mode selector */}
      <div style={{
        display: 'flex',
        background: 'var(--bg-card)',
        borderRadius: '4px',
        overflow: 'hidden',
        border: '1px solid var(--border)',
      }}>
        {MODES.map(mode => (
          <button
            key={mode.id}
            onClick={() => onModeChange(mode.id)}
            style={{
              padding: '4px 9px',
              fontSize: '10px',
              letterSpacing: '0.8px',
              fontWeight: 600,
              border: 'none',
              background: kittyMode === mode.id ? 'var(--orange)' : 'transparent',
              color: kittyMode === mode.id ? '#fff' : 'var(--text-muted)',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {mode.label}
          </button>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd gateway/kitty-chat && npx tsc --noEmit 2>&1 | head -20
```
If there are errors about TopBar props in `page.tsx`, that's expected — you'll fix them in Task 10.

- [ ] **Step 4: Commit**

```bash
git add gateway/kitty-chat/src/components/TopBar.tsx
git commit -m "feat(ui): TopBar — nav tabs + mode selector, remove ASCII face"
```

---

## Task 9: `SessionSidebar` — add collapse

**Files:**
- Modify: `src/components/SessionSidebar.tsx`

- [ ] **Step 1: Read the current SessionSidebar.tsx**

```bash
cat gateway/kitty-chat/src/components/SessionSidebar.tsx
```

- [ ] **Step 2: Add `collapsed` prop and animate width**

Find the outermost container `div` in `SessionSidebar` and add `collapsed` to the props interface and the width style:

At the top of the component, add `collapsed` to whatever Props interface exists:
```typescript
// Add to the existing Props interface:
collapsed: boolean
```

In the outermost wrapper `div`, add:
```typescript
style={{
  width: collapsed ? '0px' : 'var(--sidebar)',
  overflow: 'hidden',
  transition: 'width 0.2s ease',
  flexShrink: 0,
  // ... keep all existing styles
}}
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd gateway/kitty-chat && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 4: Commit**

```bash
git add gateway/kitty-chat/src/components/SessionSidebar.tsx
git commit -m "feat(ui): SessionSidebar — collapse/expand with CSS transition"
```

---

## Task 10: `RightPanel` — Kitty card + schedule + overdue + system

**Files:**
- Modify: `src/components/RightPanel.tsx`

- [ ] **Step 1: Read the current RightPanel.tsx**

```bash
cat gateway/kitty-chat/src/components/RightPanel.tsx
```

- [ ] **Step 2: Rewrite RightPanel**

Replace the entire file content with:

```typescript
'use client'

import type { KittyMode } from '@/lib/types'
import type { GatewayBrief } from '@/lib/gateway'

interface Props {
  brief: GatewayBrief | null
  kittyMode: KittyMode
  gatewayLive: boolean
  modelName: string
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ padding: '12px', borderBottom: '1px solid var(--border-dim)' }}>
      <div style={{
        fontSize: '9px',
        letterSpacing: '1.5px',
        color: 'var(--text-muted)',
        fontWeight: 600,
        marginBottom: '8px',
      }}>
        {label}
      </div>
      {children}
    </div>
  )
}

export function RightPanel({ brief, kittyMode, gatewayLive, modelName }: Props) {
  const dateStr = new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })

  return (
    <div style={{
      width: 'var(--rightbar)',
      background: 'var(--panel)',
      borderLeft: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      overflowY: 'auto',
      flexShrink: 0,
    }}>
      {/* Date header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '12px',
        borderBottom: '1px solid var(--border)',
      }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>today</span>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{dateStr}</span>
      </div>

      {/* Kitty card */}
      <Section label="KITTY">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '28px', height: '28px',
            background: 'rgba(232,120,69,0.12)',
            borderRadius: '5px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '16px',
          }}>🐱</div>
          <div>
            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)' }}>
              <span style={{
                width: '6px', height: '6px', borderRadius: '50%',
                background: gatewayLive ? 'var(--teal)' : '#555',
                display: 'inline-block', marginRight: '5px',
              }} />
              {gatewayLive ? 'Active' : 'Offline'}
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
              {kittyMode} · {modelName}
            </div>
          </div>
        </div>
      </Section>

      {/* Schedule stub — will be populated from calendar integration later */}
      <Section label="SCHEDULE">
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
          No calendar connected
        </div>
      </Section>

      {/* Overdue — derived from brief if available */}
      <Section label="OVERDUE">
        {brief?.intention ? (
          <div>
            <div style={{ fontSize: '12px', color: 'var(--text)', lineHeight: 1.4 }}>
              {brief.intention}
            </div>
          </div>
        ) : (
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
            Nothing flagged
          </div>
        )}
      </Section>

      {/* System */}
      <Section label="SYSTEM">
        {[
          { label: 'gateway', value: gatewayLive ? 'OK' : 'offline', ok: gatewayLive },
          { label: 'model', value: modelName, ok: true },
        ].map(row => (
          <div key={row.label} style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: '5px',
            fontSize: '12px',
          }}>
            <span style={{ color: 'var(--text-muted)' }}>{row.label}</span>
            <span style={{ color: row.ok ? 'var(--teal)' : '#e74c3c' }}>{row.value}</span>
          </div>
        ))}
      </Section>
    </div>
  )
}
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd gateway/kitty-chat && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 4: Commit**

```bash
git add gateway/kitty-chat/src/components/RightPanel.tsx
git commit -m "feat(ui): RightPanel — Kitty status, schedule stub, system health"
```

---

## Task 11: Wire everything in `page.tsx`

**Files:**
- Modify: `src/app/page.tsx`

This is the final assembly task. Read the current `page.tsx` carefully before making changes — preserve the chat/streaming logic, only change the render structure.

- [ ] **Step 1: Read the current page.tsx completely**

```bash
cat gateway/kitty-chat/src/app/page.tsx
```

- [ ] **Step 2: Add new state + imports to page.tsx**

At the top of the imports, add:
```typescript
import { DashboardHome } from '@/components/DashboardHome'
import { TerminalStrip } from '@/components/TerminalStrip'
import { TopBar } from '@/components/TopBar'
import type { KittyMode, NavTab, TerminalState } from '@/lib/types'
```

Inside `KittyChat()`, add these new state declarations after the existing state block:
```typescript
const [kittyMode, setKittyMode] = useState<KittyMode>(() => {
  if (typeof window !== 'undefined') {
    return (localStorage.getItem('kitty-mode') as KittyMode) ?? 'blunt'
  }
  return 'blunt'
})
const [activeTab, setActiveTab] = useState<NavTab>('chats')
const [terminalExpanded, setTerminalExpanded] = useState(false)
const [pendingPrompt, setPendingPrompt] = useState('')
const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
```

Persist kittyMode to localStorage by adding this effect after the state declarations:
```typescript
useEffect(() => {
  localStorage.setItem('kitty-mode', kittyMode)
}, [kittyMode])
```

- [ ] **Step 3: Replace the render return with the 5-zone layout**

Find the `return (` in `KittyChat` and replace the entire JSX tree with:

```typescript
return (
  <div className="app-canvas" style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
    <TopBar
      activeTab={activeTab}
      onTabChange={setActiveTab}
      kittyMode={kittyMode}
      onModeChange={setKittyMode}
      chatCount={chats.length}
      taskCount={0}
      kittyOnline={modelGateway.live}
    />

    <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
      {/* Icon rail */}
      <div style={{
        width: 'var(--rail)',
        background: 'var(--recessed)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '10px 0',
        gap: '10px',
        flexShrink: 0,
      }}>
        {[
          { icon: '📋', tab: 'chats' as NavTab },
          { icon: '🔍', tab: 'knowledge' as NavTab },
          { icon: '📓', tab: 'journal' as NavTab },
          { icon: '✓',  tab: 'tasks' as NavTab },
        ].map(({ icon, tab }) => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setSidebarCollapsed(false) }}
            style={{
              width: '30px', height: '30px', borderRadius: '5px',
              background: activeTab === tab ? 'rgba(232,120,69,0.12)' : 'transparent',
              border: activeTab === tab ? '1px solid rgba(232,120,69,0.3)' : '1px solid transparent',
              fontSize: '14px', color: activeTab === tab ? 'var(--orange)' : 'var(--text-faint)',
              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            {icon}
          </button>
        ))}
      </div>

      {/* Session sidebar */}
      <SessionSidebar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={setActiveChatId}
        onNewChat={() => {
          const chat = makeChat(COLOR_CYCLE[chats.length % COLOR_CYCLE.length])
          setChats(prev => [chat, ...prev])
          setActiveChatId(chat.id)
        }}
        collapsed={sidebarCollapsed}
      />

      {/* Center — dashboard or tab stub */}
      {activeTab === 'chats' ? (
        <DashboardHome
          brief={brief}
          briefLoading={!briefGateway.loaded}
          onPromptSelect={(text) => {
            setPendingPrompt(text)
            setTerminalExpanded(true)
          }}
        />
      ) : (
        <div style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--text-muted)', fontSize: '13px',
        }}>
          {activeTab} — coming soon
        </div>
      )}

      {/* Right panel */}
      <RightPanel
        brief={brief}
        kittyMode={kittyMode}
        gatewayLive={modelGateway.live}
        modelName={activeModel.name}
      />
    </div>

    {/* Terminal strip */}
    <TerminalStrip
      messages={chats.find(c => c.id === activeChatId)?.messages ?? []}
      pendingPrompt={pendingPrompt}
      onPendingPromptClear={() => setPendingPrompt('')}
      onSend={(text) => {
        // Reuse existing send logic — find active chat and call handleSend
        setInput(text)
        // trigger send via the existing isStreaming/abortRef machinery
        handleSend(text)
      }}
      isStreaming={isStreaming}
      contextCount={tokenCount}
      expanded={terminalExpanded}
      onExpandToggle={() => setTerminalExpanded(v => !v)}
    />
  </div>
)
```

> **Note:** The existing `page.tsx` has a `handleSend` function (or similar). Adapt the `onSend` call to match whatever the existing function signature is. If the function requires `input` state to be set first, set it and then call the function.

- [ ] **Step 4: Remove any imports now unused by the new render**

Run TypeScript to see what's unused:
```bash
cd gateway/kitty-chat && npx tsc --noEmit 2>&1
```
Remove any import lines flagged as unused. Common ones: `BriefPanel`, `Rail`, `RightBar` (old component name).

- [ ] **Step 5: Run full test suite**

```bash
cd gateway/kitty-chat && npx vitest run 2>&1 | tail -20
```
Expected: all tests pass. If tests reference old component props (e.g., old TopBar props), update them.

- [ ] **Step 6: Run build**

```bash
cd gateway/kitty-chat && npx next build 2>&1 | tail -10
```
Expected: `✓ Compiled` with exit 0.

- [ ] **Step 7: Start dev server and do visual smoke test**

```bash
cd gateway/kitty-chat && npm run dev -- --port 4000
```

Open `http://localhost:4000`. Verify:
- Background is warm dark (brownish-black), not cool blue
- Top bar shows: 🐱 · chats · journal · knowledge · tasks · KITTY ACTIVE · GENTLE/BALANCED/**BLUNT**/AUTO
- Left rail shows 4 icons
- Session sidebar shows with sessions
- Center shows dashboard: greeting, 4 brief cards, compass, loop watch, prompt toolkit, insight feed
- Bottom terminal strip is visible at ~130px
- Clicking a prompt chip fills the terminal input and expands it
- Clicking ⤢ expands terminal to full height
- Mode selector persists on refresh (check localStorage)

- [ ] **Step 8: Commit**

```bash
git add gateway/kitty-chat/src/app/page.tsx
git commit -m "feat(ui): wire 5-zone dashboard layout in page.tsx"
```

---

## Task 12: Final — update integration tests

**Files:**
- Modify: `tests/gatewayIntegration.test.tsx`

- [ ] **Step 1: Update the integration test to match new TopBar props**

Open `tests/gatewayIntegration.test.tsx`. Find any renders of `<TopBar>` or assertions that check for the old TopBar content (ASCII face, old model pill). Update them to match the new props:

```typescript
// Old pattern (remove/update):
// render(<TopBar activeModel={...} ... />)

// New pattern:
render(
  <TopBar
    activeTab="chats"
    onTabChange={() => {}}
    kittyMode="blunt"
    onModeChange={() => {}}
    chatCount={0}
    taskCount={0}
    kittyOnline={true}
  />
)
```

- [ ] **Step 2: Run tests**

```bash
cd gateway/kitty-chat && npx vitest run 2>&1 | tail -20
```
Expected: all pass.

- [ ] **Step 3: Final build verification**

```bash
cd gateway/kitty-chat && npx next build 2>&1 | tail -5
```

- [ ] **Step 4: Final commit**

```bash
git add gateway/kitty-chat/tests/gatewayIntegration.test.tsx
git commit -m "test(ui): update integration tests for new TopBar + dashboard layout"
```

---

## Phase 2 backlog (not in this plan)

These are explicitly out of scope. Do not start them:

- `GET /loops` endpoint — memory graph pattern detection for LoopWatch
- Insight generation — periodic Kitty observations stored to memory
- Calendar integration — SCHEDULE section in RightPanel
- Weather widget — WEATHER card in BriefStrip
- Sidebar resize drag handle
- Mobile/responsive layout
- Journal, Knowledge, Tasks tab views (stubs only in this plan)
