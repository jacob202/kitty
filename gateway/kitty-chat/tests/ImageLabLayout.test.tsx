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

function renderReadyLab(compact = false) {
  vi.mocked(queries.useImageStatus).mockReturnValue({
    data: { available: true, engines: [{ name: 'comfyui', label: 'ComfyUI', available: true }] },
    isPending: false, isError: false, isFetching: false, refetch: vi.fn(),
  } as never)
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (String(url) === '/proxy/studio/characters') {
      return { ok: true, status: 200, json: async () => ({ characters: [] }) }
    }
    return {
      ok: true, status: 200, json: async () => ({
        provider: 'comfyui', model_id: 'sdxl', recipe_id: 'r', routing_reason: 'test', count: 1,
        estimate: { cost: { state: 'known', usd: 0 }, duration: { state: 'unknown', seconds: null } },
        per_image_estimate: { cost: { state: 'known', usd: 0 }, duration: { state: 'unknown', seconds: null } },
      }),
    }
  }))
  return render(<ImageLab compact={compact} />)
}

it('stacks the creative workspace in compact mode', async () => {
  renderReadyLab(true)
  expect(await screen.findByTestId('image-lab-workspace')).toHaveStyle({ gridTemplateColumns: '1fr' })
})

it('gives references, creation, results, and activity explicit workspace regions', async () => {
  renderReadyLab()

  expect(await screen.findByTestId('image-lab-references')).toHaveAccessibleName('References')
  expect(screen.getByTestId('image-lab-create')).toHaveAccessibleName('Create')
  expect(screen.getByTestId('image-lab-results')).toHaveAccessibleName('Results')
  expect(screen.getByTestId('image-lab-activity')).toHaveAccessibleName('Activity')

  const results = screen.getByTestId('image-lab-results')
  const activity = screen.getByTestId('image-lab-activity')
  expect(results.compareDocumentPosition(activity) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})

it('keeps runtime mechanics secondary and makes the generation action readable and touch sized', async () => {
  renderReadyLab()

  const details = await screen.findByTestId('image-lab-runtime-details')
  expect(details.tagName).toBe('DETAILS')
  expect(screen.getByText('Generation details')).toBeInTheDocument()

  const generate = screen.getByTestId('image-lab-send')
  expect(generate).toHaveTextContent('Generate')
  expect(generate).toHaveStyle({ minHeight: '48px' })
})
