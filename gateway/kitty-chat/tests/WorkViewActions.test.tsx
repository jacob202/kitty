import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WorkView, { rowAction, type RowAction } from '../src/components/WorkView'
import type { GatewayWorkItem } from '../src/lib/work'

const { useWorkSnapshot, useSupervisor, useBuilderAction, mutate } = vi.hoisted(() => ({
  useWorkSnapshot: vi.fn(),
  useSupervisor: vi.fn(),
  useBuilderAction: vi.fn(),
  mutate: vi.fn(),
}))
vi.mock('../src/lib/work', () => ({ useWorkSnapshot, useSupervisor, useBuilderAction }))

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
  useSupervisor.mockReset()
  useBuilderAction.mockReset()
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

  it('says retries are used up but still lets the user try again', () => {
    const action = rowAction(item({ next_action: 'exhausted' }), false)
    expect(action.kind).toBe('command')
    expect((action as Extract<RowAction, { kind: 'command' }>).note).toMatch(/automatic retries/i)
  })

  it('offers to start Builder for ready work when Builder is stopped', () => {
    const action = rowAction(item({ next_action: 'claim' }), false)
    expect(action).toMatchObject({ kind: 'tick', label: 'Start Builder' })
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
  it('says Builder is stopped and offers to start it', () => {
    renderWork([item()])
    expect(screen.getByText('Builder is stopped.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start Builder' })).toBeEnabled()
  })

  it('explains what is ready and what is waiting on a paused project', () => {
    renderWork([item()])
    expect(screen.getByText(/1 job is ready to run/)).toBeInTheDocument()
    expect(screen.getByText(/9 more are on hold until their project is resumed/)).toBeInTheDocument()
  })

  it('confirms before starting Builder because a run can cost money', () => {
    renderWork([item()])
    fireEvent.click(screen.getByRole('button', { name: 'Start Builder' }))
    expect(globalThis.confirm).toHaveBeenCalledWith(expect.stringMatching(/paid models/i))
    expect(mutate).toHaveBeenCalledWith('tick', expect.anything())
  })

  it('does not start Builder when the user declines the confirmation', () => {
    vi.stubGlobal('confirm', vi.fn(() => false))
    renderWork([item()])
    fireEvent.click(screen.getByRole('button', { name: 'Start Builder' }))
    expect(mutate).not.toHaveBeenCalled()
  })

  it('cannot be started when there is nothing it could actually run', () => {
    renderWork([item()], supervisor({ eligible_now: 0 }))
    expect(screen.getByRole('button', { name: 'Start Builder' })).toBeDisabled()
  })

  it('reports that Builder is working instead of offering to start it', () => {
    renderWork([item({ next_action: 'claim' })], supervisor({ running: true, active_runs: [{ id: 'run_1' }] }))
    expect(screen.getByText('Builder is working.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start Builder' })).not.toBeInTheDocument()
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

  it('confirms before cancelling, then sends the cancel', () => {
    renderWork([item({ next_action: 'recover' })])
    fireEvent.click(screen.getByRole('button', { name: 'Cancel it' }))
    expect(globalThis.confirm).toHaveBeenCalled()
    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ action: 'cancel', task_id: 'kb_task_1' }),
      expect.anything(),
    )
  })

  it('offers no cancel for work that already finished', () => {
    renderWork([item({ next_action: 'done', state: 'completed' })])
    expect(screen.queryByRole('button', { name: 'Cancel it' })).not.toBeInTheDocument()
    expect(screen.getByText(/this one is finished/i)).toBeInTheDocument()
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
      // Exactly one of the two — a row must not both offer an action and claim
      // none is available, and it must never render neither.
      expect(Boolean(action) !== Boolean(noAction)).toBe(true)
      if (action) expect(within(action).getAllByRole('button').length).toBeGreaterThan(0)
      else expect(noAction!.textContent!.trim().length).toBeGreaterThan(0)
    }
  })
})
