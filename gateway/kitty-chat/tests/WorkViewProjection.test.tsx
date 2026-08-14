import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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

  it('renders Gateway work truth', () => {
    renderSnapshot()
    expect(screen.getByText('Ship Gateway Work Spine')).toBeInTheDocument()
    expect(screen.getByText('Builder available')).toBeInTheDocument()
    expect(screen.getByText('1 active')).toBeInTheDocument()
    expect(screen.getByText('approval unavailable')).toBeInTheDocument()
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
