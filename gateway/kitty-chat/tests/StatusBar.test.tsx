import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { StatusBar } from '../src/components/StatusBar'

beforeEach(() => {
  localStorage.clear()
})

afterEach(cleanup)

const baseProps = {
  showChatSignals: true,
  attachmentErrors: [],
  modelsUnavailable: false,
  onRetryModels: vi.fn(),
  saveState: 'idle' as const,
  onRetrySave: vi.fn(),
  briefUnavailable: false,
  pwaState: 'hidden' as const,
  onPwaInstall: vi.fn(),
}

describe('StatusBar', () => {
  it('renders nothing when no condition is active', () => {
    const { container } = render(<StatusBar {...baseProps} />)
    expect(container.firstChild).toBeNull()
  })

  it('ranks attachment errors above the models-unavailable row', () => {
    render(
      <StatusBar
        {...baseProps}
        attachmentErrors={[{ file: 'x.png', reason: 'too big' }]}
        modelsUnavailable
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('x.png: too big')
    expect(screen.queryByText(/can't reach any models/i)).toBeNull()
  })

  it('shows the models-unavailable row above save-state failures and retries on click', () => {
    const onRetryModels = vi.fn()
    const props = {
      ...baseProps,
      modelsUnavailable: true,
      onRetryModels,
      saveState: 'failed' as const,
    }
    const { rerender } = render(<StatusBar {...props} />)
    rerender(<StatusBar {...props} />)
    rerender(<StatusBar {...props} />)
    expect(screen.getByText(/can't reach any models/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'retry' }))
    expect(onRetryModels).toHaveBeenCalledTimes(1)
  })

  it('shows a failed save with a working retry action', () => {
    const onRetrySave = vi.fn()
    render(<StatusBar {...baseProps} saveState="failed" onRetrySave={onRetrySave} />)
    expect(screen.getByText(/save failed/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'retry' }))
    expect(onRetrySave).toHaveBeenCalledTimes(1)
  })

  it('hides chat-only signals when no chat is on screen', () => {
    const { container } = render(
      <StatusBar
        {...baseProps}
        showChatSignals={false}
        attachmentErrors={[{ file: 'x.png', reason: 'too big' }]}
        saveState="saved"
      />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('shows brief-unavailable when nothing higher-priority is active', () => {
    render(<StatusBar {...baseProps} briefUnavailable briefError="timeout" />)
    expect(screen.getByText(/Brief unavailable \(timeout\)/)).toBeInTheDocument()
  })

  it('offers install when the browser can install the app', () => {
    const onPwaInstall = vi.fn()
    render(<StatusBar {...baseProps} pwaState="available" onPwaInstall={onPwaInstall} />)
    fireEvent.click(screen.getByRole('button', { name: 'install as app' }))
    expect(onPwaInstall).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/dock launch/i)).toBeInTheDocument()
  })

  it('shows manual iOS instructions with only a dismiss button', () => {
    render(<StatusBar {...baseProps} pwaState="manual-ios" />)
    const status = screen.getByRole('status')
    expect(screen.getByText(/Add to Home Screen/i)).toBeInTheDocument()
    expect(status.querySelectorAll('button').length).toBe(1)
    expect(screen.getByRole('button', { name: 'Dismiss' })).toBeInTheDocument()
  })

  it('surfaces a pwa install error as an alert', () => {
    render(<StatusBar {...baseProps} pwaState="error" pwaError="boom" />)
    expect(screen.getByRole('alert')).toHaveTextContent('boom')
  })

  it('falls back to the transient save state when nothing else is active', () => {
    render(<StatusBar {...baseProps} saveState="saving" />)
    expect(screen.getByText('saving…')).toBeInTheDocument()
  })

  it('persists dismissal to localStorage when dismiss button is clicked', () => {
    render(<StatusBar {...baseProps} pwaState="available" />)
    expect(screen.getByText(/dock launch/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(localStorage.getItem('kitty-pwa-install-dismissed')).toBe('true')
  })

  it('does not render install banner when kitty-pwa-install-dismissed is true in localStorage', () => {
    localStorage.setItem('kitty-pwa-install-dismissed', 'true')
    const { container } = render(<StatusBar {...baseProps} pwaState="available" />)
    expect(container.firstChild).toBeNull()
  })

  it('still renders and dismisses banner when localStorage throws on read', () => {
    const originalGetItem = localStorage.getItem
    localStorage.getItem = vi.fn(() => {
      throw new Error('quota exceeded')
    })
    try {
      render(<StatusBar {...baseProps} pwaState="manual-ios" />)
      expect(screen.getByText(/Add to Home Screen/i)).toBeInTheDocument()
      fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
      expect(screen.queryByText(/Add to Home Screen/i)).not.toBeInTheDocument()
    } finally {
      localStorage.getItem = originalGetItem
    }
  })
  // Product acceptance, PR #675: this row claimed "gateway offline" while the
  // Home panels correctly said "Kitty is running but this part isn't answering
  // yet." The flag behind it is model-list availability, and HealthGate has
  // already proven the gateway reachable before StatusBar renders at all — so
  // the row must never claim the gateway is down, and must not use the word.
  it('never claims the gateway is offline, and avoids internal vocabulary', () => {
    const props = { ...baseProps, modelsUnavailable: true, showChatSignals: false }
    const { container, rerender } = render(<StatusBar {...props} />)
    rerender(<StatusBar {...props} />)
    rerender(<StatusBar {...props} />)
    const text = container.textContent ?? ''
    expect(text).toMatch(/can't reach any models/i)
    expect(text).not.toMatch(/gateway/i)
    expect(text).not.toMatch(/offline/i)
  })
})
