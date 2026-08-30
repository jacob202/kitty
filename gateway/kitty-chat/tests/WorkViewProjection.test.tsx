import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WorkView from '../src/components/WorkView'

const { useWorkSnapshot, useSupervisor, useBuilderAction, mutate } = vi.hoisted(() => ({
  useWorkSnapshot: vi.fn(),
  useSupervisor: vi.fn(),
  useBuilderAction: vi.fn(),
  mutate: vi.fn(),
}))
vi.mock('../src/lib/work', () => ({ useWorkSnapshot, useSupervisor, useBuilderAction }))

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

function snapshot(validUntil = '2099-01-01T00:00:00Z', totalItems = 1) {
  return {
    schema_version: 1,
    observed_at: '2026-08-13T21:00:00Z',
    valid_until: validUntil,
    source: { kind: 'builder', state: 'available' },
    counts: { total: totalItems, active: 1, paused: 0, failed: 0, blocked: 0, completed: 0, ready: 0, waiting: 0 },
    queue: null,
    item_limit: 50,
    total_items: totalItems,
    items: [{
      id: 'WORK-SPINE-003',
      title: 'Ship Gateway Work Spine',
      state: 'active',
      source: { kind: 'builder', initiative_id: 'WORK-SPINE-003', packet_id: 'WORK-SPINE-FINAL' },
      current_packet: { id: 'WORK-SPINE-FINAL', title: 'Final contract', task_id: 'kb_123', task_state: 'running' },
      current_run: null,
      blocker: null,
      next_action: 'Finish verification',
      evidence: { approval: { state: 'unavailable' } },
      data_quality: { state: 'complete', issues: [] },
      updated_at: '2026-08-13T21:00:00Z',
    }],
  }
}

function renderSnapshot(data = snapshot(), supervisorData: unknown = supervisor()) {
  useWorkSnapshot.mockReturnValue({ data, isPending: false, isError: false, error: null, refetch: vi.fn() })
  useSupervisor.mockReturnValue({ data: supervisorData, isPending: false, isError: false, error: null })
  useBuilderAction.mockReturnValue({ mutate, isPending: false })
  render(<WorkView isMobile={false} />)
}

