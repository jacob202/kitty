import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchGatewaySearch } from '../src/lib/gateway'

vi.mock('../src/lib/gateway', () => ({
  fetchGatewaySearch: vi.fn(),
}))

import { CommandPalette } from '../src/components/CommandPalette'

beforeEach(() => {
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

  it.each([
    ['knowledge', 'library'],
    ['memory', 'library'],
    ['capture', 'library'],
    ['todo', 'work'],
    ['journal', 'journal'],
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
