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
  modelUnavailable: false,
  onRetryModels: vi.fn(),
  saveState: 'idle' as const,
  onRetrySave: vi.fn(),
  briefUnavailable: false,
  pwaState: 'hidden' as const,
  onPwaInstall: vi.fn(),
}

describe('StatusBar', () => {
  it('shows a connected indicator when everything is healthy', () => {
    const { container } = render(<StatusBar {...baseProps} />)
    const status = container.firstChild as HTMLElement | null
    expect(status).not.toBeNull()
    expect(status).toHaveAttribute('role', 'status')
    expect(status).toHaveTextContent('connected')
    const dot = status?.querySelector('span')
    expect(dot).toHaveStyle({ borderRadius: '50%' })
  })

  it('ranks attachment errors above model availability failure', () => {
    render(
      <StatusBar
        {...baseProps}
        attachmentErrors={[{ file: 'x.png', reason: 'too big' }]}
        modelUnavailable
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('x.png: too big')
    expect(screen.queryByText('model availability failure')).toBeNull()
  })

  it('shows model availability failure immediately with a working retry action', () => {
    const onRetryModels = vi.fn()
    render(
      <StatusBar
        {...baseProps}
        modelUnavailable
        onRetryModels={onRetryModels}
        saveState="failed"
      />,
    )
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('Models are temporarily unavailable. Retry to reconnect to Kitty.')
    expect(status).not.toHaveTextContent(/gateway/i)
    fireEvent.click(screen.getByRole('button', { name: 'retry' }))
    expect(onRetryModels).toHaveBeenCalledTimes(1)
  })

  it('surfaces picker-specific model detail failures instead of calling the gateway offline', () => {
    const props = {
      ...baseProps,
      modelUnavailable: true,
      modelError: 'Model details unavailable — model picker returned 503. Retry to reconnect to Kitty.',
    }
    render(<StatusBar {...props} />)
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('Model details are unavailable right now. Retry to reconnect to Kitty.')
    expect(status).not.toHaveTextContent(/503|model picker|gateway/i)
  })

  it('translates timeout and no-model diagnostics into product language', () => {
    const { rerender } = render(
      <StatusBar
        {...baseProps}
        modelUnavailable
        modelError="Model details timed out — request timed out after 5000ms."
      />,
    )
    let status = screen.getByRole('status')
    expect(status).toHaveTextContent('Model details are taking too long to load. Retry to reconnect to Kitty.')
    expect(status).not.toHaveTextContent(/5000|request timed out|gateway/i)

    rerender(
      <StatusBar
        {...baseProps}
        modelUnavailable
        modelError="No live curated models are available — provider discovery returned 503."
      />,
    )
    status = screen.getByRole('status')
    expect(status).toHaveTextContent('No models are available right now. Retry to reconnect to Kitty.')
    expect(status).not.toHaveTextContent(/curated|provider|503|gateway/i)
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
    expect(screen.getByText(/took too long to answer/i)).toBeInTheDocument()
    expect(screen.getByText(/chat still works/i)).toBeInTheDocument()
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
  // The install prompt held its dismissal in component state, so it returned on
  // every reload. On a phone that banner occupies a permanent strip and re-nags
  // on every app restart.
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

  // Codex P1 on #675: hiding the banner while the write failed claimed a
  // persistence that did not happen — it silently returned on the next reload.
  it('says so when the dismissal could not be saved', () => {
    const originalSetItem = localStorage.setItem
    localStorage.setItem = vi.fn(() => {
      throw new Error('storage blocked')
    })
    try {
      render(<StatusBar {...baseProps} pwaState="available" />)
      fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
      const status = screen.getByRole('status')
      expect(status).toHaveTextContent(/blocking storage/i)
      expect(status).toHaveTextContent(/comes back next time/i)
      expect(screen.queryByText(/dock launch/i)).not.toBeInTheDocument()
    } finally {
      localStorage.setItem = originalSetItem
    }
  })

  it('stays silent when the dismissal saved cleanly', () => {
    const { container } = render(<StatusBar {...baseProps} pwaState="available" />)
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
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
  // The brief row was unreachable while the model row always fired, so this
  // leak stayed hidden: it rendered the gateway's raw text verbatim
  // ("Brief unavailable (Gateway returned 404 Not Found)"). Kitty's owner does
  // not code; no user-facing row may show an HTTP status or internal name.
  it('translates a brief failure instead of printing the raw gateway text', () => {
    render(
      <StatusBar
        {...baseProps}
        briefUnavailable
        briefError="Gateway returned 404 Not Found"
      />,
    )
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent(/chat still works/i)
    expect(status).not.toHaveTextContent(/Gateway returned/i)
    expect(status).not.toHaveTextContent(/404/)
  })

  it('keeps internal vocabulary out of the offline save row', () => {
    render(<StatusBar {...baseProps} saveState="offline" />)
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent(/chat not saved/i)
    expect(status).not.toHaveTextContent(/gateway/i)
  })
})
