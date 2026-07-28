import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, afterEach, vi, beforeEach } from 'vitest'
import type { Mock } from 'vitest'
import { useInsightLoopDue, useRespondToLoopInsight } from '../src/lib/queries'
import { InsightReturnCard } from '../src/components/InsightReturnCard'
import type { GatewayLoopInsight } from '../src/lib/gateway'

vi.mock('../src/lib/queries', () => ({
  useInsightLoopDue: vi.fn(),
  useRespondToLoopInsight: vi.fn(),
}))

function makeInsight(id: number, summary: string, returnedCount = 0): GatewayLoopInsight {
  return {
    id,
    object_type: 'insight',
    source_ref: null,
    user_review: 'approved',
    payload: {
      summary,
      category: 'task',
      return_policy: 'next_brief',
      return_at: null,
      status: 'returned',
      returned_count: returnedCount,
      last_returned_at: null,
      action_id: null,
      outcome: null,
    },
  }
}

describe('InsightReturnCard', () => {
  beforeEach(() => {
    ;(useRespondToLoopInsight as Mock).mockReturnValue({
      mutateAsync: vi.fn().mockResolvedValue({}),
    })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('renders nothing when nothing is due', () => {
    ;(useInsightLoopDue as Mock).mockReturnValue({ data: [], isPending: false, isError: false })
    const { container } = render(<InsightReturnCard />)
    expect(container).toBeEmptyDOMElement()
  })

  it('lists due insights with their summaries', () => {
    ;(useInsightLoopDue as Mock).mockReturnValue({
      data: [makeInsight(1, 'book the elevator'), makeInsight(2, 'renew the lease', 2)],
      isPending: false,
      isError: false,
    })
    render(<InsightReturnCard />)
    expect(screen.getByText('back to you')).toBeInTheDocument()
    expect(screen.getByText('book the elevator')).toBeInTheDocument()
    expect(screen.getByText('renew the lease')).toBeInTheDocument()
    expect(screen.getByText('surfaced 2×')).toBeInTheDocument()
  })

  it('acts on an insight', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({})
    ;(useRespondToLoopInsight as Mock).mockReturnValue({ mutateAsync })
    ;(useInsightLoopDue as Mock).mockReturnValue({
      data: [makeInsight(7, 'pay the deposit')],
      isPending: false,
      isError: false,
    })
    render(<InsightReturnCard />)
    fireEvent.click(screen.getByRole('button', { name: /act on: pay the deposit/i }))
    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({ itemId: 7, choice: 'act' })
    })
  })

  it('snoozes with an ISO datetime', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({})
    ;(useRespondToLoopInsight as Mock).mockReturnValue({ mutateAsync })
    ;(useInsightLoopDue as Mock).mockReturnValue({
      data: [makeInsight(8, 'call the mover')],
      isPending: false,
      isError: false,
    })
    render(<InsightReturnCard />)
    fireEvent.click(screen.getByRole('button', { name: /snooze until tomorrow: call the mover/i }))
    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalled()
    })
    const arg = mutateAsync.mock.calls[0][0]
    expect(arg.itemId).toBe(8)
    expect(arg.choice).toBe('snooze')
    expect(new Date(arg.snoozeUntil).getTime()).toBeGreaterThan(Date.now())
  })

  it('archives with the default reason', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({})
    ;(useRespondToLoopInsight as Mock).mockReturnValue({ mutateAsync })
    ;(useInsightLoopDue as Mock).mockReturnValue({
      data: [makeInsight(9, 'old thought')],
      isPending: false,
      isError: false,
    })
    render(<InsightReturnCard />)
    fireEvent.click(screen.getByRole('button', { name: /archive: old thought/i }))
    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        itemId: 9,
        choice: 'archive',
        archiveReason: 'not_useful',
      })
    })
  })

  it('surfaces a respond failure instead of swallowing it', async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error('Gateway returned 500'))
    ;(useRespondToLoopInsight as Mock).mockReturnValue({ mutateAsync })
    ;(useInsightLoopDue as Mock).mockReturnValue({
      data: [makeInsight(10, 'failing item')],
      isPending: false,
      isError: false,
    })
    render(<InsightReturnCard />)
    fireEvent.click(screen.getByRole('button', { name: /act on: failing item/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Gateway returned 500')
  })

  it('shows an error card when the gateway is unreachable', () => {
    ;(useInsightLoopDue as Mock).mockReturnValue({ data: undefined, isPending: false, isError: true })
    render(<InsightReturnCard />)
    expect(screen.getByRole('alert')).toHaveTextContent('insight loop unavailable')
  })
})
