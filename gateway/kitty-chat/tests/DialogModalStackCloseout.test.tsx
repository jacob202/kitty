import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CommandPalette } from '../src/components/CommandPalette'
import { useDialogFocus } from '../src/hooks/useDialogFocus'
import * as gateway from '../src/lib/gateway'

vi.mock('../src/lib/gateway', async () => {
  const actual = await vi.importActual<typeof gateway>('../src/lib/gateway')
  return {
    ...actual,
    fetchCapabilities: vi.fn(),
    fetchGatewaySearch: vi.fn(),
  }
})

function UnderlyingDialog({ onClose }: { onClose: () => void }) {
  const ref = useDialogFocus<HTMLDivElement>({ open: true, onClose })
  return (
    <div ref={ref} role="dialog" aria-modal="true" aria-label="underlying dialog">
      <button type="button">underlying action</button>
    </div>
  )
}

beforeEach(() => {
  vi.mocked(gateway.fetchCapabilities).mockResolvedValue({ capabilities: [], fromLiveGateway: true, error: null } as never)
  vi.mocked(gateway.fetchGatewaySearch).mockResolvedValue({ hits: [], degradedStores: [], degradedErrors: [], error: null } as never)
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

describe('global modal stack closeout', () => {
  it('lets a top aria-modal own Tab and Escape instead of the lower dialog trap', () => {
    const onClose = vi.fn()
    render(
      <>
        <UnderlyingDialog onClose={onClose} />
        <div role="dialog" aria-modal="true" aria-label="top dialog">
          <button type="button">top action</button>
        </div>
      </>,
    )

    const top = screen.getByRole('button', { name: 'top action' })
    top.focus()
    fireEvent.keyDown(top, { key: 'Tab' })
    expect(top).toHaveFocus()
    fireEvent.keyDown(top, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('places the global command palette above artifact and activity modal layers', () => {
    const { container } = render(
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

    const backdrop = container.firstElementChild as HTMLElement
    expect(Number(backdrop.style.zIndex)).toBeGreaterThan(1250)
    expect(screen.getByRole('dialog', { name: /command palette/i })).toBeVisible()
  })
})
