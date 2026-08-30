import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WorkView from '../src/components/WorkView'

const { useWorkSnapshot, usePreflight } = vi.hoisted(() => ({
  useWorkSnapshot: vi.fn(),
  usePreflight: vi.fn(),
}))
vi.mock('../src/lib/work', () => ({ useWorkSnapshot, usePreflight }))

function readySnapshot() {
  return {
    schema_version: 1,
    observed_at: '2026-08-30T21:00:00Z',
    valid_until: '2099-01-01T00:00:00Z',
    source: { kind: 'builder', state: 'available' },
    counts: { total: 1, active: 0, paused: 0, failed: 0, blocked: 0, completed: 0, ready: 1, waiting: 0 },
    queue: null,
    item_limit: 50,
    total_items: 1,
    items: [{
      id: 'init-1', title: 'Preflight packet', state: 'ready',
      source: { kind: 'builder', initiative_id: 'init-1', packet_id: 'p1' },
      current_packet: { id: 'p1', title: 'P1', task_id: 'task-1', task_state: 'queued' },
      current_run: null, blocker: null, next_action: 'claim', evidence: {},
      data_quality: { state: 'complete', issues: [] }, updated_at: '2026-08-30T21:00:00Z',
    }],
  }
}

describe('WorkView preflight', () => {
  beforeEach(() => {
    useWorkSnapshot.mockReturnValue({ data: readySnapshot(), isPending: false, isError: false, error: null, refetch: vi.fn() })
    usePreflight.mockReturnValue({
      data: {
        action: 'run', route: 'free', estimated_cost_cad: 0,
        cost_basis: 'local estimate — not a provider invoice', reasons: [],
        packet: { initiative_id: 'init-1', packet_id: 'p1' },
        budget: { weekly_budget_cad: 6, remaining_cad: 6, within_budget: true, basis: 'local estimate' },
        eligibility: { state: 'eligible', blocked_by: [] }, data_quality: { state: 'complete', issues: [] },
      },
      isPending: false, isError: false,
    })
  })
  afterEach(cleanup)

  it('shows route and zero-cost estimate before a runnable packet starts', () => {
    render(<WorkView isMobile={false} />)
    expect(screen.getByTestId('preflight-banner')).toHaveTextContent('Preflight ready')
    expect(screen.getByTestId('preflight-banner')).toHaveTextContent('free')
    expect(screen.getByTestId('preflight-banner')).toHaveTextContent('CAD 0.0000 local estimate')
    expect(usePreflight).toHaveBeenCalledWith('init-1', 'p1')
  })
})
