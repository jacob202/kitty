import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

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
