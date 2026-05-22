import { render, screen, cleanup } from '@testing-library/react'
import { vi, describe, expect, it, beforeEach, afterEach } from 'vitest'

import { DashboardHome } from '../src/components/DashboardHome'
import { RightPanel } from '../src/components/RightPanel'
import { TopBar } from '../src/components/TopBar'
import { buildGatewayModels, fetchGatewaySearch, summarizeGatewaySearch } from '../src/lib/gateway'

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

describe('RightPanel', () => {
  afterEach(cleanup)
  it('shows search unavailable card when searchGatewayError is set', () => {
    render(
      <RightPanel
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
    expect(screen.getByText('Gateway search')).toBeInTheDocument()
    expect(screen.getByText('Memories')).toBeInTheDocument()
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
    kittyModes: [{ id: 'default', name: 'Default' }],
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

describe('DashboardHome', () => {
  afterEach(cleanup)
  it('renders a live gateway brief when one is available', () => {
    render(
      <DashboardHome
        brief={{
          date: '2026-05-18',
          headlines: ['Kitty is live'],
          memory_snippet: 'Remember to use the live gateway.',
          intention: 'Ship the integrated UI.',
          generated_at: '2026-05-18T17:17:23.150346Z',
          notification_sent: false,
          error: null,
        }}
        todos={[]}
        loops={[]}
        insights={[]}
        promptTemplates={[]}
      />
    )

    expect(screen.getByText('Kitty is live')).toBeInTheDocument()
    expect(screen.getAllByText('Ship the integrated UI.').length).toBeGreaterThan(0)
    expect(screen.getByText('Remember to use the live gateway.')).toBeInTheDocument()
    expect(screen.getByText("Today's Compass")).toBeInTheDocument()
    expect(screen.getByText('Loop Watch')).toBeInTheDocument()
  })

  it('shows loading skeleton when loading prop is true', () => {
    render(
      <DashboardHome
        brief={null}
        todos={[]}
        loops={[]}
        insights={[]}
        promptTemplates={[]}
        loading={true}
      />
    )
    expect(screen.getByRole('status', { name: /loading dashboard/i })).toBeInTheDocument()
  })

  it('shows brief strip when loading is false and brief is null', () => {
    render(
      <DashboardHome
        brief={null}
        todos={[]}
        loops={[]}
        insights={[]}
        promptTemplates={[]}
        loading={false}
      />
    )
    expect(screen.getByText('NEXT UP')).toBeInTheDocument()
  })
})
