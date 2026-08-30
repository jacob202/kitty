import { afterEach, expect, it, vi } from 'vitest'
import * as work from '../src/lib/work'

afterEach(() => vi.unstubAllGlobals())

it('fetches the read-only Gateway /work snapshot', async () => {
  const snapshot = {
    schema_version: 1,
    observed_at: '2026-08-13T21:00:00Z',
    valid_until: '2026-08-13T21:00:30Z',
    source: { kind: 'builder', state: 'available' },
    counts: { total: 0, active: 0, paused: 0, failed: 0, blocked: 0, completed: 0, ready: 0, waiting: 0 },
    queue: null,
    items: [],
    item_limit: 50,
    total_items: 0,
  }
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(snapshot), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  const fetchWork = (work as Record<string, unknown>).fetchGatewayWorkSnapshot
  expect(typeof fetchWork).toBe('function')
  const result = await (fetchWork as () => Promise<unknown>)()

  expect(fetchMock.mock.calls[0]?.[0]).toBe('/proxy/work')
  expect(result).toEqual(snapshot)
})

it('preserves Gateway error detail and endpoint', async () => {
  const fetchMock = vi.fn(async () => new Response(
    JSON.stringify({ detail: 'work source unavailable' }),
    { status: 503, statusText: 'Service Unavailable', headers: { 'Content-Type': 'application/json' } },
  ))
  vi.stubGlobal('fetch', fetchMock)

  const fetchWork = (work as Record<string, unknown>).fetchGatewayWorkSnapshot as () => Promise<unknown>

  await expect(fetchWork()).rejects.toThrow(
    'GET /proxy/work failed: 503 Service Unavailable: work source unavailable',
  )
})


it('fails closed when Gateway /work returns an invalid payload', async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify({ schema_version: 999 }), { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
  const fetchWork = (work as Record<string, unknown>).fetchGatewayWorkSnapshot as () => Promise<unknown>
  await expect(fetchWork()).rejects.toThrow('Gateway /work returned an invalid payload')
})

it('fails closed when a Work item omits render-required metadata', async () => {
  const invalid = {
    schema_version: 1,
    observed_at: '2026-08-13T21:00:00Z',
    valid_until: '2026-08-13T21:00:30Z',
    source: { kind: 'builder', state: 'available' },
    counts: { total: 1, active: 0, paused: 0, failed: 0, blocked: 1, completed: 0, ready: 0, waiting: 0 },
    queue: null,
    items: [{
      id: 'WORK-1',
      title: 'Malformed item',
      state: 'blocked',
      source: { kind: 'builder', initiative_id: 'WORK-1', packet_id: null },
      evidence: {},
      // data_quality intentionally omitted: WorkView dereferences it.
    }],
    item_limit: 50,
    total_items: 1,
  }
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(invalid), { status: 200 })))
  const fetchWork = (work as Record<string, unknown>).fetchGatewayWorkSnapshot as () => Promise<unknown>
  await expect(fetchWork()).rejects.toThrow('Gateway /work returned an invalid payload')
})

it('fails closed when evidence has an array shape', async () => {
  const invalid = {
    schema_version: 1,
    observed_at: '2026-08-13T21:00:00Z',
    valid_until: '2026-08-13T21:00:30Z',
    source: { kind: 'builder', state: 'available' },
    counts: { total: 1, active: 1, paused: 0, failed: 0, blocked: 0, completed: 0, ready: 0, waiting: 0 },
    queue: null,
    items: [{
      id: 'WORK-1', title: 'Bad evidence', state: 'active',
      source: { kind: 'builder', initiative_id: 'WORK-1', packet_id: null },
      evidence: [], data_quality: { state: 'complete', issues: [] },
    }],
    item_limit: 50,
    total_items: 1,
  }
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(invalid), { status: 200 })))
  const fetchWork = (work as Record<string, unknown>).fetchGatewayWorkSnapshot as () => Promise<unknown>
  await expect(fetchWork()).rejects.toThrow('Gateway /work returned an invalid payload')
})
it('fails closed when a nested evidence field is not a record', async () => {
  const invalid = {
    schema_version: 1,
    observed_at: '2026-08-13T21:00:00Z',
    valid_until: '2026-08-13T21:00:30Z',
    source: { kind: 'builder', state: 'available' },
    counts: { total: 1, active: 1, paused: 0, failed: 0, blocked: 0, completed: 0, ready: 0, waiting: 0 },
    queue: null,
    items: [{
      id: 'WORK-1', title: 'Bad review evidence', state: 'active',
      source: { kind: 'builder', initiative_id: 'WORK-1', packet_id: null },
      evidence: { review: [] }, data_quality: { state: 'complete', issues: [] },
    }],
    item_limit: 50,
    total_items: 1,
  }
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(invalid), { status: 200 })))
  const fetchWork = (work as Record<string, unknown>).fetchGatewayWorkSnapshot as () => Promise<unknown>
  await expect(fetchWork()).rejects.toThrow('Gateway /work returned an invalid payload')
})

