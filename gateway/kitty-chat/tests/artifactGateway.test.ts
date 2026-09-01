import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchArtifactText } from '../src/lib/gateway'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('fetchArtifactText', () => {
  it('preserves the gateway rejection detail', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(
      JSON.stringify({ detail: 'artifact artifact_1 is missing from disk' }),
      { status: 404, headers: { 'Content-Type': 'application/json' } },
    )))

    await expect(fetchArtifactText('artifact_1')).rejects.toMatchObject({
      name: 'ArtifactPreviewRejection',
      message: 'artifact artifact_1 is missing from disk',
    })
  })

  it('passes an abortable signal to the preview request', async () => {
    let signal: AbortSignal | undefined
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      signal = init?.signal as AbortSignal | undefined
      return new Promise<Response>((_resolve, reject) => {
        signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
      })
    }))
    const controller = new AbortController()
    const request = fetchArtifactText('artifact_1', controller.signal)
    controller.abort()

    await expect(request).rejects.toMatchObject({ name: 'AbortError' })
    expect(signal?.aborted).toBe(true)
  })
})
