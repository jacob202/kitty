import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WorkView from '../src/components/WorkView'

const { useWorkSnapshot } = vi.hoisted(() => ({ useWorkSnapshot: vi.fn() }))
vi.mock('../src/lib/work', () => ({ useWorkSnapshot }))

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

function renderSnapshot(data = snapshot()) {
  useWorkSnapshot.mockReturnValue({ data, isPending: false, isError: false, error: null, refetch: vi.fn() })
  render(<WorkView isMobile={false} />)
}

describe('WorkView projection', () => {
  beforeEach(() => useWorkSnapshot.mockReset())
  afterEach(cleanup)

  it('renders Gateway work truth', () => {
    renderSnapshot()
    expect(screen.getByText('Ship Gateway Work Spine')).toBeInTheDocument()
    expect(screen.getByText('Builder available')).toBeInTheDocument()
    expect(screen.getByText('1 active')).toBeInTheDocument()
    expect(screen.getByText('approval unavailable')).toBeInTheDocument()
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

  it('marks expired cached work stale', () => {
    renderSnapshot(snapshot('2000-01-01T00:00:00Z'))
    expect(screen.getByText('Builder stale')).toBeInTheDocument()
  })

  it('discloses bounded results', () => {
    renderSnapshot(snapshot('2099-01-01T00:00:00Z', 75))
    expect(screen.getByText('Showing 1 of 75 most relevant items.')).toBeInTheDocument()
  })
})
