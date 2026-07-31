import type { PropsWithChildren } from 'react'
import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { KittyRuntimeProvider } from '../src/components/KittyRuntimeProvider'

vi.mock('@assistant-ui/react', () => ({
  AssistantRuntimeProvider: ({ children }: PropsWithChildren) => <>{children}</>,
}))

vi.mock('@/lib/kitty-runtime', () => ({
  useKittyRuntime: vi.fn(() => ({})),
}))

const runtimeProps = {
  messages: [],
  isStreaming: false,
  activeModel: { id: 'kitty-default', name: 'Kitty', color: '#fff', glow: '#fff' },
  onSend: vi.fn(),
  onCancel: vi.fn(),
}

describe('KittyRuntimeProvider', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('recovers automatically after a transient gateway health failure', async () => {
    const abortError = new Error('aborted')
    abortError.name = 'AbortError'
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(abortError)
      .mockResolvedValueOnce({ ok: true })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <KittyRuntimeProvider {...runtimeProps}>
        <div>home ready</div>
      </KittyRuntimeProvider>,
    )

    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByText(/Gateway offline/)).toBeInTheDocument()

    await act(async () => {
      vi.advanceTimersByTime(5_000)
      await Promise.resolve()
    })

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(screen.getByText('home ready')).toBeInTheDocument()
  })
})
