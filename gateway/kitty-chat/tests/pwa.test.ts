import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { type BeforeInstallPromptEvent, usePwaInstall } from '../src/lib/pwa'

describe('usePwaInstall', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    Reflect.deleteProperty(window.navigator, 'serviceWorker')
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
