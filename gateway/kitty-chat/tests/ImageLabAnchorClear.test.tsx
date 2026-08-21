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

describe('ImageLab anchor persistence', () => {
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

  it('persists clearing the selected image before hiding the anchor', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
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
      if (target === '/proxy/studio/sessions/imgses_1' && !init?.method) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            session_id: 'imgses_1', anchor_job_id: 'job_1', turns: [], jobs: [],
          }),
        }
      }
      if (target === '/proxy/studio/batches?session_id=imgses_1') {
        return { ok: true, status: 200, json: async () => ({ batches: [] }) }
      }
      if (target === '/proxy/studio/sessions/imgses_1/anchor' && init?.method === 'DELETE') {
        return {
          ok: true,
          status: 200,
          json: async () => ({ session_id: 'imgses_1', anchor_job_id: null, turns: [], jobs: [] }),
        }
      }
      return { ok: true, status: 200, json: async () => ({}) }
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<ImageLab />)
    await screen.findByTestId('image-lab-anchor')

    fireEvent.click(screen.getByRole('button', { name: 'clear selected image' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/proxy/studio/sessions/imgses_1/anchor', { method: 'DELETE' })
    })
    await waitFor(() => expect(screen.queryByTestId('image-lab-anchor')).not.toBeInTheDocument())
  })
})
