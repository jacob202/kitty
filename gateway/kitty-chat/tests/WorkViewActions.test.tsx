import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WorkView, { rowAction, type RowAction } from '../src/components/WorkView'
import type { GatewayWorkItem } from '../src/lib/work'

const { useWorkSnapshot, usePreflight, useSupervisor, useBuilderAction, useCompileBuilderProposal, mutate } = vi.hoisted(() => ({
  useWorkSnapshot: vi.fn(),
  usePreflight: vi.fn(),
  useSupervisor: vi.fn(),
  useBuilderAction: vi.fn(),
  useCompileBuilderProposal: vi.fn(),
  mutate: vi.fn(),
}))
vi.mock('../src/lib/work', () => ({ useWorkSnapshot, usePreflight, useSupervisor, useBuilderAction }))
vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof import('../src/lib/queries')>('../src/lib/queries')
  return { ...actual, useCompileBuilderProposal }
})

function item(overrides: Partial<GatewayWorkItem> = {}): GatewayWorkItem {
  return {
    id: 'PUBLIC-GOLDEN-PATH-001',
    title: 'Kitty public golden path reliability gate',
    state: 'blocked',
    source: { kind: 'builder', initiative_id: 'PUBLIC-GOLDEN-PATH-001', packet_id: 'PGP-001' },
    current_packet: { id: 'PGP-001', title: 'CI parity', task_id: 'kb_task_1', task_state: 'blocked' },
    current_run: null,
    blocker: null,
    next_action: 'recover',
    evidence: {},
    data_quality: { state: 'complete', issues: [] },
    updated_at: '2026-08-15T13:13:45Z',
    ...overrides,
  } as GatewayWorkItem
}

function snapshot(items: GatewayWorkItem[]) {
  return {
    schema_version: 1,
    observed_at: '2026-08-30T05:00:00Z',
    valid_until: '2099-01-01T00:00:00Z',
    source: { kind: 'builder', state: 'available' },
    counts: { total: items.length, active: 0, paused: 0, failed: 0, blocked: items.length, completed: 0, ready: 0, waiting: 0 },
    queue: null,
    item_limit: 50,
    total_items: items.length,
    items,
  }
}

function supervisor(overrides: Record<string, unknown> = {}) {
  return {
    schema_version: 1,
    running: false,
    active_runs: [],
    eligible_now: 1,
    on_hold: 9,
    last_tick_at: null,
    lock_path: '/tmp/supervisor.lock',
    scheduler_enabled: false,
    ...overrides,
  }
}

function renderWork(items: GatewayWorkItem[], supervisorData = supervisor()) {
  useWorkSnapshot.mockReturnValue({ data: snapshot(items), isPending: false, isError: false, error: null, refetch: vi.fn() })
  useSupervisor.mockReturnValue({ data: supervisorData, isPending: false, isError: false, error: null })
  useBuilderAction.mockReturnValue({ mutate, isPending: false })
  render(<WorkView isMobile={false} />)
}

