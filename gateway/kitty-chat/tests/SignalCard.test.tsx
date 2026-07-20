import { render, screen, cleanup, fireEvent, waitFor, act } from '@testing-library/react'
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { SignalFeed, SignalCard } from '../src/components/SignalCard'
import * as sse from '../src/lib/sse'
import type { ExpertSignal } from '../src/lib/types'

vi.mock('../src/lib/sse', async () => {
  const actual = await vi.importActual<typeof sse>('../src/lib/sse')
  return {
    ...actual,
    useSSE: vi.fn(),
    fetchExpertSignals: vi.fn(),
    dismissExpertSignal: vi.fn(),
  }
})

const useSSE = vi.mocked(sse.useSSE)
const fetchExpertSignals = vi.mocked(sse.fetchExpertSignals)
const dismissExpertSignal = vi.mocked(sse.dismissExpertSignal)

function makeSignal(overrides: Partial<ExpertSignal> = {}): ExpertSignal {
  return {
    id: 1,
    ts: 1_784_505_600,
    source: 'expert.benefits',
    kind: 'expert.suggestion',
    payload: {
      headline: 'SGI deadline is Friday',
      action: 'Book the road test today',
      analysis: 'The paperwork window closes this week.',
      topic_hash: 'abc123',
    },
    ...overrides,
  }
}

/** The stream handler SignalFeed registered with useSSE on its last render. */
function streamHandler(): (data: string) => void {
  const calls = useSSE.mock.calls
  return calls[calls.length - 1][1]
}

