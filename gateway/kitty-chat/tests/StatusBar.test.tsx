import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StatusBar } from '../src/components/StatusBar'

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
  it('renders nothing when no condition is active', () => {
    const { container } = render(<StatusBar {...baseProps} />)
    expect(container.firstChild).toBeNull()
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
    expect(status).toHaveTextContent('models temporarily unavailable')
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
    expect(status).toHaveTextContent('Model details unavailable')
    expect(status).toHaveTextContent('model picker returned 503')
    expect(status).toHaveTextContent('Retry to reconnect to Kitty')
    expect(status).not.toHaveTextContent(/gateway offline/i)
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
})
