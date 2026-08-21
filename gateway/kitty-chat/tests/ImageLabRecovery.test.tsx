import { cleanup, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ImageLab } from '../src/components/ImageLab'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof queries>('../src/lib/queries')
  return { ...actual, useImageStatus: vi.fn() }
})

function onlineStatus() {
  return {
    data: { available: true, engines: [{ name: 'comfyui', label: 'ComfyUI', available: true }] },
    isPending: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined),
  }
}

describe('ImageLab recovery', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.localStorage.setItem('kitty-image-lab-session', 'imgses_1')
    vi.mocked(queries.useImageStatus).mockReturnValue(onlineStatus() as never)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
    window.localStorage.clear()
  })

  it('keeps the durable session pointer when reattachment fails transiently', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      const target = String(url)
      if (target === '/proxy/studio/estimate') {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            provider: 'openrouter', model_id: 'vendor/image', recipe_id: 'hosted',
            routing_reason: 'best available', count: 1,
            per_image_estimate: {
              cost: { state: 'unknown' }, duration: { state: 'unknown' },
            },
            estimate: {
              cost: { state: 'unknown' }, duration: { state: 'unknown' },
            },
          }),
        }
      }
      if (target === '/proxy/studio/sessions/imgses_1') {
        return {
          ok: false,
          status: 503,
          text: async () => 'temporarily unavailable',
        }
      }
      return { ok: true, status: 200, json: async () => ({}) }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<ImageLab />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/proxy/studio/sessions/imgses_1'))
    await waitFor(() => {
      expect(window.localStorage.getItem('kitty-image-lab-session')).toBe('imgses_1')
    })
  })
})