describe('SignalFeed', () => {
  beforeEach(() => {
    useSSE.mockReset()
    fetchExpertSignals.mockReset()
    dismissExpertSignal.mockReset()
  })
  afterEach(cleanup)

  it('renders fetched suggestion signals as cards', async () => {
    fetchExpertSignals.mockResolvedValue([makeSignal()])
    render(<SignalFeed />)

    expect(await screen.findByText('SGI deadline is Friday')).toBeInTheDocument()
    expect(screen.getByText('signal · benefits')).toBeInTheDocument()
    expect(screen.getByText('The paperwork window closes this week.')).toBeInTheDocument()
    expect(useSSE).toHaveBeenCalledWith(
      '/proxy/stream',
      expect.any(Function),
      expect.any(Function),
    )
  })

  it('renders nothing when there are no signals', async () => {
    fetchExpertSignals.mockResolvedValue([])
    const { container } = render(<SignalFeed />)

    await waitFor(() => expect(fetchExpertSignals).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('filters out non-suggestion signal kinds', async () => {
    fetchExpertSignals.mockResolvedValue([
      makeSignal(),
      makeSignal({ id: 2, kind: 'expert.evaluation', payload: { headline: 'internal bookkeeping' } }),
      makeSignal({ id: 3, kind: 'expert.error', payload: { headline: 'crash report' } }),
    ])
    render(<SignalFeed />)

    expect(await screen.findByText('SGI deadline is Friday')).toBeInTheDocument()
    expect(screen.queryByText('internal bookkeeping')).not.toBeInTheDocument()
    expect(screen.queryByText('crash report')).not.toBeInTheDocument()
  })

  it('shows a new signal live when the stream announces a state update', async () => {
    fetchExpertSignals.mockResolvedValueOnce([])
    render(<SignalFeed />)
    await waitFor(() => expect(fetchExpertSignals).toHaveBeenCalledTimes(1))
    expect(screen.queryByText('SGI deadline is Friday')).not.toBeInTheDocument()

    fetchExpertSignals.mockResolvedValueOnce([makeSignal()])
    act(() => streamHandler()('state_updated'))

    expect(await screen.findByText('SGI deadline is Friday')).toBeInTheDocument()
    expect(fetchExpertSignals).toHaveBeenCalledTimes(2)
  })

  it('resyncs signals when the stream (re)connects', async () => {
    fetchExpertSignals.mockResolvedValueOnce([])
    render(<SignalFeed />)
    await waitFor(() => expect(fetchExpertSignals).toHaveBeenCalledTimes(1))

    // A signal emitted while the connection was down broadcasts nothing the
    // client can hear — the reconnect open is the catch-up trigger.
    fetchExpertSignals.mockResolvedValueOnce([makeSignal({ payload: { headline: 'missed while offline', topic_hash: 'x' } })])
    const onOpen = useSSE.mock.calls[useSSE.mock.calls.length - 1][2]
    act(() => onOpen?.())

    expect(await screen.findByText('missed while offline')).toBeInTheDocument()
  })

  it('ignores stream messages that are not state updates', async () => {
    fetchExpertSignals.mockResolvedValue([])
    render(<SignalFeed />)
    await waitFor(() => expect(fetchExpertSignals).toHaveBeenCalledTimes(1))

    act(() => streamHandler()('{}'))
    act(() => streamHandler()('unrelated-broadcast'))

    expect(fetchExpertSignals).toHaveBeenCalledTimes(1)
  })

  it('does not duplicate cards when the same signals are delivered again', async () => {
    fetchExpertSignals.mockResolvedValue([makeSignal()])
    render(<SignalFeed />)
    await screen.findByText('SGI deadline is Friday')

    act(() => streamHandler()('state_updated'))
    act(() => streamHandler()('state_updated'))

    await waitFor(() => expect(fetchExpertSignals).toHaveBeenCalledTimes(3))
    expect(screen.getAllByText('SGI deadline is Friday')).toHaveLength(1)
  })

  it('keeps the chat alive when the signal fetch fails', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    fetchExpertSignals.mockRejectedValue(new Error('Gateway returned 500 for expert signals'))
    const { container } = render(<SignalFeed />)

    await waitFor(() => expect(consoleError).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
    consoleError.mockRestore()
  })

  it('dismisses a signal through the gateway and removes its card', async () => {
    fetchExpertSignals.mockResolvedValue([makeSignal(), makeSignal({ id: 2, payload: { headline: 'second signal', topic_hash: 'x' } })])
    dismissExpertSignal.mockResolvedValue(undefined)
    render(<SignalFeed />)
    await screen.findByText('SGI deadline is Friday')

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss signal: SGI deadline is Friday' }))

    await waitFor(() => {
      expect(screen.queryByText('SGI deadline is Friday')).not.toBeInTheDocument()
    })
    expect(dismissExpertSignal).toHaveBeenCalledWith(1)
    expect(screen.getByText('second signal')).toBeInTheDocument()
  })

  it('keeps the card and reports the error when dismissal fails', async () => {
    fetchExpertSignals.mockResolvedValue([makeSignal()])
    dismissExpertSignal.mockRejectedValue(new Error('Gateway returned 400 dismissing signal 1'))
    render(<SignalFeed />)
    await screen.findByText('SGI deadline is Friday')

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss signal: SGI deadline is Friday' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('400')
    expect(screen.getByText('SGI deadline is Friday')).toBeInTheDocument()
  })
})

describe('SignalCard', () => {
  afterEach(cleanup)

  it('shows title, body, source expert, timestamp, and an accessible dismiss control', () => {
    const signal = makeSignal()
    render(<SignalCard signal={signal} onDismiss={vi.fn(async () => {})} />)

    expect(screen.getByText('SGI deadline is Friday')).toBeInTheDocument()
    expect(screen.getByText('The paperwork window closes this week.')).toBeInTheDocument()
    expect(screen.getByText('signal · benefits')).toBeInTheDocument()
    const expectedTime = new Date(signal.ts * 1000).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    })
    expect(screen.getByText(expectedTime)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Dismiss signal: SGI deadline is Friday' }),
    ).toBeInTheDocument()
  })

  it('falls back to the action line when a signal has no analysis', () => {
    render(
      <SignalCard
        signal={makeSignal({ payload: { headline: 'h', action: 'do the thing' } })}
        onDismiss={vi.fn(async () => {})}
      />,
    )
    expect(screen.getByText('do the thing')).toBeInTheDocument()
  })

  it('blocks repeated dismiss taps while one is in flight', async () => {
    let resolveDismiss: () => void = () => {}
    const onDismiss = vi.fn(
      () => new Promise<void>((resolve) => { resolveDismiss = resolve }),
    )
    render(<SignalCard signal={makeSignal()} onDismiss={onDismiss} />)

    const btn = screen.getByRole('button', { name: /Dismiss signal/ })
    fireEvent.click(btn)
    fireEvent.click(btn)
    fireEvent.click(btn)

    expect(onDismiss).toHaveBeenCalledTimes(1)
    expect(btn).toBeDisabled()
    resolveDismiss()
  })
})