describe('WorkView projection', () => {
  beforeEach(() => {
    useWorkSnapshot.mockReset()
    useSupervisor.mockReset()
    useBuilderAction.mockReset()
    mutate.mockReset()
    useSupervisor.mockReturnValue({ data: supervisor(), isPending: false, isError: false, error: null })
    useBuilderAction.mockReturnValue({ mutate, isPending: false })
  })
  afterEach(cleanup)

  it('renders Gateway work truth', () => {
    renderSnapshot()
    expect(screen.getByText('Ship Gateway Work Spine')).toBeInTheDocument()
    expect(screen.getByText('Builder available')).toBeInTheDocument()
    expect(screen.getByText('1 active')).toBeInTheDocument()
  })

  it('groups durable work by what needs the user, what is moving, and what finished', () => {
    const base = snapshot().items[0]
    const states = [
      ['blocked', 'Blocked item'],
      ['failed', 'Failed item'],
      ['paused', 'Paused item'],
      ['active', 'Active item'],
      ['ready', 'Ready item'],
      ['waiting', 'Waiting item'],
      ['completed', 'Completed item'],
    ] as const
    const items = states.map(([state, title], index) => ({
      ...base,
      id: `WORK-${index}`,
      title,
      state,
      source: { ...base.source, initiative_id: `WORK-${index}` },
    }))
    renderSnapshot({
      ...snapshot('2099-01-01T00:00:00Z', items.length),
      counts: { total: 7, active: 1, paused: 1, failed: 1, blocked: 1, completed: 1, ready: 1, waiting: 1 },
      items,
    })

    const needsYou = screen.getByRole('region', { name: 'Needs you' })
    expect(within(needsYou).getByText('Blocked item')).toBeInTheDocument()
    expect(within(needsYou).getByText('Failed item')).toBeInTheDocument()
    expect(within(needsYou).getByText('Paused item')).toBeInTheDocument()
    expect(within(needsYou).queryByText('Active item')).not.toBeInTheDocument()

    const inProgress = screen.getByRole('region', { name: 'In progress' })
    expect(within(inProgress).getByText('Active item')).toBeInTheDocument()
    expect(within(inProgress).getByText('Ready item')).toBeInTheDocument()
    expect(within(inProgress).getByText('Waiting item')).toBeInTheDocument()

    const completed = screen.getByRole('region', { name: 'Completed' })
    expect(within(completed).getByText('Completed item')).toBeInTheDocument()
  })

  it('keeps implementation identifiers and unavailable approval metadata behind Details', () => {
    const base = snapshot().items[0]
    renderSnapshot({
      ...snapshot(),
      items: [{
        ...base,
        current_run: { id: 'RUN-123', state: 'running' },
      }],
    })

    expect(screen.getByText('WORK-SPINE-003')).not.toBeVisible()
    expect(screen.getByText('RUN-123')).not.toBeVisible()
    expect(screen.getByText('approval unavailable')).not.toBeVisible()

    fireEvent.click(screen.getByText('Details'))

    expect(screen.getByText('WORK-SPINE-003')).toBeVisible()
    expect(screen.getByText('RUN-123')).toBeVisible()
    expect(screen.getByText('approval unavailable')).toBeVisible()
  })

  it('translates machine reasons in the primary row and keeps the raw value in Details', () => {
    const base = snapshot().items[0]
    renderSnapshot({
      ...snapshot(),
      items: [{
        ...base,
        state: 'blocked',
        blocker: { state: 'blocked', reason: 'shadow_run_complete', blocked_by: [] },
        next_action: 'recover',
      }],
    })

    expect(screen.queryByText('shadow_run_complete')).not.toBeVisible()
    expect(screen.getByText('The previous Builder run completed; this item remains blocked.')).toBeVisible()

    fireEvent.click(screen.getByText('Details'))
    expect(screen.getByText('shadow_run_complete')).toBeVisible()
  })

  it('puts terminal cancelled failures with finished work instead of Needs you', () => {
    const base = snapshot().items[0]
    renderSnapshot({
      ...snapshot(),
      counts: { total: 1, active: 0, paused: 0, failed: 1, blocked: 0, completed: 0, ready: 0, waiting: 0 },
      items: [{ ...base, state: 'failed', blocker: null, next_action: 'cancelled' }],
    })

    expect(screen.queryByRole('region', { name: 'Needs you' })).not.toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Completed' })).getByText('Ship Gateway Work Spine')).toBeVisible()
  })

  it('exposes advertised review validation and publication proof inside Details', () => {
    const base = snapshot().items[0]
    renderSnapshot({
      ...snapshot(),
      items: [{
        ...base,
        evidence: {
          approval: { state: 'unavailable' },
          review: { verdict: 'approve', summary: 'Independent review passed.' },
          validation: { status: 'passed', summary: '4 validation commands passed.' },
          publication: {
            pr_number: 564,
            checks_state: 'passed',
            merged: true,
            merged_at: '2026-08-21T15:30:00Z',
          },
        },
      }],
    })

    expect(screen.getByText('Review evidence available')).toBeVisible()
    expect(screen.getByText('Validation evidence available')).toBeVisible()
    expect(screen.getByText('Publication evidence available')).toBeVisible()

    fireEvent.click(screen.getByText('Details'))
    expect(screen.getByText('review approve')).toBeVisible()
    expect(screen.getByText('Independent review passed.')).toBeVisible()
    expect(screen.getByText('validation passed')).toBeVisible()
    expect(screen.getByText('4 validation commands passed.')).toBeVisible()
    expect(screen.getByText('publication PR #564')).toBeVisible()
    expect(screen.getByText('publication checks passed')).toBeVisible()
    expect(screen.getByText('publication merged')).toBeVisible()
    expect(screen.getByText('merged Aug 21, 2026')).toBeVisible()
  })

  it('interprets Builder timestamps without a timezone as UTC', () => {
    const base = snapshot().items[0]
    renderSnapshot({
      ...snapshot(),
      items: [{
        ...base,
        evidence: { publication: { merged: true, merged_at: '2026-08-21 00:30:00.000' } },
      }],
    })

    fireEvent.click(screen.getByText('Details'))
    expect(screen.getByText('merged Aug 21, 2026')).toBeVisible()
  })

  it('surfaces review evidence only when review evidence is present', () => {
    const base = snapshot().items[0]
    renderSnapshot({
      ...snapshot(),
      items: [{
        ...base,
        evidence: { ...base.evidence, review: { verdict: 'pass' } },
      }],
    })
    expect(screen.getByText('Review evidence available')).toBeVisible()
  })

  it('distinguishes an unmerged publication without presenting a merged date', () => {
    const base = snapshot().items[0]
    renderSnapshot({
      ...snapshot(),
      items: [{
        ...base,
        evidence: { publication: { pr_number: 564, merged: false, merged_at: '2026-08-21T15:30:00Z' } },
      }],
    })

    fireEvent.click(screen.getByText('Details'))
    expect(screen.getByText('publication not merged')).toBeVisible()
    expect(screen.queryByText('merged Aug 21, 2026')).not.toBeInTheDocument()
  })

  it('does not treat inherited object keys as known Work detail labels', () => {
    const base = snapshot().items[0]
    renderSnapshot({
      ...snapshot(),
      counts: { total: 1, active: 0, paused: 0, failed: 0, blocked: 1, completed: 0, ready: 0, waiting: 0 },
      items: [{ ...base, state: 'blocked', blocker: { reason: '__proto__' }, next_action: null }],
    })

    expect(screen.getAllByText('__proto__').length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: 'Work' })).toBeVisible()
  })

  it('shows degraded Builder truth without switching surfaces', () => {
    renderSnapshot({ ...snapshot(), source: { kind: 'builder', state: 'degraded', reason: 'partial Builder data' } })
    expect(screen.getByText('Builder degraded')).toBeVisible()
    expect(screen.getByText(/some work may be missing/i)).toBeVisible()
    expect(screen.getByRole('heading', { name: 'Work' })).toBeVisible()
  })

  it('keeps Work visible when the Gateway request fails and exposes retry', () => {
    const refetch = vi.fn()
    useWorkSnapshot.mockReturnValue({ data: undefined, isPending: false, isError: true, error: new Error('offline'), refetch })
    render(<WorkView isMobile={false} />)
    expect(screen.getByRole('heading', { name: 'Work' })).toBeVisible()
    expect(screen.getByText('Work is unavailable right now. Retry to reconnect to Builder.')).toBeVisible()
    expect(screen.queryByText('offline')).not.toBeVisible()
    fireEvent.click(screen.getByText('Technical details'))
    expect(screen.getByText('offline')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(refetch).toHaveBeenCalledTimes(1)
  })

  it('marks expired cached work stale', () => {
    renderSnapshot(snapshot('2000-01-01T00:00:00Z'))
    expect(screen.getByText('Builder stale')).toBeInTheDocument()
  })

  it('discloses bounded results', () => {
    renderSnapshot(snapshot('2099-01-01T00:00:00Z', 75))
    expect(screen.getByText('Showing 1 of 75 most relevant items from Builder.')).toBeInTheDocument()
  })
})


