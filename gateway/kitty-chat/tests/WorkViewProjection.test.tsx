import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkView from '../src/components/WorkView'

const { useWorkSnapshot } = vi.hoisted(() => ({ useWorkSnapshot: vi.fn() }))

vi.mock('../src/lib/work', () => ({ useWorkSnapshot }))
const SNAPSHOT = {
  schema_version: 1,
  observed_at: '2026-08-13T21:00:00Z',
  valid_until: '2026-08-13T21:00:30Z',
  source: { kind: 'builder', state: 'available' },
  counts: { total: 2, active: 1, paused: 0, failed: 0, blocked: 0, completed: 1, ready: 0, waiting: 0 },
  queue: null,
  item_limit: 50,
  total_items: 2,
  items: [
    {
      id: 'WORK-SPINE-003',
      title: 'Ship Gateway Work Spine',
      state: 'active',
      source: { kind: 'builder', initiative_id: 'WORK-SPINE-003', packet_id: 'WORK-SPINE-FINAL' },
      current_packet: { id: 'WORK-SPINE-FINAL', title: 'Final contract', task_id: 'kb_123', task_state: 'running' },
      current_run: { id: 'run_123', state: 'running', started_at: '2026-08-13T20:59:00Z' },
      blocker: null,
      next_action: 'Finish verification',
      evidence: { approval: { state: 'unavailable', reason: 'No durable Gateway approval binding exists yet.' } },
      data_quality: { state: 'complete', issues: [] },
      updated_at: '2026-08-13T21:00:00Z',
    },
    {
      id: 'KPROOF-VERSION-007',
      title: 'KPROOF version endpoint',
      state: 'completed',
      source: { kind: 'builder', initiative_id: 'KPROOF-VERSION-007', packet_id: 'KVERSION-007' },
      current_packet: { id: 'KVERSION-007', title: 'Version endpoint', task_id: 'kb_007', task_state: 'done' },
      current_run: null,
      blocker: null,
      next_action: null,
      evidence: { approval: { state: 'unavailable', reason: 'No durable Gateway approval binding exists yet.' } },
      data_quality: { state: 'complete', issues: [] },
      updated_at: '2026-08-13T20:00:00Z',
    },
  ],
}

describe('WorkView /work projection', () => {
  beforeEach(() => useWorkSnapshot.mockReset())

  it('renders Gateway Work truth instead of legacy todo/builder surfaces', () => {
    useWorkSnapshot.mockReturnValue({ data: SNAPSHOT, isPending: false, isError: false, error: null, refetch: vi.fn() })
    render(<WorkView isMobile={false} />)

    expect(screen.getByText('Ship Gateway Work Spine')).toBeInTheDocument()
    expect(screen.getByText('KPROOF version endpoint')).toBeInTheDocument()
    expect(screen.getByText('Builder available')).toBeInTheDocument()
    expect(screen.getByText('1 active')).toBeInTheDocument()
    expect(screen.getAllByText('approval unavailable').length).toBeGreaterThan(0)
  })
})
