import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WorkView from '../src/components/WorkView'

const { useWorkSnapshot, usePreflight, useSupervisor, useBuilderAction, useCompileBuilderProposal, streamChat } = vi.hoisted(() => ({
  useWorkSnapshot: vi.fn(), usePreflight: vi.fn(), useSupervisor: vi.fn(), useBuilderAction: vi.fn(), useCompileBuilderProposal: vi.fn(), streamChat: vi.fn(),
}))
vi.mock('../src/lib/work', () => ({ useWorkSnapshot, usePreflight, useSupervisor, useBuilderAction }))
vi.mock('../src/lib/queries', () => ({ useCompileBuilderProposal }))
vi.mock('../src/lib/chat-client', () => ({
  streamChat,
  friendlyChatError: (error: unknown) => ({ kind: 'routing', userMessage: error instanceof Error ? error.message : 'routing failed' }),
}))
vi.mock('../src/components/builder/BuilderProposalCard', () => ({
  BuilderProposalCard: ({ task }: { task: { objective: string } }) => <div data-testid="work-builder-proposal">{task.objective}</div>,
}))

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
    useSupervisor.mockReturnValue({ data: supervisor(), isPending: false, isError: false })
    useBuilderAction.mockReturnValue({ mutate: vi.fn(), isPending: false })
    useWorkSnapshot.mockReturnValue({ data: readySnapshot(), isPending: false, isError: false, error: null, refetch: vi.fn() })
    useCompileBuilderProposal.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    usePreflight.mockReturnValue({ data: { action: 'run', route: 'free', estimated_cost_cad: 0, cost_basis: 'local estimate', reasons: [], packet: { initiative_id: 'init-1', packet_id: 'p1' }, budget: { weekly_budget_cad: 6, remaining_cad: 6, within_budget: true, basis: 'local estimate' }, eligibility: { state: 'eligible', blocked_by: [] }, data_quality: { state: 'complete', issues: [] } }, isPending: false, isError: false })
  })
  afterEach(cleanup)



  it('uses the lightweight Builder compiler instead of the full chat stream', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({
      ok: true,
      task: { objective: 'Add the proof file', instructions: 'Add it.', allowed_paths: ['rc0-builder-proof.txt'] },
    })
    useCompileBuilderProposal.mockReturnValue({ mutateAsync, isPending: false })
    streamChat.mockImplementation(() => { throw new Error('full chat stream must not be used') })
    render(<WorkView isMobile={false} />)

    fireEvent.change(screen.getByRole('textbox', { name: 'Ask Builder for work' }), { target: { value: 'Add the proof file.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Prepare Builder proposal' }))

    expect(await screen.findByTestId('work-builder-proposal')).toHaveTextContent('Add the proof file')
    expect(mutateAsync).toHaveBeenCalledWith({ request: 'Add the proof file.' })
    expect(streamChat).not.toHaveBeenCalled()
    expect(screen.queryByText(/phi3:mini/i)).not.toBeInTheDocument()
  })

  it('turns an ordinary-language Work request into the existing bounded Builder proposal card', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({
      ok: true,
      task: { objective: 'Add the proof file', instructions: 'Add the requested proof file.', allowed_paths: ['rc0-builder-proof.txt'] },
    })
    useCompileBuilderProposal.mockReturnValue({ mutateAsync, isPending: false })
    render(<WorkView isMobile={false} />)

    fireEvent.change(screen.getByRole('textbox', { name: 'Ask Builder for work' }), { target: { value: 'Add the proof file.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Prepare Builder proposal' }))

    expect(await screen.findByTestId('work-builder-proposal')).toHaveTextContent('Add the proof file')
    expect(screen.getByText(/execution route and spend are shown by Builder/i)).toBeInTheDocument()
  })

  it('keeps a failed Work request editable and offers an inline retry', async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error('The selected provider is unavailable.'))
    useCompileBuilderProposal.mockReturnValue({ mutateAsync, isPending: false })
    render(<WorkView isMobile={false} />)

    const request = screen.getByRole('textbox', { name: 'Ask Builder for work' })
    fireEvent.change(request, { target: { value: 'Fix the launch bug.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Prepare Builder proposal' }))

    expect(await screen.findByText(/could not prepare the proposal/i)).toBeInTheDocument()
    expect(screen.queryByText('The selected provider is unavailable.')).not.toBeInTheDocument()
    expect(request).toHaveValue('Fix the launch bug.')
    expect(screen.getByRole('button', { name: 'Try preparing again' })).toBeEnabled()
  })

  it('shows route and zero-cost estimate before a runnable packet starts', () => {
    render(<WorkView isMobile={false} />)
    expect(screen.getByTestId('preflight-banner')).toHaveTextContent('Preflight ready')
    expect(screen.getByTestId('preflight-banner')).toHaveTextContent('free')
    expect(screen.getByTestId('preflight-banner')).toHaveTextContent('CAD 0.0000 local estimate')
  })

  it('shows truthful scheduled Builder status without inventing timestamps', () => {
    render(<WorkView isMobile={false} />)
    const status = screen.getByTestId('builder-scheduler-status')
    expect(status).toHaveTextContent('Scheduled Builder: healthy')
    expect(status).toHaveTextContent('every 15 min')
    expect(status).toHaveTextContent('last tick time unavailable')
    expect(status).toHaveTextContent('next run time unavailable')
  })

  it('offers an explicit one-proposal alternate-model recovery without replacing the saved route', async () => {
    const mutateAsync = vi.fn()
      .mockResolvedValueOnce({ ok: false, error: 'The selected provider did not accept this request.' })
      .mockResolvedValueOnce({
        ok: true,
        task: { objective: 'Fix launch', instructions: 'Fix the launch bug.', allowed_paths: ['gateway/launcher.py'] },
        routing: { mode: 'request_scoped_fallback', saved_preference_changed: false },
      })
    useCompileBuilderProposal.mockReturnValue({ mutateAsync, isPending: false })
    render(<WorkView isMobile={false} />)

    const request = screen.getByRole('textbox', { name: 'Ask Builder for work' })
    fireEvent.change(request, { target: { value: 'Fix the launch bug.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Prepare Builder proposal' }))

    expect(await screen.findByRole('button', { name: 'Try another available model' })).toBeInTheDocument()
    expect(request).toHaveValue('Fix the launch bug.')
    fireEvent.click(screen.getByRole('button', { name: 'Try another available model' }))

    expect(await screen.findByTestId('work-builder-proposal')).toHaveTextContent('Fix launch')
    expect(mutateAsync).toHaveBeenNthCalledWith(1, { request: 'Fix the launch bug.' })
    expect(mutateAsync).toHaveBeenNthCalledWith(2, { request: 'Fix the launch bug.', allow_provider_fallback: true })
  })

})
