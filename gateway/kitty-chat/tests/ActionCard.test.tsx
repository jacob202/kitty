import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ActionCard } from '../src/components/chat/ActionCard'
import { useAction, useApproveAction, useExecuteAction, useRejectAction } from '../src/lib/queries'

vi.mock('../src/lib/queries', () => ({
  useAction: vi.fn(),
  useApproveAction: vi.fn(),
  useExecuteAction: vi.fn(),
  useRejectAction: vi.fn(),
}))

const approve = vi.fn()
const reject = vi.fn()
const execute = vi.fn()

function action(status = 'proposed') {
  return {
    id: 42,
    created_at: 1,
    source_kind: 'chat',
    source_id: 'message-7',
    kind: 'calendar.event.create',
    title: 'Schedule dentist',
    preview: 'Create a dentist appointment on September 3 at 2 PM.',
    payload: { title: 'Dentist', starts_at: '2026-09-03T14:00:00-06:00' },
    risk_tier: 'T2' as const,
    status,
    result: status === 'executed' ? 'Calendar event created.' : null,
    decided_at: null,
    executed_at: null,
  }
}

describe('ActionCard', () => {
  beforeEach(() => {
    approve.mockReset()
    reject.mockReset()
    execute.mockReset()
    vi.mocked(useApproveAction).mockReturnValue({ mutate: approve, isPending: false } as never)
    vi.mocked(useRejectAction).mockReturnValue({ mutate: reject, isPending: false } as never)
    vi.mocked(useExecuteAction).mockReturnValue({ mutate: execute, isPending: false } as never)
  })

  afterEach(cleanup)

  it('shows the exact durable payload before approval', () => {
    vi.mocked(useAction).mockReturnValue({ data: action(), isLoading: false, isError: false } as never)
    render(<ActionCard actionId={42} />)

    expect(screen.getByText('Schedule dentist')).toBeInTheDocument()
    expect(screen.getByText(/September 3 at 2 PM/)).toBeInTheDocument()
    expect(screen.getByText(/starts_at/)).toBeInTheDocument()
    expect(screen.getByText(/2026-09-03T14:00:00-06:00/)).toBeInTheDocument()
    expect(screen.getByText('T2')).toBeInTheDocument()
  })

  it('keeps approval and rejection attached to the proposed object', () => {
    vi.mocked(useAction).mockReturnValue({ data: action(), isLoading: false, isError: false } as never)
    render(<ActionCard actionId={42} />)

    fireEvent.click(screen.getByRole('button', { name: 'Approve action' }))
    fireEvent.click(screen.getByRole('button', { name: 'Reject action' }))

    expect(approve).toHaveBeenCalledWith(42)
    expect(reject).toHaveBeenCalledWith(42)
  })

  it('turns an approved action into an explicit run control', () => {
    vi.mocked(useAction).mockReturnValue({ data: action('approved'), isLoading: false, isError: false } as never)
    render(<ActionCard actionId={42} />)

    fireEvent.click(screen.getByRole('button', { name: 'Run approved action' }))
    expect(execute).toHaveBeenCalledWith(42)
    expect(screen.queryByRole('button', { name: 'Approve action' })).not.toBeInTheDocument()
  })

  it('shows the durable result in the same card after execution', () => {
    vi.mocked(useAction).mockReturnValue({ data: action('executed'), isLoading: false, isError: false } as never)
    render(<ActionCard actionId={42} />)

    expect(screen.getByText('Calendar event created.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run approved action' })).not.toBeInTheDocument()
  })
})
