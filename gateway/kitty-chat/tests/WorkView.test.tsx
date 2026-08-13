import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WorkView from '../src/components/WorkView'
import { fetchGatewayWork } from '../src/lib/gateway'

const hooks = vi.hoisted(() => ({
  useGatewayWork: vi.fn(),
  useGatewayWorkDetail: vi.fn(),
  useGatewayWorkEvents: vi.fn(),
}))

vi.mock('../src/lib/queries', () => hooks)

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const item = {
  work_id: 'builder:kb_1',
  source: 'builder' as const,
  source_id: 'kb_1',
  title: 'Ship authoritative Work',
  summary: 'One Gateway-owned work projection.',
  state: 'blocked' as const,
  source_state: 'blocked',
  priority: 10,
  created_at: '2026-08-13T20:00:00Z',
  updated_at: '2026-08-13T21:00:00Z',
  blocker: 'Needs operator decision',
  error: null,
  latest_run: { id: 'run_1', state: 'exited' },
  latest_pr: null,
  evidence: { approval: { state: 'unavailable', reason: 'No durable Gateway approval binding exists' } },
  links: [],
}
const snapshot = {
  schema_version: 1 as const,
  observed_at: '2026-08-13T21:00:00Z',
  valid_until: '2099-08-13T21:00:30Z',
  source_health: { kind: 'builder' as const, state: 'available' },
  state_counts: { blocked: 1, completed: 1 },
  total_items: 2,
  item_limit: 100,
  items: [
    item,
    { ...item, work_id: 'builder:kb_2', source_id: 'kb_2', title: 'Finished proof', state: 'completed' as const, source_state: 'done', blocker: null },
  ],
}

function setHooks(overrides: Record<string, unknown> = {}) {
  hooks.useGatewayWork.mockReturnValue({
    data: snapshot, isPending: false, isError: false, error: null, refetch: vi.fn(), ...overrides,
  })
  hooks.useGatewayWorkDetail.mockReturnValue({ data: item, isPending: false, error: null })
  hooks.useGatewayWorkEvents.mockReturnValue({
    data: { events: [{ id: 1, event_type: 'worker_started', created_at: '2026-08-13T20:30:00Z' }] },
    error: null,
  })
}

it('preserves the Gateway detail when /work fails', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Builder database unavailable' }), {
    status: 503,
    headers: { 'Content-Type': 'application/json' },
  })))
  await expect(fetchGatewayWork()).rejects.toThrow('Builder database unavailable')
})

describe('WorkView authoritative Gateway projection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setHooks()
  })

  it('renders authoritative counts, blocker and diagnostics navigation', () => {
    const navigate = vi.fn()
    render(<WorkView isMobile={false} onNavigate={navigate} />)
    expect(screen.getAllByText('Ship authoritative Work').length).toBeGreaterThan(0)
    expect(screen.getByText('1 blocked')).toBeInTheDocument()
    expect(screen.getAllByText('Needs operator decision').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole('button', { name: /builder diagnostics/i }))
    expect(navigate).toHaveBeenCalledWith('builder')
  })
  it('shows loading, true empty, and concrete Gateway errors distinctly', () => {
    setHooks({ data: undefined, isPending: true })
    const { rerender } = render(<WorkView isMobile />)
    expect(screen.getByText(/loading authoritative work/i)).toBeInTheDocument()

    setHooks({ data: { ...snapshot, total_items: 0, state_counts: {}, items: [] }, isPending: false })
    rerender(<WorkView isMobile />)
    expect(screen.getByText(/no builder work matches/i)).toBeInTheDocument()

    setHooks({ data: undefined, isPending: false, isError: true, error: new Error('Builder database unavailable') })
    rerender(<WorkView isMobile />)
    expect(screen.getByText(/builder database unavailable/i)).toBeInTheDocument()
  })

  it('keeps degraded and stale data visible with explicit warnings', () => {
    setHooks({ data: {
      ...snapshot,
      valid_until: '2000-01-01T00:00:00Z',
      source_health: { kind: 'builder', state: 'degraded', reason: 'partial read' },
    } })
    render(<WorkView isMobile={false} />)
    expect(screen.getByText(/builder source is degraded/i)).toBeInTheDocument()
    expect(screen.getByText(/work data is stale/i)).toBeInTheDocument()
    expect(screen.getAllByText('Ship authoritative Work').length).toBeGreaterThan(0)
  })

  it('shows approval truth, structured evidence, latest run and ordered events', () => {
    hooks.useGatewayWorkDetail.mockReturnValue({
      data: {
        ...item,
        evidence: {
          approval: { state: 'unavailable', reason: 'No durable Gateway approval binding exists' },
          implementation: { status: 'completed', summary: 'Implemented the slice' },
          validation: { status: 'passed' },
          review: { verdict: 'approve' },
          publication: { merged: false },
        },
      },
      isPending: false,
      error: null,
    })
    hooks.useGatewayWorkEvents.mockReturnValue({
      data: { events: [
        { id: 1, event_type: 'worker_started', created_at: '2026-08-13T20:30:00Z' },
        { id: 2, event_type: 'validation_passed', created_at: '2026-08-13T20:31:00Z' },
      ] },
      error: null,
    })
    render(<WorkView isMobile={false} />)
    expect(screen.getAllByText(/unavailable — no durable gateway approval binding exists/i).length).toBeGreaterThan(0)
    expect(screen.getByText('Implemented the slice')).toBeInTheDocument()
    expect(screen.getByText('passed')).toBeInTheDocument()
    expect(screen.getByText('approve')).toBeInTheDocument()
    expect(screen.getByText('worker_started')).toBeInTheDocument()
    expect(screen.getByText('validation_passed')).toBeInTheDocument()
  })

  it('renders no unsupported work mutation controls', () => {
    render(<WorkView isMobile={false} />)
    for (const name of [/run now/i, /^retry$/i, /^approve$/i, /^publish$/i]) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
    }
  })
})