describe('WorkView visual hierarchy', () => {
  beforeEach(() => useWorkSnapshot.mockReset())
  afterEach(cleanup)

  it('bounds each status group to the five most relevant rows until expanded', () => {
    const base = snapshot().items[0]
    const items = Array.from({ length: 8 }, (_, index) => ({
      ...base,
      id: `BLOCKED-${index}`,
      title: `Blocked item ${index + 1}`,
      state: 'blocked' as const,
      source: { ...base.source, initiative_id: `BLOCKED-${index}` },
      blocker: { state: 'blocked', reason: 'shadow_run_complete', blocked_by: [] },
      next_action: 'recover',
    }))
    renderSnapshot({
      ...snapshot('2099-01-01T00:00:00Z', items.length),
      counts: { total: 8, active: 0, paused: 0, failed: 0, blocked: 8, completed: 0, ready: 0, waiting: 0 },
      items,
    })

    const region = screen.getByRole('region', { name: 'Needs you' })
    expect(within(region).getAllByTestId('work-row')).toHaveLength(5)
    expect(within(region).queryByText('Blocked item 6')).not.toBeInTheDocument()
    fireEvent.click(within(region).getByRole('button', { name: /show 3 more/i }))
    expect(within(region).getAllByTestId('work-row')).toHaveLength(8)
    expect(within(region).getByText('Blocked item 8')).toBeVisible()
  })

  it('uses one shared list surface for rows in a status group', () => {
    renderSnapshot()
    const progress = screen.getByRole('region', { name: 'In progress' })
    expect(within(progress).getByTestId('work-group-list')).toBeInTheDocument()
    expect(within(progress).getAllByTestId('work-row')).toHaveLength(1)
  })

  it('opens the deeper Builder evidence surface without duplicating its state', () => {
    const onNavigate = vi.fn()
    useWorkSnapshot.mockReturnValue({ data: snapshot(), isPending: false, isError: false, error: null, refetch: vi.fn() })
    render(<WorkView isMobile={false} onNavigate={onNavigate} />)
    fireEvent.click(screen.getByRole('button', { name: /open builder details/i }))
    expect(onNavigate).toHaveBeenCalledWith('builder-details')
  })

  it('keeps the exact degraded source reason behind disclosure', () => {
    renderSnapshot({ ...snapshot(), source: { kind: 'builder', state: 'degraded', reason: 'partial Builder data' } })
    expect(screen.getByText('Builder degraded')).toBeVisible()
    expect(screen.getByText(/some work may be missing/i)).toBeVisible()
    expect(screen.getByText('partial Builder data')).not.toBeVisible()
    fireEvent.click(screen.getByText('Source details'))
    expect(screen.getByText('partial Builder data')).toBeVisible()
  })
})
