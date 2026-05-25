import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { vi, describe, expect, it, beforeEach, afterEach } from 'vitest'

import { DashboardHome } from '../src/components/DashboardHome'
import { RightPanel } from '../src/components/RightPanel'
import { TopBar } from '../src/components/TopBar'
import { LoopWatch } from '../src/components/LoopWatch'
import { PromptToolkit } from '../src/components/PromptToolkit'
import { InsightFeed } from '../src/components/InsightFeed'
import { TerminalStrip } from '../src/components/TerminalStrip'
import { SessionSidebar } from '../src/components/SessionSidebar'
import { buildGatewayModels, fetchGatewaySearch, summarizeGatewaySearch } from '../src/lib/gateway'
import type { Chat } from '../src/lib/types'

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

describe('LoopWatch', () => {
  afterEach(cleanup)
  const mockLoops = [
    {
      loop_id: 'loop-1',
      name: 'Daily Brief',
      status: 'running',
      interval_minutes: 60,
      last_run: Date.now() - 60000,
    },
    {
      loop_id: 'loop-2',
      name: 'Index',
      status: 'paused',
    },
  ]

  it('renders loops with status badges', () => {
    render(<LoopWatch loops={mockLoops} />)
    expect(screen.getByText('Daily Brief')).toBeInTheDocument()
    expect(screen.getByText('RUNNING')).toBeInTheDocument()
    expect(screen.getByText('Index')).toBeInTheDocument()
    expect(screen.getByText('PAUSED')).toBeInTheDocument()
  })

  it('shows empty state when no loops', () => {
    render(<LoopWatch loops={[]} />)
    expect(screen.getByText('No loops configured')).toBeInTheDocument()
  })

  it('calls onToggle when toggle button clicked', () => {
    const onToggle = vi.fn()
    render(<LoopWatch loops={mockLoops} onToggle={onToggle} />)
    fireEvent.click(screen.getByTitle('Pause loop'))
    expect(onToggle).toHaveBeenCalledWith('loop-1')
  })
})

describe('PromptToolkit', () => {
  afterEach(cleanup)
  const templates = [
    { id: 1, title: 'Brainstorm', content: 'Help me brainstorm...', category: 'Creative', icon: '💡' },
    { id: 2, title: 'Debug', content: 'Help me debug...', category: 'Technical' },
  ]

  it('renders templates grouped by category', () => {
    render(<PromptToolkit templates={templates} />)
    expect(screen.getByText('CREATIVE')).toBeInTheDocument()
    expect(screen.getByText('TECHNICAL')).toBeInTheDocument()
    expect(screen.getByText('Brainstorm')).toBeInTheDocument()
    expect(screen.getByText('Debug')).toBeInTheDocument()
  })

  it('calls onSelect when template clicked', () => {
    const onSelect = vi.fn()
    render(<PromptToolkit templates={templates} onSelect={onSelect} />)
    fireEvent.click(screen.getByText('Brainstorm'))
    expect(onSelect).toHaveBeenCalledWith('Help me brainstorm...')
  })
})

describe('InsightFeed', () => {
  afterEach(cleanup)
  const insights = [
    {
      insight_id: 'i1',
      kind: 'pattern',
      title: 'Pattern detected',
      detail: 'Details here',
      created_at: Date.now() / 1000,
    },
    {
      insight_id: 'i2',
      kind: 'suggestion',
      title: 'Suggest action',
      actions: [{ label: 'Do it', action_id: 'act-1' }],
      created_at: Date.now() / 1000,
    },
  ]

  it('renders insight kinds and titles', () => {
    render(<InsightFeed insights={insights} />)
    expect(screen.getByText('PATTERN')).toBeInTheDocument()
    expect(screen.getByText('SUGGESTION')).toBeInTheDocument()
    expect(screen.getByText('Pattern detected')).toBeInTheDocument()
    expect(screen.getByText('Suggest action')).toBeInTheDocument()
  })

  it('shows action buttons and calls onAction', () => {
    const onAction = vi.fn()
    render(<InsightFeed insights={insights} onAction={onAction} />)
    fireEvent.click(screen.getByRole('button', { name: 'Do it' }))
    expect(onAction).toHaveBeenCalledWith('i2', 'act-1')
  })

  it('calls onDismiss when dismiss clicked', () => {
    const onDismiss = vi.fn()
    render(<InsightFeed insights={insights} onDismiss={onDismiss} />)
    fireEvent.click(screen.getAllByTitle('Dismiss')[0])
    expect(onDismiss).toHaveBeenCalledWith('i1')
  })
})

describe('TerminalStrip', () => {
  afterEach(cleanup)
  it('shows initial line count', () => {
    render(<TerminalStrip title="Test Log" maxLines={10} />)
    expect(screen.getByText('Test Log')).toBeInTheDocument()
    expect(screen.getByText('0 lines')).toBeInTheDocument()
  })
})

describe('SessionSidebar', () => {
  afterEach(cleanup)
  const mockChats: Chat[] = [
    {
      id: 'chat-1',
      title: 'First Chat',
      messages: [],
      model: 'kitty-default',
      color: 'teal',
      createdAt: new Date(),
      updatedAt: new Date(),
    },
    {
      id: 'chat-2',
      title: 'Second Chat',
      messages: [{ role: 'user', content: 'hello', timestamp: new Date() }],
      model: 'kitty-default',
      color: 'coral',
      createdAt: new Date(),
      updatedAt: new Date(),
    },
  ]

  it('renders sessions header and new chat button', () => {
    render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} />)
    expect(screen.getByText('SESSIONS')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '+ new' })).toBeInTheDocument()
  })

  it('shows today and earlier groups based on date', () => {
    render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} />)
    expect(screen.getByText('Today')).toBeInTheDocument()
    expect(screen.getByText('Earlier')).toBeInTheDocument()
  })

  it('collapses to icon-only mode when collapsed prop is true', () => {
    render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} collapsed={true} />)
    expect(screen.queryByText('SESSIONS')).not.toBeInTheDocument()
    expect(screen.queryByText('Today')).not.toBeInTheDocument()
    const avatars = screen.getAllByRole('button', { name: /^[A-Z]$/ })
    expect(avatars.length).toBe(mockChats.length)
  })

  it('new chat button shows + only when collapsed', () => {
    const { rerender } = render(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} collapsed={false} />)
    expect(screen.getByText('+ new')).toBeInTheDocument()
    rerender(<SessionSidebar chats={mockChats} activeChatId={null} onSelectChat={() => {}} onNewChat={() => {}} onCloseChat={() => {}} collapsed={true} />)
    expect(screen.queryByText('+ new')).not.toBeInTheDocument()
    expect(screen.getByText('+')).toBeInTheDocument()
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
