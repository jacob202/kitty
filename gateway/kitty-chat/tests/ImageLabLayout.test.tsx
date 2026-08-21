import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ImageLab } from '../src/components/ImageLab'
import * as queries from '../src/lib/queries'

vi.mock('../src/lib/queries', async () => {
  const actual = await vi.importActual<typeof queries>('../src/lib/queries')
  return { ...actual, useImageStatus: vi.fn() }
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

it('stacks conversation and queue in compact mode', async () => {
  vi.mocked(queries.useImageStatus).mockReturnValue({
    data: { available: true, engines: [] }, isPending: false, isError: false,
    isFetching: false, refetch: vi.fn(),
  } as never)
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, status: 200, json: async () => ({
      provider: 'comfyui', model_id: 'sdxl', recipe_id: 'r', routing_reason: 'test', count: 1,
      estimate: { cost: { state: 'known', usd: 0 }, duration: { state: 'unknown', seconds: null } },
      per_image_estimate: { cost: { state: 'known', usd: 0 }, duration: { state: 'unknown', seconds: null } },
    }),
  })))

  render(<ImageLab compact />)
  expect(await screen.findByTestId('image-lab-workspace')).toHaveStyle({ gridTemplateColumns: '1fr' })
})
