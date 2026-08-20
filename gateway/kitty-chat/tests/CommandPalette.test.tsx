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
