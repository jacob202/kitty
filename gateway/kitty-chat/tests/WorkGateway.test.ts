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
