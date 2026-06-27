import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PwaInstallBanner } from '../src/components/PwaInstallBanner'
import {
  type BeforeInstallPromptEvent,
  usePwaInstall,
} from '../src/lib/pwa'

describe('PwaInstallBanner', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    Reflect.deleteProperty(window.navigator, 'serviceWorker')
  })

  it('renders an install button when the browser can install the app', () => {
    const onInstall = vi.fn()

    render(<PwaInstallBanner state="available" onInstall={onInstall} />)

    fireEvent.click(screen.getByRole('button', { name: 'install' }))
    expect(onInstall).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/dock launch/i)).toBeInTheDocument()
  })

  it('renders manual iOS instructions when beforeinstallprompt is unavailable', () => {
    render(<PwaInstallBanner state="manual-ios" />)

    const banner = screen.getByRole('status')

    expect(screen.getByText(/Add to Home Screen/i)).toBeInTheDocument()
    expect(banner.querySelector('button')).toBeNull()
  })

  it('renders a visible error when install setup fails', () => {
    render(<PwaInstallBanner state="error" error="Service worker registration failed: boom" />)

    expect(screen.getByRole('alert')).toHaveTextContent('Service worker registration failed: boom')
  })

  it('renders nothing when install chrome should stay hidden', () => {
    const { container } = render(<PwaInstallBanner state="hidden" />)
    expect(container.firstChild).toBeNull()
  })

  it('hides a one-shot browser prompt after the user dismisses it', async () => {
    const media = {
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }
    vi.stubGlobal('matchMedia', vi.fn(() => media))
    Object.defineProperty(window.navigator, 'serviceWorker', {
      configurable: true,
      value: { register: vi.fn().mockResolvedValue({}) },
    })

    const promptEvent = Object.assign(new Event('beforeinstallprompt'), {
      prompt: vi.fn().mockResolvedValue(undefined),
      userChoice: Promise.resolve({ outcome: 'dismissed' as const, platform: 'web' }),
    }) as BeforeInstallPromptEvent
    const { result } = renderHook(() => usePwaInstall())

    act(() => window.dispatchEvent(promptEvent))
    await waitFor(() => expect(result.current.state).toBe('available'))

    await act(async () => result.current.install())

    expect(promptEvent.prompt).toHaveBeenCalledTimes(1)
    expect(result.current.state).toBe('hidden')
  })
})
