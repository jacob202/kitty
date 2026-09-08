import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
        recipes: [{ recipe_id: 'test_route', display_name: 'Test route', provider: 'comfyui', quality_tier: 'quality', is_available: true }],
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

  const details = await screen.findByTestId('image-lab-more-controls')
  expect(details.tagName).toBe('DETAILS')
  expect(screen.getByText('More controls')).toBeInTheDocument()

  const generate = screen.getByTestId('image-lab-send')
  expect(generate).toHaveTextContent('Generate')
  expect(generate).toHaveStyle({ minHeight: '48px' })
})

it('preserves advanced selections across More controls close and reopen', async () => {
  renderReadyLab()

  const moreControls = await screen.findByTestId('image-lab-more-controls')
  expect(moreControls).not.toHaveAttribute('open')
  expect(screen.getByRole('textbox', { name: 'Image request' })).toBeVisible()
  expect(screen.getByTestId('image-lab-references')).toBeVisible()
  expect(screen.getByTestId('image-lab-results')).toBeVisible()
  expect(screen.getByTestId('image-lab-estimate')).toBeVisible()
  expect(screen.getByTestId('image-lab-per-image-estimate')).toBeVisible()
  expect(screen.getByTestId('image-lab-send')).toHaveTextContent('Generate')
  expect(moreControls).toContainElement(screen.getByRole('combobox', { name: 'generation route' }))

  fireEvent.click(screen.getByText('More controls'))

  expect(moreControls).toHaveAttribute('open')
  expect(screen.getByRole('button', { name: '4 images' })).toBeVisible()
  expect(screen.getByRole('combobox', { name: 'generation route' })).toBeVisible()
  expect(screen.getByRole('combobox', { name: 'quality' })).toBeVisible()
  expect(screen.getByRole('combobox', { name: 'identity' })).toBeVisible()
  expect(screen.getByTestId('image-lab-preflight')).toBeVisible()

  fireEvent.change(screen.getByRole('combobox', { name: 'generation route' }), { target: { value: 'test_route' } })
  fireEvent.change(screen.getByRole('combobox', { name: 'quality' }), { target: { value: 'maximum' } })
  fireEvent.change(screen.getByRole('combobox', { name: 'identity' }), { target: { value: 'identity_first' } })

  expect(screen.getByRole('combobox', { name: 'generation route' })).toHaveValue('test_route')
  expect(screen.getByRole('combobox', { name: 'quality' })).toHaveValue('maximum')
  expect(screen.getByRole('combobox', { name: 'identity' })).toHaveValue('identity_first')

  fireEvent.click(screen.getByText('More controls'))
  expect(moreControls).not.toHaveAttribute('open')
  fireEvent.click(screen.getByText('More controls'))

  expect(moreControls).toHaveAttribute('open')
  expect(screen.getByRole('combobox', { name: 'generation route' })).toHaveValue('test_route')
  expect(screen.getByRole('combobox', { name: 'quality' })).toHaveValue('maximum')
  expect(screen.getByRole('combobox', { name: 'identity' })).toHaveValue('identity_first')

  /* Keep the existing estimate interaction covered while the disclosure is open. */
  fireEvent.click(screen.getByRole('button', { name: '4 images' }))
  await waitFor(() => expect(screen.getByTestId('image-lab-estimate')).toHaveTextContent('4 images'))
})

it('stacks advanced controls safely in compact mode', async () => {
  renderReadyLab(true)
  const moreControls = await screen.findByTestId('image-lab-more-controls')
  fireEvent.click(screen.getByText('More controls'))

  expect(moreControls).toHaveAttribute('open')
  expect(screen.getByRole('combobox', { name: 'generation route' })).toHaveStyle({ width: '100%' })
  expect(screen.getByTestId('image-lab-preflight')).toHaveStyle({ gridTemplateColumns: '1fr' })
  expect(screen.getByTestId('image-lab-send')).toHaveStyle({ width: '100%' })
})
