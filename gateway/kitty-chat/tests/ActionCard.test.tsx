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
    effective_risk_tier: 'T2' as const,
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
    vi.mocked(useApproveAction).mockReturnValue({ mutate: approve, isPending: false, isError: false, error: null } as never)
    vi.mocked(useRejectAction).mockReturnValue({ mutate: reject, isPending: false, isError: false, error: null } as never)
    vi.mocked(useExecuteAction).mockReturnValue({ mutate: execute, isPending: false, isError: false, error: null } as never)
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


  it('uses the current effective tier instead of the stale proposed tier', () => {
    vi.mocked(useAction).mockReturnValue({
      data: { ...action(), risk_tier: 'T0', effective_risk_tier: 'T2' },
      isLoading: false, isError: false,
    } as never)
    render(<ActionCard actionId={42} />)

    expect(screen.getByText('T2')).toBeInTheDocument()
    expect(screen.queryByText('T0')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Approve action' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reject action' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run approved action' })).not.toBeInTheDocument()
  })

  it('keeps Reject available for proposed T0/T1 actions', () => {
    vi.mocked(useAction).mockReturnValue({
      data: { ...action(), risk_tier: 'T0', effective_risk_tier: 'T0' },
      isLoading: false, isError: false,
    } as never)
    render(<ActionCard actionId={42} />)

    fireEvent.click(screen.getByRole('button', { name: 'Reject action' }))
    expect(reject).toHaveBeenCalledWith(42)
    expect(screen.getByRole('button', { name: 'Run approved action' })).toBeInTheDocument()
  })


  it('uses the current grant decision for proposed action controls', () => {
    vi.mocked(useAction).mockReturnValue({
      data: {
        ...action(), risk_tier: 'T0', effective_risk_tier: 'T0',
        execution_decision: { outcome: 'ask', basis: 'scoped_ask' },
      },
      isLoading: false, isError: false,
    } as never)
    render(<ActionCard actionId={42} />)

    expect(screen.getByRole('button', { name: 'Approve action' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reject action' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run approved action' })).not.toBeInTheDocument()
  })

  it('does not offer Run when a scoped grant denies the action', () => {
    vi.mocked(useAction).mockReturnValue({
      data: {
        ...action(), risk_tier: 'T0', effective_risk_tier: 'T0',
        execution_decision: { outcome: 'deny', basis: 'scoped_deny' },
      },
      isLoading: false, isError: false,
    } as never)
    render(<ActionCard actionId={42} />)

    expect(screen.getByRole('button', { name: 'Reject action' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve action' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run approved action' })).not.toBeInTheDocument()
  })

  it('surfaces failed action mutations instead of making a click look ignored', () => {
    vi.mocked(useAction).mockReturnValue({ data: action(), isLoading: false, isError: false } as never)
    vi.mocked(useApproveAction).mockReturnValue({
      mutate: approve, isPending: false, isError: true, error: new Error('Gateway returned 409 Conflict'),
    } as never)
    render(<ActionCard actionId={42} />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(/couldn|went wrong|conflict/i)
  })

  it('treats restart-reconciled unknown outcomes as terminal and unsafe', () => {
    vi.mocked(useAction).mockReturnValue({
      data: { ...action('unknown'), result: 'Gateway restarted mid-execution; outcome unknown.' },
      isLoading: false, isError: false,
    } as never)
    render(<ActionCard actionId={42} />)

    const status = screen.getByText('Unknown')
    expect(status).toHaveStyle({ color: 'var(--color-destructive)' })
    expect(screen.queryByRole('button', { name: /approve|reject|run/i })).not.toBeInTheDocument()
  })

  it('shows the durable result in the same card after execution', () => {
    vi.mocked(useAction).mockReturnValue({ data: action('executed'), isLoading: false, isError: false } as never)
    render(<ActionCard actionId={42} />)

    expect(screen.getByText('Calendar event created.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run approved action' })).not.toBeInTheDocument()
  })
})