beforeEach(() => {
  useWorkSnapshot.mockReset()
  usePreflight.mockReset()
  usePreflight.mockReturnValue({ data: null, isPending: false, isError: false })
  useSupervisor.mockReset()
  useBuilderAction.mockReset()
  useCompileBuilderProposal.mockReset()
  useCompileBuilderProposal.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
  mutate.mockReset()
  vi.stubGlobal('confirm', vi.fn(() => true))
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('rowAction mapping', () => {
  it('offers a retry for work Builder can pick back up', () => {
    const action = rowAction(item({ next_action: 'recover' }), false)
    expect(action).toMatchObject({
      kind: 'command',
      label: 'Try again',
      command: { action: 'requeue', task_id: 'kb_task_1' },
    })
  })

  it('offers to resume the project when the whole initiative is on hold', () => {
    const action = rowAction(item({ state: 'paused', next_action: 'recover' }), false)
    expect(action).toMatchObject({
      kind: 'command',
      label: 'Resume this project',
      command: { action: 'resume', initiative_id: 'PUBLIC-GOLDEN-PATH-001' },
    })
  })

  it('grants exactly one additional attempt when automatic retries are exhausted', () => {
    const action = rowAction(item({ next_action: 'exhausted' }), false)
    expect(action).toMatchObject({
      kind: 'command',
      label: 'Allow one more try',
      command: { action: 'grant_attempt', initiative_id: 'PUBLIC-GOLDEN-PATH-001', packet_id: 'PGP-001' },
    })
  })

  it('never starts global Builder work from a row when Builder is not scheduled', () => {
    const action = rowAction(item({ next_action: 'claim' }), false, false)
    expect(action.kind).toBe('none')
    expect((action as Extract<RowAction, { kind: 'none' }>).explanation).toMatch(/global pass/i)
  })

  it('does not invent a scheduler state when Builder status is unknown', () => {
    const action = rowAction(item({ next_action: 'claim' }), false, null)
    expect(action.kind).toBe('none')
    expect((action as Extract<RowAction, { kind: 'none' }>).explanation).toMatch(/can't verify/i)
  })

  it('explains Builder is idle for ready work when the scheduler is enabled', () => {
    const action = rowAction(item({ next_action: 'claim' }), false, true)
    expect(action).toMatchObject({ kind: 'none' })
    expect((action as Extract<RowAction, { kind: 'none' }>).explanation).toMatch(/idle.*scheduled/i)
  })

  it('explains the wait instead of offering a button once Builder is running', () => {
    const action = rowAction(item({ next_action: 'claim' }), true)
    expect(action).toMatchObject({ kind: 'none' })
    expect((action as Extract<RowAction, { kind: 'none' }>).explanation).toMatch(/pick it up/i)
  })

  it('refuses to offer a retry it cannot actually send', () => {
    const action = rowAction(item({ next_action: 'recover', current_packet: null }), false)
    expect(action.kind).toBe('none')
    expect((action as Extract<RowAction, { kind: 'none' }>).explanation).toMatch(/cannot retry/i)
  })

  it.each([
    ['cancelled', /was cancelled/i],
    ['done', /finished/i],
    ['await_review', /review/i],
  ])('explains why %s work has no action', (nextAction, expected) => {
    const action = rowAction(item({ next_action: nextAction }), false)
    expect(action.kind).toBe('none')
    expect((action as Extract<RowAction, { kind: 'none' }>).explanation).toMatch(expected)
  })

  // Jacob's rule: information with no action attached is a defect. Every row
  // must resolve to something the user can press or a sentence saying why not.
  it('never leaves a row with neither an action nor an explanation', () => {
    const nextActions = ['recover', 'exhausted', 'claim', 'await_review', 'cancelled', 'done', 'something_new', null]
    for (const nextAction of nextActions) {
      for (const running of [true, false]) {
        const action = rowAction(item({ next_action: nextAction }), running)
        if (action.kind === 'none') expect(action.explanation.length).toBeGreaterThan(0)
        else expect(action.label.length).toBeGreaterThan(0)
      }
    }
  })
})

describe('Builder run banner', () => {
  it('says Builder is idle when scheduler is enabled but nothing is running', () => {
    renderWork([item()], supervisor({ scheduler_enabled: true }))
    expect(screen.getByText('Builder is idle.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run ready work now' })).not.toBeInTheDocument()
  })

  it('says Builder is not scheduled when the scheduler is disabled', () => {
    renderWork([item()], supervisor())
    expect(screen.getByText('Builder is not scheduled.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run ready work now' })).toBeEnabled()
  })

  it('explains what is ready and what is waiting on a paused project', () => {
    renderWork([item()], supervisor())
    expect(screen.getByText(/1 job is ready to run/)).toBeInTheDocument()
    expect(screen.getByText(/9 more are on hold until their project is resumed/)).toBeInTheDocument()
  })

  it('confirms before starting Builder without promising a free execution route', () => {
    renderWork([item()], supervisor())
    fireEvent.click(screen.getByRole('button', { name: 'Run ready work now' }))
    expect(globalThis.confirm).toHaveBeenCalledWith(expect.stringMatching(/current Builder routing and spend policy/i))
    expect(globalThis.confirm).not.toHaveBeenCalledWith(expect.stringMatching(/free Builder runs/i))
    expect(mutate).toHaveBeenCalledWith('tick', expect.anything())
  })

  it('describes the global pass as policy-controlled before running it', () => {
    renderWork([item()], supervisor())
    fireEvent.click(screen.getByRole('button', { name: 'Run ready work now' }))
    expect(globalThis.confirm).toHaveBeenCalledWith(expect.stringMatching(/may start up to two Builder runs/i))
    expect(globalThis.confirm).toHaveBeenCalledWith(expect.stringMatching(/current Builder routing and spend policy/i))
  })

  it('does not start Builder when the user declines the confirmation', () => {
    vi.stubGlobal('confirm', vi.fn(() => false))
    renderWork([item()], supervisor())
    fireEvent.click(screen.getByRole('button', { name: 'Run ready work now' }))
    expect(mutate).not.toHaveBeenCalled()
  })

  it('cannot be started when there is nothing it could actually run', () => {
    renderWork([item()], supervisor({ eligible_now: 0 }))
    expect(screen.getByRole('button', { name: 'Run ready work now' })).toBeDisabled()
  })

  it('reports that Builder is working instead of offering to start it', () => {
    renderWork([item({ next_action: 'claim' })], supervisor({ running: true, active_runs: [{ id: 'run_1' }], scheduler_enabled: true }))
    expect(screen.getByText('Builder is working.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run ready work now' })).not.toBeInTheDocument()
  })

  it('keeps a global pass available while Builder is working when scheduling is off and capacity remains', () => {
    renderWork([item({ next_action: 'claim' })], supervisor({
      running: true,
      active_runs: [{ id: 'run_1' }],
      scheduler_enabled: false,
      eligible_now: 1,
    }))
    expect(screen.getByText('Builder is working.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run ready work now' })).toBeEnabled()
  })

  it('shows unknown status when the supervisor query has not resolved', () => {
    const unknownSupervisor = { data: undefined, isPending: true, isError: false, error: null }
    useSupervisor.mockReturnValue(unknownSupervisor)
    useWorkSnapshot.mockReturnValue({ data: snapshot([item()]), isPending: false, isError: false, error: null, refetch: vi.fn() })
    useBuilderAction.mockReturnValue({ mutate, isPending: false })
    render(<WorkView isMobile={false} />)
    expect(screen.getByText('Builder status is unknown.')).toBeInTheDocument()
    expect(screen.getByText(/Could not reach Builder's supervisor/)).toBeInTheDocument()
  })

  it('shows unknown status when the supervisor query failed', () => {
    const failedSupervisor = { data: undefined, isPending: false, isError: true, error: new Error('offline'), refetch: vi.fn() }
    useSupervisor.mockReturnValue(failedSupervisor)
    useWorkSnapshot.mockReturnValue({ data: snapshot([item()]), isPending: false, isError: false, error: null, refetch: vi.fn() })
    useBuilderAction.mockReturnValue({ mutate, isPending: false })
    render(<WorkView isMobile={false} />)
    expect(screen.getByText('Builder status is unknown.')).toBeInTheDocument()
    expect(screen.getByText(/Could not reach Builder's supervisor/)).toBeInTheDocument()
  })
})

describe('independent cancellation', () => {
  it('renders Cancel task even when there is no primary row action', () => {
    renderWork([item({ state: 'active', next_action: 'await_review' })])
    expect(screen.getByRole('button', { name: 'Cancel task' })).toBeEnabled()
  })
})

describe('row actions', () => {
  it('sends a requeue when the user retries blocked work', () => {
    renderWork([item({ next_action: 'recover' })])
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'requeue', task_id: 'kb_task_1' }),
      expect.anything(),
    )
  })

  it('grants a new attempt rather than requeueing exhausted work', () => {
    renderWork([item({ next_action: 'exhausted' })])
    fireEvent.click(screen.getByRole('button', { name: 'Allow one more try' }))
    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'grant_attempt', initiative_id: 'PUBLIC-GOLDEN-PATH-001', packet_id: 'PGP-001' }),
      expect.anything(),
    )
  })

  it('confirms before cancelling, then sends the cancel', () => {
    renderWork([item({ next_action: 'recover' })])
    fireEvent.click(screen.getByRole('button', { name: 'Cancel task' }))
    expect(globalThis.confirm).toHaveBeenCalled()
    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'cancel', task_id: 'kb_task_1' }),
      expect.anything(),
    )
  })

  it('keeps cancellation available even when there is no primary action', () => {
    renderWork([item({ next_action: 'await_review', state: 'in_progress' })])
    expect(screen.getByText(/waiting for a review/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel task' })).toBeEnabled()
  })

  it('offers no cancel for work that already finished', () => {
    renderWork([item({ next_action: 'done', state: 'completed' })])
    expect(screen.queryByRole('button', { name: 'Cancel task' })).not.toBeInTheDocument()
    expect(screen.getByText(/this one is finished/i)).toBeInTheDocument()
  })

  it.each(['running', 'pr_opened'])('hides cancellation when task state %s rejects operator cancel', taskState => {
    renderWork([item({
      state: 'active',
      next_action: 'await_review',
      current_packet: { id: 'PGP-001', title: 'CI parity', task_id: 'kb_task_1', task_state: taskState },
    })])
    expect(screen.queryByRole('button', { name: 'Cancel task' })).not.toBeInTheDocument()
  })

  it('shows Builder’s refusal in plain words instead of silently doing nothing', () => {
    mutate.mockImplementation((_command: unknown, handlers: { onSuccess: (r: unknown) => void }) => {
      handlers.onSuccess({ ok: false, error: 'task not found: kb_task_1' })
    })
    renderWork([item({ next_action: 'recover' })])
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(screen.getByRole('status')).toHaveTextContent('task not found: kb_task_1')
  })

  it('gives every visible row an action or a stated reason there is none', () => {
    renderWork([
      item({ id: 'a', next_action: 'recover' }),
      item({ id: 'b', next_action: 'claim' }),
      item({ id: 'c', next_action: 'cancelled' }),
      item({ id: 'd', state: 'paused', next_action: 'recover' }),
    ])
    const rows = screen.getAllByTestId('work-row')
    expect(rows).toHaveLength(4)
    for (const row of rows) {
      const action = within(row).queryByTestId('row-action')
      const noAction = within(row).queryByTestId('row-no-action')
      expect(Boolean(action) || Boolean(noAction)).toBe(true)
      if (action) expect(within(action).getAllByRole('button').length).toBeGreaterThan(0)
      if (noAction) expect(noAction.textContent!.trim().length).toBeGreaterThan(0)
    }
  })
})
