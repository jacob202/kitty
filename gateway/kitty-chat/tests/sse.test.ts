import { renderHook, act } from '@testing-library/react'
import { StrictMode, createElement, type ReactNode } from 'react'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { useSSE } from '../src/lib/sse'

class FakeEventSource {
  static instances: FakeEventSource[] = []
  url: string
  closed = false
  onopen: ((e: Event) => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onerror: ((e: Event) => void) | null = null

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  close() {
    this.closed = true
  }

  emitOpen() {
    this.onopen?.(new Event('open'))
  }

  emitMessage(data: string) {
    this.onmessage?.({ data })
  }

  emitError() {
    this.onerror?.(new Event('error'))
  }

  static get open(): FakeEventSource[] {
    return FakeEventSource.instances.filter((i) => !i.closed)
  }

  static get latest(): FakeEventSource {
    return FakeEventSource.instances[FakeEventSource.instances.length - 1]
  }
}

describe('useSSE', () => {
  beforeEach(() => {
    FakeEventSource.instances = []
    vi.stubGlobal('EventSource', FakeEventSource)
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('opens one connection to the given URL and delivers messages', () => {
    const onMessage = vi.fn()
    renderHook(() => useSSE('/proxy/stream', onMessage))

    expect(FakeEventSource.open).toHaveLength(1)
    expect(FakeEventSource.latest.url).toBe('/proxy/stream')

    act(() => FakeEventSource.latest.emitMessage('state_updated'))
    expect(onMessage).toHaveBeenCalledWith('state_updated')
  })

  it('a throwing handler does not kill the stream', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const onMessage = vi
      .fn()
      .mockImplementationOnce(() => {
        throw new Error('malformed event')
      })
    renderHook(() => useSSE('/proxy/stream', onMessage))

    act(() => FakeEventSource.latest.emitMessage('garbage'))
    act(() => FakeEventSource.latest.emitMessage('state_updated'))

    expect(onMessage).toHaveBeenCalledTimes(2)
    expect(FakeEventSource.open).toHaveLength(1)
    expect(consoleError).toHaveBeenCalled()
  })

  it('reconnects after a dropped connection with a delay', () => {
    renderHook(() => useSSE('/proxy/stream', vi.fn()))
    const first = FakeEventSource.latest

    act(() => first.emitError())
    expect(first.closed).toBe(true)
    expect(FakeEventSource.instances).toHaveLength(1)

    act(() => vi.advanceTimersByTime(999))
    expect(FakeEventSource.instances).toHaveLength(1)
    act(() => vi.advanceTimersByTime(1))
    expect(FakeEventSource.instances).toHaveLength(2)
    expect(FakeEventSource.open).toHaveLength(1)
  })

  it('backs off exponentially on repeated failures and resets after a message', () => {
    renderHook(() => useSSE('/proxy/stream', vi.fn()))

    // First failure → 1000ms, second consecutive → 2000ms.
    act(() => FakeEventSource.latest.emitError())
    act(() => vi.advanceTimersByTime(1000))
    expect(FakeEventSource.instances).toHaveLength(2)
    act(() => FakeEventSource.latest.emitError())
    act(() => vi.advanceTimersByTime(1999))
    expect(FakeEventSource.instances).toHaveLength(2)
    act(() => vi.advanceTimersByTime(1))
    expect(FakeEventSource.instances).toHaveLength(3)

    // A delivered message marks the connection healthy → backoff resets.
    act(() => FakeEventSource.latest.emitMessage('state_updated'))
    act(() => FakeEventSource.latest.emitError())
    act(() => vi.advanceTimersByTime(1000))
    expect(FakeEventSource.instances).toHaveLength(4)
  })

  it('cleanup closes the connection and cancels pending reconnects', () => {
    const { unmount } = renderHook(() => useSSE('/proxy/stream', vi.fn()))

    act(() => FakeEventSource.latest.emitError())
    unmount()

    act(() => vi.advanceTimersByTime(60_000))
    expect(FakeEventSource.instances).toHaveLength(1)
    expect(FakeEventSource.open).toHaveLength(0)
  })

  it('closes the live connection on unmount', () => {
    const { unmount } = renderHook(() => useSSE('/proxy/stream', vi.fn()))
    expect(FakeEventSource.open).toHaveLength(1)
    unmount()
    expect(FakeEventSource.open).toHaveLength(0)
  })

  it('switches connections when the URL changes', () => {
    const { rerender } = renderHook(({ url }: { url: string }) => useSSE(url, vi.fn()), {
      initialProps: { url: '/proxy/stream' },
    })
    const first = FakeEventSource.latest

    rerender({ url: '/proxy/stream?session_id=abc' })

    expect(first.closed).toBe(true)
    expect(FakeEventSource.open).toHaveLength(1)
    expect(FakeEventSource.latest.url).toBe('/proxy/stream?session_id=abc')
  })

  it('does not open a connection for a null URL', () => {
    renderHook(() => useSSE(null, vi.fn()))
    expect(FakeEventSource.instances).toHaveLength(0)
  })

  it('settles to exactly one live connection under Strict Mode double-mounting', () => {
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(StrictMode, null, children)
    const { unmount } = renderHook(() => useSSE('/proxy/stream', vi.fn()), { wrapper })

    expect(FakeEventSource.open).toHaveLength(1)
    act(() => vi.advanceTimersByTime(60_000))
    expect(FakeEventSource.open).toHaveLength(1)

    unmount()
    expect(FakeEventSource.open).toHaveLength(0)
  })

  it('fires onOpen on every successful (re)connect so consumers can resync', () => {
    const onOpen = vi.fn()
    renderHook(() => useSSE('/proxy/stream', vi.fn(), onOpen))

    act(() => FakeEventSource.latest.emitOpen())
    expect(onOpen).toHaveBeenCalledTimes(1)

    act(() => FakeEventSource.latest.emitError())
    act(() => vi.advanceTimersByTime(1000))
    act(() => FakeEventSource.latest.emitOpen())
    expect(onOpen).toHaveBeenCalledTimes(2)
  })

  it('a throwing onOpen does not kill the stream', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const onMessage = vi.fn()
    const onOpen = vi.fn(() => {
      throw new Error('resync failed')
    })
    renderHook(() => useSSE('/proxy/stream', onMessage, onOpen))

    act(() => FakeEventSource.latest.emitOpen())
    act(() => FakeEventSource.latest.emitMessage('state_updated'))

    expect(onMessage).toHaveBeenCalledWith('state_updated')
    expect(consoleError).toHaveBeenCalled()
  })

  it('uses the latest handler without resubscribing', () => {
    const first = vi.fn()
    const second = vi.fn()
    const { rerender } = renderHook(
      ({ handler }: { handler: (d: string) => void }) => useSSE('/proxy/stream', handler),
      { initialProps: { handler: first } },
    )

    rerender({ handler: second })
    expect(FakeEventSource.instances).toHaveLength(1)

    act(() => FakeEventSource.latest.emitMessage('state_updated'))
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledWith('state_updated')
  })
})
