// Finding 2 (PR #355 review): a reachable gateway with offline renderers must
// resolve { available: false }, but an unreachable gateway/proxy must reject —
// never be masked as "renderers are offline" (which would send the user to
// start ComfyUI when the real fix is restoring the gateway).
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { fetchImageStatus } from '../src/lib/gateway'

function response(body: unknown, ok: boolean, status: number) {
  return {
    ok,
    status,
    statusText: status === 503 ? 'Service Unavailable' : '',
    json: async () => JSON.parse(JSON.stringify(body)),
  }
}

describe('fetchImageStatus error distinction (#346 / PR#355 finding 2)', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('resolves a shallow-offline result when the gateway answers, renderers offline', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      response(
        {
          available: false,
          backend: 'comfyui',
          engines: [{ name: 'comfyui', label: 'ComfyUI', available: false }],
        },
        true,
        200,
      ),
    )
    const status = await fetchImageStatus()
    expect(status.available).toBe(false)
    expect(status.engines).toHaveLength(1)
    expect(status.engines?.[0].available).toBe(false)
  })

  it('resolves available when the gateway reports a renderer online', async () => {
    vi.mocked(global.fetch).mockResolvedValue(
      response({ available: true, backend: 'comfyui', engines: [{ name: 'comfyui', available: true }] }, true, 200),
    )
    expect((await fetchImageStatus()).available).toBe(true)
  })

  it('REJECTS on a non-2xx status instead of masking it as offline renderers', async () => {
    vi.mocked(global.fetch).mockResolvedValue(response({ detail: 'boom' }, false, 503))
    await expect(fetchImageStatus()).rejects.toThrow(/503/)
  })

  it('REJECTS on a network failure instead of masking it as offline renderers', async () => {
    vi.mocked(global.fetch).mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(fetchImageStatus()).rejects.toThrow('Failed to fetch')
  })
})