it.each([
  ['review verdict', { review: { verdict: { code: 'approve' } } }],
  ['review summary', { review: { summary: ['passed'] } }],
  ['validation status', { validation: { status: { code: 'passed' } } }],
  ['validation summary', { validation: { summary: ['passed'] } }],
  ['publication checks state', { publication: { checks_state: { code: 'passed' } } }],
  ['publication merged flag', { publication: { merged: 'true' } }],
  ['publication merged timestamp', { publication: { merged_at: 123 } }],
])('fails closed when a rendered evidence field is malformed: %s', async (_label, evidence) => {
  const invalid = {
    schema_version: 1,
    observed_at: '2026-08-13T21:00:00Z',
    valid_until: '2026-08-13T21:00:30Z',
    source: { kind: 'builder', state: 'available' },
    counts: { total: 1, active: 1, paused: 0, failed: 0, blocked: 0, completed: 0, ready: 0, waiting: 0 },
    queue: null,
    items: [{
      id: 'WORK-1', title: 'Bad evidence field', state: 'active',
      source: { kind: 'builder', initiative_id: 'WORK-1', packet_id: null },
      evidence, data_quality: { state: 'complete', issues: [] },
    }],
    item_limit: 50,
    total_items: 1,
  }
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(invalid), { status: 200 })))
  const fetchWork = (work as Record<string, unknown>).fetchGatewayWorkSnapshot as () => Promise<unknown>
  await expect(fetchWork()).rejects.toThrow('Gateway /work returned an invalid payload')
})

it.each([
  ['next_action', { next_action: ['needs_review'], blocker: null }],
  ['blocker reason', { next_action: null, blocker: { state: 'blocked', reason: { code: 'needs_review' } } }],
])('fails closed when a Work item has a non-string %s', async (_label, malformedFields) => {
  const invalid = {
    schema_version: 1,
    observed_at: '2026-08-13T21:00:00Z',
    valid_until: '2026-08-13T21:00:30Z',
    source: { kind: 'builder', state: 'available' },
    counts: { total: 1, active: 0, paused: 0, failed: 0, blocked: 1, completed: 0, ready: 0, waiting: 0 },
    queue: null,
    items: [{
      id: 'WORK-1', title: 'Bad work detail', state: 'blocked',
      source: { kind: 'builder', initiative_id: 'WORK-1', packet_id: null },
      evidence: {}, data_quality: { state: 'complete', issues: [] },
      ...malformedFields,
    }],
    item_limit: 50,
    total_items: 1,
  }
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(invalid), { status: 200 })))
  const fetchWork = (work as Record<string, unknown>).fetchGatewayWorkSnapshot as () => Promise<unknown>
  await expect(fetchWork()).rejects.toThrow('Gateway /work returned an invalid payload')
})


it.each([
  ['current_packet.id', { id: { value: 'PACKET-1' } }],
  ['current_packet.task_id', { task_id: { value: 'TASK-1' } }],
  ['current_packet.task_state', { task_state: { value: 'running' } }],
  ['current_run.id', { id: { value: 'RUN-1' } }],
])('fails closed when a rendered Work metadata field is not a string: %s', async (label, malformedField) => {
  const currentPacket = label.startsWith('current_packet')
    ? { id: 'PACKET-1', title: 'Packet', task_id: 'TASK-1', task_state: 'running', ...malformedField }
    : null
  const currentRun = label.startsWith('current_run')
    ? { id: 'RUN-1', state: 'running', ...malformedField }
    : null
  const invalid = {
    schema_version: 1,
    observed_at: '2026-08-13T21:00:00Z',
    valid_until: '2026-08-13T21:00:30Z',
    source: { kind: 'builder', state: 'available' },
    counts: { total: 1, active: 1, paused: 0, failed: 0, blocked: 0, completed: 0, ready: 0, waiting: 0 },
    queue: null,
    items: [{
      id: 'WORK-1', title: 'Bad metadata', state: 'active',
      source: { kind: 'builder', initiative_id: 'WORK-1', packet_id: null },
      current_packet: currentPacket,
      current_run: currentRun,
      evidence: {}, data_quality: { state: 'complete', issues: [] },
    }],
    item_limit: 50,
    total_items: 1,
  }
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(invalid), { status: 200 })))
  const fetchWork = (work as Record<string, unknown>).fetchGatewayWorkSnapshot as () => Promise<unknown>
  await expect(fetchWork()).rejects.toThrow('Gateway /work returned an invalid payload')
})


it('allows a supervisor tick longer than the ordinary 8-second mutation timeout', async () => {
  vi.useFakeTimers()
  try {
    let signal: AbortSignal | undefined
    const fetchMock = vi.fn((_url: string | URL | Request, init?: RequestInit) => {
      signal = init?.signal ?? undefined
      return new Promise<Response>((_resolve, reject) => {
        signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    const settled = work.runSupervisorTick().then(
      () => 'resolved',
      () => 'rejected',
    )
    await vi.advanceTimersByTimeAsync(8_100)
    expect(signal?.aborted).toBe(false)
    await vi.advanceTimersByTimeAsync(20_000)
    expect(signal?.aborted).toBe(true)
    expect(await settled).toBe('rejected')
  } finally {
    vi.useRealTimers()
  }
})
