import { render, screen, cleanup } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi, describe, expect, it, beforeEach, afterEach } from 'vitest'

import { RightPanel } from '../src/components/RightPanel'
import { TopBar } from '../src/components/TopBar'
import {
  buildGatewayModels,
  fetchGatewayBrief,
  fetchGatewaySearch,
  fetchStateChanges,
  fetchStateNow,
  summarizeGatewaySearch,
} from '../src/lib/gateway'

function renderWithQueryClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>)
}

describe('gateway integration helpers', () => {
  it('buildGatewayModels prefers live gateway ids and keeps a fallback', () => {
    const models = buildGatewayModels(['kitty-smart', 'custom-model'])

    expect(models.map(model => model.id)).toEqual(['kitty-smart', 'custom-model'])
    expect(models[0].name).toBe('smart')
    expect(models[1].name).toBe('custom-model')
  })

  it('summarizeGatewaySearch returns the first non-empty result from each section', () => {
    const summary = summarizeGatewaySearch({
      query: 'honda',
      memories: [
        {
          kind: 'memory',
          source: 'memory-a',
          title: 'Memory A',
          text: 'remember this',
          score: 1,
        },
      ],
      knowledge: [
        {
          kind: 'knowledge',
          source: 'kb.md',
          title: 'KB note',
          text: 'facts',
          score: 0.9,
        },
      ],
      journal: [],
      todos: [
        {
          kind: 'todo',
          source: 'todo',
          title: 'Call shop',
          text: 'call shop',
          score: null,
        },
      ],
    })

    expect(summary.query).toBe('honda')
    expect(summary.sections.memories[0]).toContain('remember this')
    expect(summary.sections.knowledge[0]).toContain('KB note')
    expect(summary.sections.todos[0]).toContain('Call shop')
  })
})

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
    vi.mocked(global.fetch).mockImplementation((_url, init) => {
      const signal = init?.signal as AbortSignal | undefined
      return new Promise((_resolve, reject) => {
        function rejectAbort() {
          const err = new Error('The operation was aborted')
          err.name = 'AbortError'
          reject(err)
        }
        if (signal?.aborted) {
          rejectAbort()
        } else {
          signal?.addEventListener('abort', rejectAbort, { once: true })
        }
      })
    })

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

describe('fetchGatewayBrief timeout budget', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn())
    vi.stubGlobal('window', {
      setTimeout: globalThis.setTimeout,
      clearTimeout: globalThis.clearTimeout,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('waits long enough for the gateway cold-cache fallback path', async () => {
    vi.mocked(global.fetch).mockImplementation((_url, init) => {
      const signal = init?.signal as AbortSignal | undefined
      return new Promise((resolve, reject) => {
        const rejectAbort = () => {
          const err = new Error('The operation was aborted')
          err.name = 'AbortError'
          reject(err)
        }
        if (signal?.aborted) {
          rejectAbort()
          return
        }
        signal?.addEventListener('abort', rejectAbort, { once: true })
        setTimeout(() => {
          resolve(
            Response.json({
              date: '2026-07-08',
              headlines: [],
              memory_snippet: '',
              intention: 'Move the real project forward.',
              generated_at: '2026-07-08T21:00:00Z',
              notification_sent: false,
              error: null,
            })
          )
        }, 2100)
      })
    })

    const pending = fetchGatewayBrief()
    await vi.advanceTimersByTimeAsync(2100)

    const result = await pending
    expect(result.fromLiveGateway).toBe(true)
    expect(result.error).toBeNull()
    expect(result.brief?.intention).toBe('Move the real project forward.')
  })
})

describe('state endpoint timeout budget', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn())
    vi.stubGlobal('localStorage', { getItem: vi.fn(() => null) })
    vi.stubGlobal('window', {
      setTimeout: globalThis.setTimeout,
      clearTimeout: globalThis.clearTimeout,
      dispatchEvent: vi.fn(),
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('waits for state endpoints that include slow calendar checks', async () => {
    vi.mocked(global.fetch).mockImplementation((url, init) => {
      const signal = init?.signal as AbortSignal | undefined
      return new Promise((resolve, reject) => {
        const rejectAbort = () => {
          const err = new Error('The operation was aborted')
          err.name = 'AbortError'
          reject(err)
        }
        if (signal?.aborted) {
          rejectAbort()
          return
        }
        signal?.addEventListener('abort', rejectAbort, { once: true })
        setTimeout(() => {
          if (String(url).endsWith('/state/changes')) {
            resolve(Response.json({ baseline_ts: null, current_ts: 1, changes: [], new_signals: [] }))
            return
          }
          resolve(Response.json({ ts: 1, sections: { calendar: { ok: false, error: 'timed out after 3.0s' } } }))
        }, 3100)
      })
    })

    const changes = fetchStateChanges()
    const now = fetchStateNow()
    await vi.advanceTimersByTimeAsync(3100)

    await expect(changes).resolves.toMatchObject({ current_ts: 1 })
    await expect(now).resolves.toMatchObject({ sections: { calendar: { ok: false } } })
  })
})

describe('RightPanel', () => {
  afterEach(cleanup)
  it('shows search unavailable card when searchGatewayError is set', () => {
    renderWithQueryClient(
      <RightPanel
        chats={[]}
        activeChat={null}
        isStreaming={false}
        search={null}
        searchGatewayError="Gateway returned 500 Internal Server Error"
      />
    )
    expect(screen.getByText('Search')).toBeInTheDocument()
    expect(screen.getByText('unavailable')).toBeInTheDocument()
  })

  it('shows search results when search snapshot has data', () => {
    renderWithQueryClient(
      <RightPanel
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
    expect(screen.getByText(/Search · test/)).toBeInTheDocument()
    expect(screen.getByText('Mem')).toBeInTheDocument()
    expect(screen.getByText('Memory A: remember this')).toBeInTheDocument()
  })
})

describe('TopBar', () => {
  afterEach(cleanup)
  const baseProps = {
    activeModel: { id: 'kitty-default', name: 'default', color: '#4D9FFF', glow: '#4D9FFF99' },
    models: [],
    onSelectModel: () => undefined,
    showModelMenu: false,
    setShowModelMenu: () => undefined,
    isStreaming: false,
    activeChat: null,
    activeView: 'home',
    onViewChange: () => undefined,
    kittyMode: 'default',
    onKittyModeChange: () => undefined,
  }

  it('shows offline indicator when modelFromGateway is false', () => {
    render(<TopBar {...baseProps} modelFromGateway={false} />)
    expect(screen.getByTitle('Using offline model list')).toBeInTheDocument()
  })

  it('does not show offline indicator when modelFromGateway is true', () => {
    render(<TopBar {...baseProps} modelFromGateway={true} />)
    expect(screen.queryByTitle('Using offline model list')).not.toBeInTheDocument()
  })

  it('reserves the iOS status-bar safe area in mobile mode', () => {
    const { container } = render(<TopBar {...baseProps} isMobile />)

    expect((container.firstElementChild as HTMLElement).style.padding).toContain(
      'safe-area-inset-top'
    )
  })
})
