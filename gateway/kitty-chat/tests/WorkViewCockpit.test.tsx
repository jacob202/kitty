import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WorkView from '../src/components/WorkView'

const { useWorkSnapshot, usePreflight, useSupervisor, useBuilderAction, proposeBuilderJob, approveBuilderJob } = vi.hoisted(() => ({
  useWorkSnapshot: vi.fn(), usePreflight: vi.fn(), useSupervisor: vi.fn(), useBuilderAction: vi.fn(),
  proposeBuilderJob: vi.fn(), approveBuilderJob: vi.fn(),
}))
vi.mock('../src/lib/work', () => ({ useWorkSnapshot, usePreflight, useSupervisor, useBuilderAction }))
vi.mock('../src/lib/gateway', () => ({ proposeBuilderJob, approveBuilderJob }))

function readySnapshot() {
  return {
    schema_version: 1, observed_at: '2026-08-30T21:00:00Z', valid_until: '2099-01-01T00:00:00Z',
    source: { kind: 'builder', state: 'available' },
    counts: { total: 1, active: 0, paused: 0, failed: 0, blocked: 0, completed: 0, ready: 1, waiting: 0 },
    queue: null, item_limit: 50, total_items: 1,
    items: [{ id: 'init-1', title: 'Preflight packet', state: 'ready', source: { kind: 'builder', initiative_id: 'init-1', packet_id: 'p1' }, current_packet: { id: 'p1', title: 'P1', task_id: 'task-1', task_state: 'queued' }, current_run: null, blocker: null, next_action: 'claim', evidence: {}, data_quality: { state: 'complete', issues: [] }, updated_at: '2026-08-30T21:00:00Z' }],
  }
}

function supervisor() {
  return { schema_version: 1, running: false, active_runs: [], eligible_now: 1, on_hold: 0, last_tick_at: null, next_run_at: null, lock_path: '/tmp/lock', scheduler_enabled: true, budget: {}, scheduler: { supported: true, installed: true, loaded: true, healthy: true, label: 'com.kitty.builder.supervisor', plist_path: '/tmp/supervisor.plist', start_interval_seconds: 900, run_at_load: true, last_exit_status: 0, pid: null, last_tick_at: null, next_run_at: null, reason: null } }
}

describe('WorkView recovery cockpit', () => {
  beforeEach(() => {
    proposeBuilderJob.mockReset(); approveBuilderJob.mockReset()
    useSupervisor.mockReturnValue({ data: supervisor(), isPending: false, isError: false })
    useBuilderAction.mockReturnValue({ mutate: vi.fn(), isPending: false })
    useWorkSnapshot.mockReturnValue({ data: readySnapshot(), isPending: false, isError: false, error: null, refetch: vi.fn() })
    usePreflight.mockReturnValue({ data: { action: 'run', route: 'free', estimated_cost_cad: 0, cost_basis: 'local estimate', reasons: [], packet: { initiative_id: 'init-1', packet_id: 'p1' }, budget: { weekly_budget_cad: 6, remaining_cad: 6, within_budget: true, basis: 'local estimate' }, eligibility: { state: 'eligible', blocked_by: [] }, data_quality: { state: 'complete', issues: [] } }, isPending: false, isError: false })
  })
  afterEach(cleanup)

  it('shows route and zero-cost estimate before a runnable packet starts', () => {
    render(<WorkView isMobile={false} />)
    expect(screen.getByTestId('preflight-banner')).toHaveTextContent('Preflight ready')
    expect(screen.getByTestId('preflight-banner')).toHaveTextContent('free')
    expect(screen.getByTestId('preflight-banner')).toHaveTextContent('CAD 0.0000 local estimate')
  })

  it('prepares a bounded proposal and requires an explicit send', async () => {
    proposeBuilderJob.mockResolvedValue({ ok: true, prepared_manifest: { manifest_version: 1 }, manifest_sha256: 'manifest-sha', expected_base_sha: 'base-sha', approval_nonce: 'nonce', warnings: [] })
    approveBuilderJob.mockResolvedValue({ ok: true, state: 'queued', mission_id: 'mission-1' })
    render(<WorkView isMobile={false} />)
    fireEvent.change(screen.getByLabelText('What should Builder do?'), { target: { value: 'Fix the Work button behavior' } })
    fireEvent.change(screen.getByLabelText('Allowed paths'), { target: { value: 'gateway/kitty-chat/src, gateway/kitty-chat/tests' } })
    fireEvent.click(screen.getByRole('button', { name: 'Prepare proposal' }))
    await waitFor(() => expect(screen.getByTestId('builder-proposal-preview')).toBeInTheDocument())
    expect(approveBuilderJob).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Send to Builder' }))
    await waitFor(() => expect(approveBuilderJob).toHaveBeenCalledOnce())
  })

  it('shows truthful scheduled Builder status without inventing timestamps', () => {
    render(<WorkView isMobile={false} />)
    const status = screen.getByTestId('builder-scheduler-status')
    expect(status).toHaveTextContent('Scheduled Builder: healthy')
    expect(status).toHaveTextContent('every 15 min')
    expect(status).toHaveTextContent('last tick time unavailable')
    expect(status).toHaveTextContent('next run time unavailable')
  })
})
