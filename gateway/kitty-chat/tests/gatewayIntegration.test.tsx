import { render, screen, cleanup } from '@testing-library/react'
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi, describe, expect, it, beforeEach, afterEach } from 'vitest'

import { RightPanel } from '../src/components/RightPanel'
import { TopBar } from '../src/components/TopBar'
import {
  buildGatewayModels,
  fetchGatewayModels,
  fetchGatewaySearch,
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
      inbox: [
        {
          kind: 'capture',
          source: 'inbox',
          title: 'Captured note',
          text: 'remember this capture',
          score: 0.7,
        },
      ],
    })

    expect(summary.query).toBe('honda')
    expect(summary.sections.memories[0]).toContain('remember this')
    expect(summary.sections.knowledge[0]).toContain('KB note')
    expect(summary.sections.todos[0]).toContain('Call shop')
    expect(summary.sections.inbox[0]).toContain('Captured note')
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

  it('waits longer than the backend store timeout before aborting search', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('window', {
      setTimeout: globalThis.setTimeout,
      clearTimeout: globalThis.clearTimeout,
    })
    vi.mocked(global.fetch).mockImplementation((_url, init) => {
      const signal = init?.signal as AbortSignal | undefined
      return new Promise((_resolve, reject) => {
        signal?.addEventListener('abort', () => {
          const err = new Error('The operation was aborted')
          err.name = 'AbortError'
          reject(err)
        }, { once: true })
      })
    })

    let settled = false
    const pending = fetchGatewaySearch('slow partial search').then((result) => {
      settled = true
      return result
    })
    await vi.advanceTimersByTimeAsync(5_100)
    expect(settled).toBe(false)

    await vi.advanceTimersByTimeAsync(2_000)
    expect((await pending).error).toContain('timed out')
    vi.useRealTimers()
  })

  it('adapts the live flat /search contract into grouped context sections', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({
        query: 'mosfet',
        results: [
          { store: 'knowledge', content: 'MOSFET bias notes', score: 0.87 },
          { store: 'memory', content: 'Jacob owns the manual', score: 0.8 },
        ],
        stores: ['knowledge', 'memory'],
        errors: ['generic search warning'],
        degraded_stores: ['memory', 'knowledge'],
      }), { status: 200 }),
    )

    const result = await fetchGatewaySearch('mosfet', 3)

    expect(result.fromLiveGateway).toBe(true)
    expect(result.error).toBeNull()
    expect(result.snapshot?.sections.knowledge[0]).toContain('MOSFET bias notes')
    expect(result.snapshot?.sections.memories[0]).toContain('Jacob owns the manual')
    expect(result.degradedStores).toEqual(['memory', 'knowledge'])
    expect(result.degradedErrors).toEqual(['generic search warning'])
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

describe('fetchGatewayModels', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => { vi.unstubAllGlobals() })

  it('keeps a safe route but reports degraded state when curated metadata is unavailable', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ data: [{ id: 'kitty-code' }] }), { status: 200 }),
    )

    const result = await fetchGatewayModels()

    expect(result.fromLiveGateway).toBe(false)
    expect(result.error).toMatch(/model details unavailable/i)
    expect(result.models.map(model => [model.id, model.name])).toEqual([['kitty-code', 'Code']])
  })

  it('exposes only the configured human-facing shortlist when raw LiteLLM aliases include internal routes', async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({
          data: [
            { id: 'kitty-default', display_name: 'deepseek-v4-pro' },
            { id: 'kitty-sonnet', display_name: 'deepseek-v4-pro' },
            { id: 'kitty-code', display_name: 'qwen3-coder' },
            { id: 'kitty-local', display_name: 'Qwen3.5-4B-4bit' },
          ],
        }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({
          schema_version: 1, source: 'test',
          discovery: { state: 'missing', reason: null, checked_at: null },
          claims: { role_tags: 'heuristic', alternatives: 'cost-screened only' },
          presets: [
            { role: 'auto', label: 'Daily Kitty', route: 'kitty-default', purpose: 'Everyday use.', kind: 'router', provider: null, model: null, configured: true, catalogue: null, catalogue_state: 'not_applicable', alternatives: [] },
            { role: 'code', label: 'Code', route: 'kitty-code', purpose: 'Repository work.', kind: 'model_role', provider: 'openrouter', model: 'qwen/qwen3-coder', configured: true, catalogue: null, catalogue_state: 'not_observed', alternatives: [] },
          ],
        }), { status: 200 }),
      )

    const result = await fetchGatewayModels()

    expect(result.fromLiveGateway).toBe(true)
    expect(result.models.map(model => [model.id, model.name])).toEqual([
      ['kitty-default', 'Daily Kitty'],
      ['kitty-code', 'Code'],
    ])
  })

  it('marks the model list offline instead of hiding a proxy error', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(null, { status: 503, statusText: 'Service Unavailable' }),
    )

    const result = await fetchGatewayModels()

    expect(result.fromLiveGateway).toBe(false)
    expect(result.error).toContain('503')
    expect(result.models.length).toBeGreaterThan(0)
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
    expect(screen.getByText('search')).toBeInTheDocument()
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

  it('disables model selection when live availability is unknown', () => {
    render(<TopBar {...baseProps} modelFromGateway={false} />)
    const modelButton = screen.getByRole('button', { name: 'Model: default' })
    expect(modelButton).toBeDisabled()
    expect(modelButton).toHaveAttribute(
      'title',
      'model availability is unknown — reconnect to Kitty before switching',
    )
  })

  it('does not show an unknown-availability warning when modelFromGateway is true', () => {
    render(<TopBar {...baseProps} modelFromGateway={true} />)
    expect(
      screen.queryByTitle('model availability is unknown — reconnect to Kitty before switching'),
    ).not.toBeInTheDocument()
  })

  it('reserves the iOS status-bar safe area in mobile mode', () => {
    const { container } = render(<TopBar {...baseProps} isMobile />)

    expect((container.firstElementChild as HTMLElement).style.padding).toContain(
      'safe-area-inset-top'
    )
  })

  it('labels the mobile sidebar control and gives it a 44px target', () => {
    render(<TopBar {...baseProps} isMobile onToggleSidebar={() => undefined} />)

    const sidebarButton = screen.getByRole('button', { name: 'Open sidebar' })
    expect(sidebarButton).toHaveStyle({ width: '44px', height: '44px' })
  })
})
