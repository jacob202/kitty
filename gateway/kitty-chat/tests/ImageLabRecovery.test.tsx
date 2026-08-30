import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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

  it('keeps the restored session authoritative after a transient restore error', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const target = String(url)
      if (target === '/proxy/studio/estimate') return { ok: true, status: 200, json: async () => ({
        provider: 'openrouter', model_id: 'vendor/image', recipe_id: 'hosted', routing_reason: 'best', count: 1,
        per_image_estimate: { cost: { state: 'unknown' }, duration: { state: 'unknown' } },
        estimate: { cost: { state: 'unknown' }, duration: { state: 'unknown' } },
      }) }
      if (target === '/proxy/studio/sessions/imgses_1') return { ok: false, status: 503, text: async () => 'temporarily unavailable' }
      if (target === '/proxy/studio/characters') return { ok: true, status: 200, json: async () => ({ characters: [] }) }
      if (target === '/proxy/studio/agent') return { ok: true, status: 200, json: async () => ({ action: 'clarify', session_id: 'imgses_1', summary: 'ok', plan_id: null, question: 'ok' }) }
      if (target === '/proxy/studio/sessions' && (init?.method ?? 'GET') === 'POST') return { ok: true, status: 200, json: async () => ({ session_id: 'imgses_NEW' }) }
      return { ok: true, status: 200, json: async () => ({ batches: [] }) }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<ImageLab />)
    await screen.findByText(/could not restore the saved image lab session/i)
    fireEvent.change(screen.getByPlaceholderText(/tell kitty what you want/i), { target: { value: 'continue' } })
    fireEvent.click(screen.getByTestId('image-lab-send'))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/proxy/studio/agent', expect.anything()))
    expect(fetchMock.mock.calls.some(([url, init]) => String(url) === '/proxy/studio/sessions' && (init?.method ?? 'GET') === 'POST')).toBe(false)
    expect(window.localStorage.getItem('kitty-image-lab-session')).toBe('imgses_1')
  })

})
