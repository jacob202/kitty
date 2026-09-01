import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchCapabilities, fetchGatewaySearch } from '../src/lib/gateway'

vi.mock('../src/lib/gateway', () => ({
  fetchCapabilities: vi.fn(),
  fetchGatewaySearch: vi.fn(),
}))

import { CommandPalette } from '../src/components/CommandPalette'

beforeEach(() => {
  vi.mocked(fetchGatewaySearch).mockReset()
  vi.mocked(fetchCapabilities).mockReset()
  vi.mocked(fetchCapabilities).mockResolvedValue({ capabilities: [], fromLiveGateway: true, error: null } as never)
  vi.stubGlobal('ResizeObserver', class {
    observe() {}
    unobserve() {}
    disconnect() {}
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  cleanup()
})

describe('CommandPalette', () => {
  it('loads live capabilities and delegates their launch behavior', async () => {
    const onLaunchCapability = vi.fn()
    vi.mocked(fetchCapabilities).mockResolvedValue({
      capabilities: [
        { id: 'work', label: 'work', description: 'Run and inspect delegated Kitty work.', category: 'work', launch: 'view', view: 'work' },
        { id: 'skill:agent-council', label: 'agent council', description: 'Ask multiple agents for independent judgment.', category: 'skills', launch: 'skill', skill_name: 'agent-council' },
      ],
      fromLiveGateway: true,
      error: null,
    } as never)

    render(
      <CommandPalette
        chats={[]}
        onNewChat={vi.fn()}
        onSelectChat={vi.fn()}
        onViewChange={vi.fn()}
        onToggleSidebar={vi.fn()}
        onLaunchCapability={onLaunchCapability}
        open
        onOpenChange={vi.fn()}
      />,
    )

    expect(await screen.findByText('agent council')).toBeVisible()
    expect(screen.getByText('Ask multiple agents for independent judgment.')).toBeVisible()
    fireEvent.click(screen.getByText('agent council'))

    expect(onLaunchCapability).toHaveBeenCalledWith(expect.objectContaining({
      id: 'skill:agent-council',
      launch: 'skill',
      skill_name: 'agent-council',
    }))
  })

  it('does not expose Builder as a second normal-user destination', () => {
    render(
      <CommandPalette
        chats={[]}
        onNewChat={vi.fn()}
        onSelectChat={vi.fn()}
        onViewChange={vi.fn()}
        onToggleSidebar={vi.fn()}
        open
        onOpenChange={vi.fn()}
      />,
    )

    expect(screen.getByText('work')).toBeVisible()
    expect(screen.queryByText('builder')).not.toBeInTheDocument()
  })

  it('shows capability discovery details and retries the live catalog', async () => {
    vi.mocked(fetchCapabilities)
      .mockResolvedValueOnce({ capabilities: [], fromLiveGateway: false, error: 'Gateway 503: catalog unavailable' } as never)
      .mockResolvedValueOnce({
        capabilities: [{ id: 'image-lab', label: 'image lab', description: 'Create images.', category: 'create', launch: 'view', view: 'studio' }],
        fromLiveGateway: true,
        error: null,
      } as never)

    render(
      <CommandPalette
        chats={[]}
        onNewChat={vi.fn()}
        onSelectChat={vi.fn()}
        onViewChange={vi.fn()}
        onToggleSidebar={vi.fn()}
        open
        onOpenChange={vi.fn()}
      />,
    )

    expect(await screen.findByText('live capabilities unavailable — navigation fallback shown.')).toBeVisible()
    expect(screen.getByText('Gateway 503: catalog unavailable')).toBeInTheDocument()
    fireEvent.click(screen.getByText('technical details'))
    expect(screen.getByText('Gateway 503: catalog unavailable')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'retry capabilities' }))
    expect(await screen.findByText('image lab')).toBeVisible()
    expect(fetchCapabilities).toHaveBeenCalledTimes(2)
  })

  it('shows canonical Kitty search results while typing', async () => {
    vi.mocked(fetchGatewaySearch).mockResolvedValue({
      snapshot: null,
      hits: [{
        kind: 'knowledge',
        source: 'sansui.pdf',
        title: 'Sansui bias notes',
        text: 'MOSFET bias procedure and target voltage',
        score: 0.87,
      }],
      fromLiveGateway: true,
      error: null,
    } as never)

    render(
      <CommandPalette
        chats={[]}
        onNewChat={vi.fn()}
        onSelectChat={vi.fn()}
        onViewChange={vi.fn()}
        onToggleSidebar={vi.fn()}
        open
        onOpenChange={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByPlaceholderText('type a command or search…'), {
      target: { value: 'mosfet' },
    })

    expect(await screen.findByText('Sansui bias notes')).toBeInTheDocument()
    expect(fetchGatewaySearch).toHaveBeenCalled()
  })

  it('clears hits from the previous query immediately', async () => {
    vi.mocked(fetchGatewaySearch).mockImplementation((query: string) => {
      if (query === 'first') {
        return Promise.resolve({
          snapshot: null,
          hits: [{ kind: 'knowledge', source: 'old', title: 'old result', text: 'old', score: 1 }],
          degradedStores: [],
          degradedErrors: [],
          fromLiveGateway: true,
          error: null,
        } as never)
      }
      return new Promise(() => {})
    })

    render(
      <CommandPalette
        chats={[]}
        onNewChat={vi.fn()}
        onSelectChat={vi.fn()}
        onViewChange={vi.fn()}
        onToggleSidebar={vi.fn()}
        open
        onOpenChange={vi.fn()}
      />,
    )

    const input = screen.getByPlaceholderText('type a command or search…')
    fireEvent.change(input, { target: { value: 'first' } })
    expect(await screen.findByText('old result')).toBeInTheDocument()

    fireEvent.change(input, { target: { value: 'second' } })
    expect(screen.queryByText('old result')).not.toBeInTheDocument()
  })

  it.each([
    ['knowledge', 'library'],
  ])('opens the owning surface for a %s search result', async (kind, expectedView) => {
    const onViewChange = vi.fn()
    vi.mocked(fetchGatewaySearch).mockResolvedValue({
      snapshot: null,
      hits: [{
        kind,
        source: 'source',
        title: `${kind} result`,
        text: 'matching content',
        score: 0.87,
      }],
      fromLiveGateway: true,
      error: null,
    } as never)

    render(
      <CommandPalette
        chats={[]}
        onNewChat={vi.fn()}
        onSelectChat={vi.fn()}
        onViewChange={onViewChange}
        onToggleSidebar={vi.fn()}
        open
        onOpenChange={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByPlaceholderText('type a command or search…'), {
      target: { value: 'matching' },
    })
    fireEvent.click(await screen.findByText(`${kind} result`))

    expect(onViewChange).toHaveBeenCalledWith(expectedView)
  })

  it.each(['memory', 'capture', 'todo', 'journal'])('keeps an unsupported %s hit visible instead of routing to the wrong surface', async (kind) => {
    const onViewChange = vi.fn()
    const onOpenChange = vi.fn()
    vi.mocked(fetchGatewaySearch).mockResolvedValue({
      snapshot: null,
      hits: [{ kind, source: 'source', title: `${kind} result`, text: 'matching content', score: 0.87 }],
      degradedStores: [],
      degradedErrors: [],
      fromLiveGateway: true,
      error: null,
    } as never)

    render(
      <CommandPalette
        chats={[]}
        onNewChat={vi.fn()}
        onSelectChat={vi.fn()}
        onViewChange={onViewChange}
        onToggleSidebar={vi.fn()}
        open
        onOpenChange={onOpenChange}
      />,
    )

    fireEvent.change(screen.getByPlaceholderText('type a command or search…'), {
      target: { value: 'matching' },
    })
    const result = await screen.findByText(`${kind} result`)
    expect(result.closest('[role="option"]')).toHaveAttribute('aria-disabled', 'true')
    expect(screen.getByText('preview only')).toBeVisible()
    fireEvent.click(result)

    expect(onViewChange).not.toHaveBeenCalled()
    expect(onOpenChange).not.toHaveBeenCalled()
    expect(result).toBeVisible()
  })

  it('does not let a stale slow query overwrite a newer result', async () => {
    let resolveFirst: ((value: unknown) => void) | undefined
    const first = new Promise(resolve => { resolveFirst = resolve })
    vi.mocked(fetchGatewaySearch).mockImplementation((query: string) => {
      if (query === 'first') return first as never
      return Promise.resolve({
        snapshot: null,
        hits: [{ kind: 'knowledge', source: 'new', title: 'new result', text: 'new', score: 1 }],
        degradedStores: [],
        fromLiveGateway: true,
        error: null,
      } as never)
    })

    render(
      <CommandPalette
        chats={[]}
        onNewChat={vi.fn()}
        onSelectChat={vi.fn()}
        onViewChange={vi.fn()}
        onToggleSidebar={vi.fn()}
        open
        onOpenChange={vi.fn()}
      />,
    )
    const input = screen.getByPlaceholderText('type a command or search…')
    fireEvent.change(input, { target: { value: 'first' } })
    await new Promise(resolve => setTimeout(resolve, 300))
    fireEvent.change(input, { target: { value: 'second' } })
    expect(await screen.findByText('new result')).toBeInTheDocument()

    resolveFirst?.({
      snapshot: null,
      hits: [{ kind: 'knowledge', source: 'old', title: 'old result', text: 'old', score: 1 }],
      degradedStores: [],
      fromLiveGateway: true,
      error: null,
    })
    await new Promise(resolve => setTimeout(resolve, 50))

    expect(screen.queryByText('old result')).not.toBeInTheDocument()
    expect(screen.getByText('new result')).toBeInTheDocument()
  })

  it('shows a concise warning when some search sources are unavailable', async () => {
    vi.mocked(fetchGatewaySearch).mockResolvedValue({
      snapshot: null,
      hits: [],
      degradedStores: ['memory', 'knowledge'],
      degradedErrors: ['memory: TimeoutError: timed out'],
      fromLiveGateway: true,
      error: null,
    } as never)

    render(
      <CommandPalette
        chats={[]}
        onNewChat={vi.fn()}
        onSelectChat={vi.fn()}
        onViewChange={vi.fn()}
        onToggleSidebar={vi.fn()}
        open
        onOpenChange={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByPlaceholderText('type a command or search…'), {
      target: { value: 'missing' },
    })

    expect(await screen.findByText('some sources unavailable: memory, knowledge')).toBeInTheDocument()
    expect(screen.getByText('memory: TimeoutError: timed out')).toBeInTheDocument()
  })

  it('shows a recovery message and bounded technical detail when Gateway search fails', async () => {
    vi.mocked(fetchGatewaySearch).mockResolvedValue({
      snapshot: null,
      hits: [],
      degradedStores: [],
      degradedErrors: [],
      fromLiveGateway: false,
      error: 'Gateway returned 503 Service Unavailable',
    } as never)

    render(
      <CommandPalette
        chats={[]}
        onNewChat={vi.fn()}
        onSelectChat={vi.fn()}
        onViewChange={vi.fn()}
        onToggleSidebar={vi.fn()}
        open
        onOpenChange={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByPlaceholderText('type a command or search…'), {
      target: { value: 'missing' },
    })

    expect(await screen.findByRole('alert')).toHaveTextContent('search unavailable')
    expect(screen.getByText('Gateway returned 503 Service Unavailable')).toBeInTheDocument()
  })

  it('shows that remote search is pending instead of reporting no results', async () => {
    vi.mocked(fetchGatewaySearch).mockImplementation(() => new Promise(() => {}))

    render(
      <CommandPalette
        chats={[]}
        onNewChat={vi.fn()}
        onSelectChat={vi.fn()}
        onViewChange={vi.fn()}
        onToggleSidebar={vi.fn()}
        open
        onOpenChange={vi.fn()}
      />,
    )

    fireEvent.change(screen.getByPlaceholderText('type a command or search…'), {
      target: { value: 'remote-only query' },
    })

    expect(screen.getByText('searching Kitty…')).toBeInTheDocument()
    expect(screen.queryByText('no results.')).not.toBeInTheDocument()
  })

  it('resets the controlled query when the palette closes', () => {
    const onOpenChange = vi.fn()
    const props = {
      chats: [],
      onNewChat: vi.fn(),
      onSelectChat: vi.fn(),
      onViewChange: vi.fn(),
      onToggleSidebar: vi.fn(),
      onOpenChange,
    }
    const { rerender } = render(<CommandPalette {...props} open />)
    fireEvent.change(screen.getByPlaceholderText('type a command or search…'), {
      target: { value: 'remembered query' },
    })

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onOpenChange).toHaveBeenCalledWith(false)
    rerender(<CommandPalette {...props} open={false} />)
    rerender(<CommandPalette {...props} open />)

    expect(screen.getByPlaceholderText('type a command or search…')).toHaveValue('')
  })

  it('opens the shared Agents room from the Go to commands', () => {
    const onViewChange = vi.fn()

    render(
      <CommandPalette
        chats={[]}
        onNewChat={vi.fn()}
        onSelectChat={vi.fn()}
        onViewChange={onViewChange}
        onToggleSidebar={vi.fn()}
        open
        onOpenChange={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByText('agents'))

    expect(onViewChange).toHaveBeenCalledWith('agents')
  })
})
